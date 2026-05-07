import networkx as nx
import flowpaths.stdag as stdag
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import math
import copy


class kMinDiscordantNodes(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        k: int,
        weight_type: type = float,
        discordance_tolerance: float = 0.1,
        subsequence_constraints: list = [],
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

        - `subsequence_constraints: list`, optional
            
            List of subsequence constraints. Default is an empty list.
            Each constraint is a list of node names that must all be visited (in order) by some solution path.
            Internally, each node is mapped to its expanded edge ``(node.0, node.1)`` via ``NodeExpandedDiGraph``.
        
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
        subpath_constraints_internal = self.G_internal._get_expanded_subpath_constraints_nodes(subsequence_constraints)
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
        max_flow = self.G.get_max_flow_value_and_check_non_negative_flow(
            flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
        )
        w_max_base = (1 + self.discordance_tolerance) * max_flow
        self.w_max = math.ceil(w_max_base) if self.weight_type == int else float(w_max_base)
        self.path_cover_mip_start_paths = self.optimization_options.get("path_cover_mip_start_paths", [])

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

        # If available, seed the MILP with a structural path-cover witness.
        self._apply_path_cover_mip_start()

        utils.logger.info(f"{__name__}: END initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_discordance_decomposition(self):

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

        self.discordant_low_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="zlow",
            lb=0,
            ub=1,
            var_type="binary",
        )
        self.discordant_high_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="zhigh",
            lb=0,
            ub=1,
            var_type="binary",
        )

        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                continue

            f_u_v = data[self.flow_attr]
            interval_lb = (1 - self.discordance_tolerance) * f_u_v
            interval_ub = (1 + self.discordance_tolerance) * f_u_v
            total_pi_u_v = self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k))

            big_m = 2 * self.w_max
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

            self.solver.add_constraint(
                self.discordant_low_vars[(u, v)] + self.discordant_high_vars[(u, v)] <= 1,
                name=f"disc_side_exclusive_u={u}_v={v}",
            )

            if self.solver.external_solver == "gurobi":
                self.solver.add_indicator_constraint(
                    self.discordant_low_vars[(u, v)],
                    0,
                    total_pi_u_v >= interval_lb,
                    name=f"disc_ind_lb0_u={u}_v={v}",
                )
                self.solver.add_indicator_constraint(
                    self.discordant_low_vars[(u, v)],
                    1,
                    total_pi_u_v <= interval_lb - strict_eps,
                    name=f"disc_ind_lb1_u={u}_v={v}",
                )
                self.solver.add_indicator_constraint(
                    self.discordant_high_vars[(u, v)],
                    0,
                    total_pi_u_v <= interval_ub,
                    name=f"disc_ind_ub0_u={u}_v={v}",
                )
                self.solver.add_indicator_constraint(
                    self.discordant_high_vars[(u, v)],
                    1,
                    total_pi_u_v >= interval_ub + strict_eps,
                    name=f"disc_ind_ub1_u={u}_v={v}",
                )
            else:
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
                self.discordant_low_vars[(u, v)] + self.discordant_high_vars[(u, v)]
                for (u, v) in self.edge_indexes_basic
            ),
            sense="minimize"
        )

    def _path_satisfies_subpath_constraint(self, path_edges: set, constraint: list) -> bool:
        """Return whether a seeded path satisfies one expanded-graph subpath constraint."""
        if self.subpath_constraints_coverage_length is None:
            covered_edges = sum((edge in path_edges) for edge in constraint)
            required_coverage = len(constraint) * self.subpath_constraints_coverage
            return covered_edges + 1e-9 >= required_coverage

        covered_length = sum(
            self.G[u][v].get(self.length_attr, 1)
            for (u, v) in constraint
            if (u, v) in path_edges
        )
        required_length = (
            sum(self.G[u][v].get(self.length_attr, 1) for (u, v) in constraint)
            * self.subpath_constraints_coverage_length
        )
        return covered_length + 1e-9 >= required_length

    def _get_seed_internal_path(self, condensed_path: list):
        """Map one original-node path to a full source-to-sink path in the expanded st-DAG."""
        if not condensed_path:
            return None

        expanded_path = [self.G.source]
        for node in condensed_path:
            expanded_edge = self.G_internal.get_expanded_edge(node)
            expanded_path.extend([expanded_edge[0], expanded_edge[1]])
        expanded_path.append(self.G.sink)

        for edge in zip(expanded_path[:-1], expanded_path[1:]):
            if not self.G.has_edge(*edge):
                return None

        return expanded_path

    def _apply_path_cover_mip_start(self):
        """Seed the MILP with a structural path-cover witness when available."""
        if not self.path_cover_mip_start_paths:
            return

        if self.solver.external_solver != "gurobi":
            utils.logger.info(
                f"{__name__}: Structural path-cover witness with {len(self.path_cover_mip_start_paths)} paths is available, but MIP starts are only enabled for Gurobi.",
            )
            return

        if self.k < len(self.path_cover_mip_start_paths):
            utils.logger.info(
                f"{__name__}: Skipping path-cover MIP start because k={self.k} is smaller than witness size {len(self.path_cover_mip_start_paths)}.",
            )
            return

        seeded_paths = []
        for condensed_path in self.path_cover_mip_start_paths:
            expanded_path = self._get_seed_internal_path(condensed_path)
            if expanded_path is None:
                utils.logger.warning(
                    f"{__name__}: Skipping path-cover MIP start because witness path {condensed_path} cannot be embedded in the expanded st-DAG.",
                )
                return
            seeded_paths.append(expanded_path)

        if not seeded_paths:
            return

        while len(seeded_paths) < self.k:
            seeded_paths.append(list(seeded_paths[0]))

        path_edge_sets = [
            set(zip(path[:-1], path[1:]))
            for path in seeded_paths
        ]

        start_values = {}

        for i, path_edges in enumerate(path_edge_sets):
            for (u, v, path_index) in self.edge_indexes:
                if path_index != i:
                    continue
                start_values[self.edge_vars[(u, v, path_index)]] = 1.0 if (u, v) in path_edges else 0.0

        for i in self.path_indexes:
            start_values[self.path_weights_vars[i]] = 0.0

        for edge_index in self.edge_indexes:
            start_values[self.pi_vars[edge_index]] = 0.0

        for edge in self.edge_indexes_basic:
            start_values[self.discordant_low_vars[edge]] = 1.0
            start_values[self.discordant_high_vars[edge]] = 0.0

        if len(self.subpath_constraints) > 0:
            for i, path_edges in enumerate(path_edge_sets):
                for j, constraint in enumerate(self.subpath_constraints):
                    start_values[self.subpaths_vars[(i, j)]] = 1.0 if self._path_satisfies_subpath_constraint(path_edges, constraint) else 0.0

        self.solver.set_start_values(start_values)
        self.solve_statistics["optimizations_applied"].add("optimize_with_path_cover_mip_start")
        self.solve_statistics["path_cover_mip_start_path_count"] = len(self.path_cover_mip_start_paths)
        utils.logger.info(
            f"{__name__}: Seeded Gurobi with a feasible path-cover MIP start using {len(self.path_cover_mip_start_paths)} structural paths.",
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
        discordant_lows = self.solver.get_values(self.discordant_low_vars)
        discordant_highs = self.solver.get_values(self.discordant_high_vars)
        self.discordant_edges_sol = {}
        for (u, v) in self.edge_indexes_basic:
            self.discordant_edges_sol[(u, v)] = int(round(discordant_lows[(u, v)])) + int(round(discordant_highs[(u, v)]))
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
            discordant_lows = self.solver.get_values(self.discordant_low_vars)
            discordant_highs = self.solver.get_values(self.discordant_high_vars)
            self.discordant_edges_sol = {}
            for (u, v) in self.edge_indexes_basic:
                self.discordant_edges_sol[(u, v)] = int(round(discordant_lows[(u, v)])) + int(round(discordant_highs[(u, v)]))

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