import networkx as nx
import flowpaths.stdag as stdag
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import copy


class kMinDiscordantNodes(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        k: int,
        weight_type: type = float,
        discordance_tolerance: float = 0.1,
        subpath_constraints: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = None,
        solver_options: dict = {},
    ):
        """
        This class implements the k-MinDiscordantNodes problem, namely it looks for a decomposition of a weighted DAG into 
        $k$ weighted paths, minimizing the number of *discordant* nodes. A node is *discordant*
        if the sum of the weights of the solution paths traversing it lies outside the interval

            [(1 - discordance_tolerance) * observed_flow,
             (1 + discordance_tolerance) * observed_flow].

        Additionally, it is required that every node and every edge appear in some solution path.

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed acyclic graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html).

        - `k: int`
            
            The number of paths to decompose in.

        - `weight_type: int | float`, optional
            
            The type of the weights and slacks (`int` or `float`). Default is `float`.

         - `subpath_constraints: list`, optional
            
            List of subpath constraints. Default is an empty list. 
            Each subpath constraint is a list of edges that must be covered by some solution path, according 
            to the `subpath_constraints_coverage` or `subpath_constraints_coverage_length` parameters (see below).
        
        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list.

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).

        Raises
        ------
        - `ValueError`
            
            - If `weight_type` is not `int` or `float`.
            - If the edge error scaling factor is not in [0,1].
            - If the flow attribute `flow_attr` is not specified in some edge.
            - If the graph contains edges with negative flow values.
        """
    
        utils.logger.info(f"{__name__}: START initialized with graph id = {utils.fpid(G)}, k = {k}")

        # Handling node-weighted graphs
        if G.number_of_nodes() == 0:
            utils.logger.error(f"{__name__}: The input graph G has no nodes. Please provide a graph with at least one node.")
            raise ValueError(f"The input graph G has no nodes. Please provide a graph with at least one node.")
        self.G_internal = nedg.NodeExpandedDiGraph(G, node_flow_attr=flow_attr)
        subpath_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subpath_constraints)
        additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
        additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)

        edges_to_ignore_internal = self.G_internal.edges_to_ignore

        self.G = stdag.stDAG(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subpath_constraints = subpath_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)
        # Add nodes and edges are required to be covered by the solution paths, 
        # thus all edges of the NodeExpanded Digraphs are trusted for safety
        self.trusted_edges_for_safety = self.G_internal.edges()

        if weight_type not in [int, float]:
            utils.logger.error(f"{__name__}: weight_type must be either int or float, not {weight_type}")
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type


        self.k = k
        self.original_k = k
        self.optimization_options = optimization_options or {}
        self.discordance_tolerance = discordance_tolerance
        
        self.flow_attr = flow_attr
        self.w_max = self.k * self.weight_type(
            self.G.get_max_flow_value_and_check_non_negative_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.discordant_edge_vars = {}
        self.discordant_low_vars = {}
        self.discordant_high_vars = {}

        self.path_weights_sol = None
        self.discordant_edges_sol = None
        self.discordant_nodes_sol = None
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}
                
        self.optimization_options["trusted_edges_for_safety"] = set(self.trusted_edges_for_safety)

        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            self.k,
            subpath_constraints=self.subpath_constraints, 
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class to encode the problem
        self._encode_discordance_decomposition()

        # This method is called from the current class to encode that every node and edge is covered by at least one path
        self._encode_cover_every_node_edge_constraints()

        # This method is called from the current class to add the objective function
        self._encode_objective()

        utils.logger.info(f"{__name__}: END initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_discordance_decomposition(self):

        # pi vars from https://arxiv.org/pdf/2201.10923 page 14
        self.pi_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="pi",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        self.path_weights_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="weights",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )

        self.edge_indexes_basic = [(u,v) for (u,v) in self.G.edges() if (u,v) not in self.edges_to_ignore]

        self.discordant_edge_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="z",
            lb=0,
            ub=1,
            var_type="integer",
        )
        self.discordant_low_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="zlow",
            lb=0,
            ub=1,
            var_type="integer",
        )
        self.discordant_high_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="zhigh",
            lb=0,
            ub=1,
            var_type="integer",
        )

        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                continue

            f_u_v = data[self.flow_attr]
            interval_lb = (1 - self.discordance_tolerance) * f_u_v
            interval_ub = (1 + self.discordance_tolerance) * f_u_v
            total_pi_u_v = self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k))

            # Bound for the sum over k pi variables, each in [0, w_max].
            sum_pi_ub = self.k * self.w_max
            big_m = sum_pi_ub + abs(interval_lb) + abs(interval_ub)
            strict_eps = 1 if self.weight_type == int else 1e-6

            # We encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_weights_vars[(i)]
            for i in range(self.k):
                if (u, v, i) in self.edges_set_to_zero:
                    self.solver.add_constraint(
                            self.pi_vars[(u, v, i)] == 0,
                            name=f"i={i}_u={u}_v={v}_10b",
                        )
                elif (u, v, i) in self.edges_set_to_one:
                    self.solver.add_constraint(
                            self.pi_vars[(u, v, i)] == self.path_weights_vars[(i)],
                            name=f"i={i}_u={u}_v={v}_10b",
                        )
                else:
                    self.solver.add_binary_continuous_product_constraint(
                        binary_var=self.edge_vars[(u, v, i)],
                        continuous_var=self.path_weights_vars[(i)],
                        product_var=self.pi_vars[(u, v, i)],
                        lb=0,
                        ub=self.w_max,
                        name=f"10_u={u}_v={v}_i={i}",
                    )

            # z[(u, v)] = 0 iff total_pi_u_v is inside [interval_lb, interval_ub].
            self.solver.add_constraint(
                total_pi_u_v >= interval_lb - big_m * self.discordant_low_vars[(u, v)],
                name=f"disc_lb_u={u}_v={v}",
            )
            self.solver.add_constraint(
                total_pi_u_v <= interval_ub + big_m * self.discordant_high_vars[(u, v)],
                name=f"disc_ub_u={u}_v={v}",
            )
            self.solver.add_constraint(
                total_pi_u_v <= interval_lb - strict_eps + big_m * (1 - self.discordant_low_vars[(u, v)]),
                name=f"disc_force_low_u={u}_v={v}",
            )
            self.solver.add_constraint(
                total_pi_u_v >= interval_ub + strict_eps - big_m * (1 - self.discordant_high_vars[(u, v)]),
                name=f"disc_force_high_u={u}_v={v}",
            )
            self.solver.add_constraint(
                self.discordant_low_vars[(u, v)] + self.discordant_high_vars[(u, v)] <= 1,
                name=f"disc_side_exclusive_u={u}_v={v}",
            )
            self.solver.add_constraint(
                self.discordant_edge_vars[(u, v)] == self.discordant_low_vars[(u, v)] + self.discordant_high_vars[(u, v)],
                name=f"disc_z_link_u={u}_v={v}",
            )

    def _encode_cover_every_node_edge_constraints(self):
        """
        Adds constraints to ensure that every node and edge of the input graph is covered by at least one path.
        """
        for u, v in self.G.edges():
            if (u, v) in self.G.source_sink_edges:
                continue
            
            # At least one path must cover this
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.edge_vars[(u, v, i)] for i in range(self.k)
                ) >= 1,
                name=f"cover_edge_u={u}_v={v}",
            )

    def _encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(
                self.discordant_edge_vars[(u, v)] for (u, v) in self.edge_indexes_basic
            ),
            sense="minimize"
        )

    def _remove_empty_paths(self, solution):
        """
        Removes empty paths from the solution. Empty paths are those with 0 or 1 nodes.

        Parameters
        ----------
        - `solution: dict`
            
            The solution dictionary containing paths and weights.

        Returns
        -------
        - `solution: dict`
            
            The solution dictionary with empty paths removed.

        """
        solution_copy = copy.deepcopy(solution)
        non_empty_paths = []
        non_empty_weights = []
        for path, weight in zip(solution["paths"], solution["weights"]):
            if len(path) > 1:
                non_empty_paths.append(path)
                non_empty_weights.append(weight)

        solution_copy["paths"] = non_empty_paths
        solution_copy["weights"] = non_empty_weights
        return solution_copy

    def get_solution(self, remove_empty_paths=True):
        """
        Retrieves the solution for the flow decomposition problem.

        If the solution has already been computed and cached as `self.solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution paths, weights, slacks
        and caches the solution.


        Returns
        -------
        - `solution: dict`
        
            A dictionary containing the solution paths (key `"paths"`) and their corresponding
            weights (key `"weights"`), and binary discordance indicators in the
            original graph (key `"discordant_nodes"`, keyed by original nodes).

        Raises
        -------
        - `exception` If model is not solved.
        """

        if self._solution is not None:
            return self._remove_empty_paths(self._solution) if remove_empty_paths else self._solution

        self.check_is_solved()

        weights_sol_dict = self.solver.get_values(self.path_weights_vars)

        self.path_weights_sol = [
            (
                round(weights_sol_dict[i])
                if self.weight_type == int
                else float(weights_sol_dict[i])
            )
            for i in range(self.k)
        ]
        self.discordant_edges_sol = self.solver.get_values(self.discordant_edge_vars)
        for (u, v) in self.edge_indexes_basic:
            self.discordant_edges_sol[(u, v)] = int(round(self.discordant_edges_sol[(u, v)]))
        self.discordant_nodes_sol = {}
        for expanded_edge, z_value in self.discordant_edges_sol.items():
            condensed_node = self.G_internal.get_condensed_node(expanded_edge)
            if condensed_node is not None:
                self.discordant_nodes_sol[condensed_node] = z_value
            else:
                utils.logger.error(
                    f"{__name__}: Error: expanded edge {expanded_edge} does not correspond to any condensed node. This should not happen."
                )

        self._solution = {
            "_paths_internal": self.get_solution_paths(),
            "paths": self.G_internal.get_condensed_paths(self.get_solution_paths()),
            "weights": self.path_weights_sol,
            "discordant_nodes": self.discordant_nodes_sol,  # Keys are original graph nodes, values are in {0,1}.
        }

        return self._remove_empty_paths(self._solution) if remove_empty_paths else self._solution

    def is_valid_solution(self, tolerance=0.001):
        """
        Checks if the solution is valid by comparing the flow from paths with the flow attribute in the graph edges.

        Raises
        ------
        - ValueError: If the solution is not available (i.e., self.solution is None).

        Returns
        -------
        - bool: True if the solution is valid, False otherwise.

        Notes
        -------
        - `get_solution()` must be called before this method.
        - The solution is considered valid if the flow from paths is equal
            (up to `TOLERANCE * num_paths_on_edges[(u, v)]`) to the flow value of the graph edges.
        """

        if self._solution is None:
            self.get_solution()

        solution_paths = self._solution.get("_paths_internal", self._solution["paths"])
        solution_weights = self._solution["weights"]
        if self.discordant_edges_sol is None:
            self.discordant_edges_sol = self.solver.get_values(self.discordant_edge_vars)
            for (u, v) in self.edge_indexes_basic:
                self.discordant_edges_sol[(u, v)] = int(round(self.discordant_edges_sol[(u, v)]))

        solution_discordance_expanded = self.discordant_edges_sol
        solution_paths_of_edges = [
            [(path[i], path[i + 1]) for i in range(len(path) - 1)]
            for path in solution_paths
        ]

        weight_from_paths = {(u, v): 0 for (u, v) in self.G.edges()}
        num_paths_on_edges = {e: 0 for e in self.G.edges()}
        for weight, path in zip(solution_weights, solution_paths_of_edges):
            for e in path:
                weight_from_paths[e] += weight
                num_paths_on_edges[e] += 1

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u,v) not in self.edges_to_ignore:
                interval_lb = (1 - self.discordance_tolerance) * data[self.flow_attr]
                interval_ub = (1 + self.discordance_tolerance) * data[self.flow_attr]
                inside_interval = interval_lb - tolerance <= weight_from_paths[(u, v)] <= interval_ub + tolerance
                edge_z = int(round(solution_discordance_expanded[(u, v)]))

                if edge_z == 0 and not inside_interval:
                    utils.logger.debug(
                        f"{__name__}: Invalid solution for expanded-graph node item ({u}, {v}): z=0 but "
                        f"weight from paths {weight_from_paths[(u, v)]} is outside "
                        f"[{interval_lb}, {interval_ub}]"
                    )
                    return False
                if edge_z == 1 and inside_interval:
                    utils.logger.debug(
                        f"{__name__}: Invalid solution for expanded-graph node item ({u}, {v}): z=1 but "
                        f"weight from paths {weight_from_paths[(u, v)]} is inside "
                        f"[{interval_lb}, {interval_ub}]"
                    )
                    return False

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.original_k:
            utils.logger.debug(
                f"{__name__}: Invalid solution: objective value {self.get_objective_value()} != solver objective value {self.solver.get_objective_value()} (tolerance: {tolerance * self.original_k})"
            )
            return False

        return True

    def get_objective_value(self):

        self.check_is_solved()

        if self.discordant_edges_sol is None:
            self.get_solution()

        # Number of discordant node items in the node-expanded graph.
        return sum(self.discordant_edges_sol.values())
    
    def get_lowerbound_k(self):

        if self._lowerbound_k != None:
            return self._lowerbound_k

        self._lowerbound_k = self.G.get_width()

        return self._lowerbound_k