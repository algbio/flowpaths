import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.abstractwalkmodeldigraph as walkmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import copy
import numpy as np
import time

class kMinPathErrorCycles(walkmodel.AbstractWalkModelDiGraph):
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        k: int = None,
        flow_attr_origin: str = "edge",
        weight_type: type = float,
        subset_constraints: list = [],
        subset_constraints_coverage: float = 1.0,
        elements_to_ignore: list = [],
        error_scaling: dict = {},
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = None,
        solver_options: dict = {},
        trusted_edges_for_safety_percentile: float = None,
    ):
        """
        This class implements the k-MinPathError problem on general directed graphs. Given an edge-weighted DAG, this model looks for k walks, with associated weights and slacks, such that for every edge (u,v), 
        the sum of the weights of the walks going through (u,v) minus the flow value of (u,v) is at most 
        the sum of the slacks of the walks going through (u,v). The objective is to minimize the sum of the slacks.

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html), which can have cycles.

        - `flow_attr: str`
            
            The attribute name from where to get the flow values on the edges.

        - `k: int`
            
            The number of walks to decompose in.

            !!! note "Unknown $k$"
                If you do not have a good guess for $k$, you can pass `k=None` and the model will set $k$ to the condensation width of the graph (i.e. the minimum number of $s$-$t$ walks needed to cover all the edges of the graph, except those in `edges_to_ignore`).

        - `flow_attr_origin: str`, optional

            The origin of the flow attribute. Default is `"edge"`. Options:
            
            - `"edge"`: the flow attribute is assumed to be on the edges of the graph.
            - `"node"`: the flow attribute is assumed to be on the nodes of the graph. See [the documentation](node-expanded-digraph.md) on how node-weighted graphs are handled.

        - `weight_type: int | float`, optional
            
            The type of the weights and slacks (`int` or `float`). Default is `float`.

         - `subset_constraints: list`, optional
            
            List of subset constraints. Default is an empty list. 
            Each subset constraint is a list of edges that must be covered by some solution walk, in any order, according 
            to the `subset_constraints_coverage` parameter (see below).

        - `subset_constraints_coverage: float`, optional

            Coverage fraction of the subset constraints that must be covered by some solution walk. 
            
            Defaults to `1.0`, meaning that 100% of the edges (or nodes, if `flow_attr_origin` is `"node"`) of 
            the constraint need to be covered by some solution walk). 
            See [subset constraints documentation](subset-constraints.md#3-relaxing-the-constraint-coverage)
        
        - `elements_to_ignore: list`, optional

            List of edges (or nodes, if `flow_attr_origin` is `"node"`) to ignore when adding constrains on flow explanation by the weighted walks. 
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `error_scaling: dict`, optional

            Dictionary `edge: factor` (or `node: factor`, if `flow_attr_origin` is `"node"`)) storing the error scale factor (in [0,1]) of every edge, which scale the allowed difference between edge/node weight and walk weights.
            Default is an empty dict. If an edge/node has a missing error scale factor, it is assumed to be 1. The factors are used to scale the 
            difference between the flow value of the edge/node and the sum of the weights of the walks going through the edge/node. See [ignoring edges documentation](ignoring-edges.md)

        - `additional_starts: list`, optional
            
            List of additional start nodes of the walks. Default is an empty list.

        - `additional_ends: list`, optional

            List of additional end nodes of the walks. Default is an empty list.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).

        - `trusted_edges_for_safety_percentile: float`, optional

            If set to a value different than `None`, this will be used to select edges to trust for safety (i.e. they are guaranteed to appear in any optimal solution). 
            Edges whose weight (`flow_attr`) is greater than or equal to the percentile value will be trusted for safety. Default is `None`. This is ignored if `trusted_edges_for_safety` is set.


        Raises
        ------
        - `ValueError`
            
            - If `weight_type` is not `int` or `float`.
            - If the edge error scaling factor is not in [0,1].
            - If the flow attribute `flow_attr` is not specified in some edge.
            - If the graph contains edges with negative flow values.
            - ValueError: If `flow_attr_origin` is not "node" or "edge".
        """
    
        # Handling node-weighted graphs
        self.flow_attr_origin = flow_attr_origin
        if self.flow_attr_origin == "node":
            if G.number_of_nodes() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no nodes. Please provide a graph with at least one node.")
                raise ValueError(f"The input graph G has no nodes. Please provide a graph with at least one node.")
            self.G_internal = nedg.NodeExpandedDiGraph(G, node_flow_attr=flow_attr)
            subset_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subset_constraints)
            additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
            additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)

            if not all(isinstance(element_to_ignore, str) for element_to_ignore in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of nodes (i.e strings), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of nodes (i.e strings), not {elements_to_ignore}")
            edges_to_ignore_internal = self.G_internal.edges_to_ignore
            edges_to_ignore_internal += [self.G_internal.get_expanded_edge(node) for node in elements_to_ignore]
            edges_to_ignore_internal = list(set(edges_to_ignore_internal))

            error_scaling_internal = {self.G_internal.get_expanded_edge(node): error_scaling[node] for node in error_scaling}

        elif self.flow_attr_origin == "edge":
            if G.number_of_edges() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
                raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
            self.G_internal = G
            subset_constraints_internal = subset_constraints
            if not all(isinstance(edge, tuple) and len(edge) == 2 for edge in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
            edges_to_ignore_internal = elements_to_ignore
            additional_starts_internal = additional_starts
            additional_ends_internal = additional_ends
            error_scaling_internal = error_scaling
        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")

        self.G = stdigraph.stDiGraph(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subset_constraints = subset_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)
        self.edge_error_scaling = error_scaling_internal
        # If the error scaling factor is 0, we ignore the edge
        self.edges_to_ignore |= {edge for edge, factor in self.edge_error_scaling.items() if factor == 0}
        
        # Checking that every entry in self.error_scaling is between 0 and 1
        for key, value in error_scaling.items():
            if value < 0 or value > 1:
                utils.logger.error(f"{__name__}: Error scaling factor for {key} must be between 0 and 1.")
                raise ValueError(f"Error scaling factor for {key} must be between 0 and 1.")

        if weight_type not in [int, float]:
            utils.logger.error(f"{__name__}: weight_type must be either int or float, not {weight_type}")
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        self.k = k
        # If k is not specified, we set k to the edge width of the graph
        if self.k is None:
            self.k = self.G.get_width(edges_to_ignore=self.edges_to_ignore)
            utils.logger.info(f"{__name__}: k received as None, we set it to {self.k} (edge width of the graph)")
        self.optimization_options = optimization_options or {}
        self.subset_constraints_coverage = subset_constraints_coverage
        
        self.flow_attr = flow_attr
        self.w_max = self.k * self.weight_type(
            self.G.get_max_flow_value_and_check_non_negative_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.path_slacks_vars = {}

        self.path_weights_sol = None
        self.path_slacks_sol = None
        self.path_slacks_scaled_sol = None
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}
        self.solve_time_start = time.perf_counter()

        if trusted_edges_for_safety_percentile is not None:
            # Select edges where the flow_attr value is >= trusted_edges_for_safety_percentile (using self.G)
            flow_values = [self.G.edges[edge][flow_attr] for edge in self.G.edges() if flow_attr in self.G.edges[edge]]
            percentile = np.percentile(flow_values, trusted_edges_for_safety_percentile) if flow_values else 0
            self.trusted_edges_for_safety = list(edge for edge in self.G.edges() if flow_attr in self.G.edges[edge] and self.G.edges[edge][flow_attr] >= percentile)
            # Remove from trusted_edges_for_safety the edges in edges_to_ignore
            self.trusted_edges_for_safety = set(edge for edge in self.trusted_edges_for_safety if edge not in self.edges_to_ignore)
            utils.logger.info(f"{__name__}: trusted_edges_for_safety set using using percentile {trusted_edges_for_safety_percentile} = {percentile} to {self.trusted_edges_for_safety}")
        else:
            # We trust for safety all edges with non-zero flow and which are not in edges_to_ignore
            self.trusted_edges_for_safety = self.G.get_non_zero_flow_edges(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            ).difference(self.edges_to_ignore)

        self.optimization_options["trusted_edges_for_safety"] = self.trusted_edges_for_safety
        
        # If we get subset constraints, and the coverage fraction is 1
        # then we know their edges must appear in the solution, so we add their edges to the trusted edges for safety
        if self.subset_constraints is not None:
            if self.subset_constraints_coverage == 1.0:
                for constraint in self.subset_constraints:
                    # Convert to set if it's a list
                    self.optimization_options["trusted_edges_for_safety"].update(constraint)

        # Call the constructor of the parent class AbstractWalkModelDiGraph
        super().__init__(
            G=self.G,
            k=self.k,
            # max_edge_repetition=self.w_max,
            max_edge_repetition_dict=self.G.compute_edge_max_reachable_value(flow_attr=self.flow_attr),
            subset_constraints=self.subset_constraints,
            subset_constraints_coverage=self.subset_constraints_coverage,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics
        )

        # This method is called from the super class AbstractWalkModelDiGraph
        self.create_solver_and_walks()

        # This method is called from the current class 
        self._encode_minpatherror_decomposition()

        # This method is called from the current class to add the objective function
        self._encode_objective()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_minpatherror_decomposition(self):

        # walk weights 
        self.path_weights_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="weights",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        
        # We will encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)],
        # assuming self.w_max is a bound for self.path_weights_vars[(i)]
        self.pi_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="pi",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        
        # walk slacks
        self.path_slacks_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="slack",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        
        # We will encode that edge_vars[(u,v,i)] * self.path_slacks_vars[(i)] = self.gamma_vars[(u,v,i)],
        # assuming self.w_max is a bound for self.path_slacks_vars[(i)]
        self.gamma_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="gamma",
            lb=0,
            ub=self.w_max,
            var_type="continuous",
        )
                
        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                continue

            f_u_v = data[self.flow_attr]
            edge_error_scaling_u_v = self.edge_error_scaling.get((u, v), 1)

            # We encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_weights_vars[(i)]
            for i in range(self.k):
                self.solver.add_integer_continuous_product_constraint(
                    integer_var=self.edge_vars[(u, v, i)],
                    continuous_var=self.path_weights_vars[(i)],
                    product_var=self.pi_vars[(u, v, i)],
                    lb=0,
                    ub=self.w_max,
                    name=f"10_u={u}_v={v}_i={i}",
                )

            # We encode that edge_vars[(u,v,i)] * self.path_slacks_vars[(i)] = self.gamma_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_slacks_vars[(i)]
            for i in range(self.k):
                self.solver.add_integer_continuous_product_constraint(
                    integer_var=self.edge_vars[(u, v, i)],
                    continuous_var=self.path_slacks_vars[i],
                    product_var=self.gamma_vars[(u, v, i)],
                    lb=0,
                    ub=self.w_max,
                    name=f"12_u={u}_v={v}_i={i}",
                )

            # We encode that 
            #   abs(f_u_v - sum(self.pi_vars[(u, v, i)] for i in range(self.k))) 
            #   * edge_error_scale_u_v 
            #   <= sum(self.gamma_vars[(u, v, i)] for i in range(self.k))
            self.solver.add_constraint(
                (f_u_v - self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k))) 
                * edge_error_scaling_u_v
                <= self.solver.quicksum(self.gamma_vars[(u, v, i)] for i in range(self.k)),
                name=f"9aa_u={u}_v={v}_i={i}",
            )
            self.solver.add_constraint(
                (f_u_v - self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k))) 
                * edge_error_scaling_u_v
                >= -self.solver.quicksum(self.gamma_vars[(u, v, i)] for i in range(self.k)),
                name=f"9ab_u={u}_v={v}_i={i}",
            )

    def _encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(self.path_slacks_vars[(i)] for i in range(self.k)), sense="minimize"
        )

    def _remove_empty_walks(self, solution):
        """
        Removes empty walks from the solution. Empty walks are those with 0 or 1 nodes.

        Parameters
        ----------
        - `solution: dict`

            The solution dictionary containing walks and weights.

        Returns
        -------
        - `solution: dict`

            The solution dictionary with empty walks removed.

        """
        solution_copy = copy.deepcopy(solution)
        non_empty_walks = []
        non_empty_weights = []
        non_empty_slacks = []
        for walk, weight, slack in zip(solution["walks"], solution["weights"], solution["slacks"]):
            if len(walk) > 1:
                non_empty_walks.append(walk)
                non_empty_weights.append(weight)
                non_empty_slacks.append(slack)

        solution_copy["walks"] = non_empty_walks
        solution_copy["weights"] = non_empty_weights
        solution_copy["slacks"] = non_empty_slacks
        return solution_copy

    def get_solution(self, remove_empty_walks=True):
        """
        Retrieves the solution for the flow decomposition problem.

        If the solution has already been computed and cached as `self.solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution walks, weights, slacks
        and caches the solution.

        !!! warning "Warning"
            Make sure you called `.solve()` before calling this method.

        Returns
        -------
        - `solution: dict`

            A dictionary containing the solution walks (key `"walks"`) and their corresponding weights (key `"weights"`) and slacks (key `"slacks"`).

        Raises
        -------
        - `exception` If model is not solved.
        """

        if self._solution is not None:
            return self._remove_empty_walks(self._solution) if remove_empty_walks else self._solution

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
        slacks_sol_dict = self.solver.get_values(self.path_slacks_vars)
        self.path_slacks_sol = [
            (
                round(slacks_sol_dict[i])
                if self.weight_type == int
                else float(slacks_sol_dict[i])
            )
            for i in range(self.k)
        ]

        if self.flow_attr_origin == "edge":
            self._solution = {
                "walks": self.get_solution_walks(),
                "weights": self.path_weights_sol,
                "slacks": self.path_slacks_sol
                }
        elif self.flow_attr_origin == "node":
            self._solution = {
                "_walks_internal": self.get_solution_walks(),
                "walks": self.G_internal.get_condensed_paths(self.get_solution_walks()),
                "weights": self.path_weights_sol,
                "slacks": self.path_slacks_sol
                }

        return self._remove_empty_walks(self._solution) if remove_empty_walks else self._solution

    def is_valid_solution(self, tolerance=0.001):
        """
        Checks if the solution is valid by checking of the weighted walks and their slacks satisfy the constraints of the problem. 

        !!! warning "Warning"
            Make sure you called `.solve()` before calling this method.

        Raises
        ------
        - `ValueError`: If the solution is not available.

        Returns
        -------
        - `bool`: `True` if the solution is valid, `False` otherwise.

        Notes
        -------
        - `get_solution()` must be called before this method.
        - The solution is considered valid if the flow from walks is equal
            (up to `tolerance * num_edge_walks_on_edges[(u, v)]`) to the flow value of the graph edges.
        """

        if self._solution is None:
            self.get_solution()

        if tolerance < 0:
            utils.logger.error(f"{__name__}: tolerance must be non-negative, not {tolerance}")
            raise ValueError(f"tolerance must be non-negative, not {tolerance}")

        solution_walks = self._solution.get("_walks_internal", self._solution["walks"])
        solution_weights = self._solution["weights"]
        solution_slacks = self._solution["slacks"]
        for walk in solution_walks:
            if len(walk) == 1:
                utils.logger.error(f"{__name__}: Encountered a solution walk with length 1, which is not allowed.")
                raise ValueError("Solution walk with length 1 encountered.")
        solution_walks_of_edges = [
            [(walk[i], walk[i + 1]) for i in range(len(walk) - 1)]
            for walk in solution_walks
        ]

        weight_from_walks = {e: 0 for e in self.G.edges()}
        slack_from_walks = {e: 0 for e in self.G.edges()}
        num_edge_walks_on_edges = {e: 0 for e in self.G.edges()}
        for weight, slack, walk in zip(
            solution_weights, solution_slacks, solution_walks_of_edges
        ):
            for e in walk:
                if e in weight_from_walks:
                    weight_from_walks[e] += weight
                    slack_from_walks[e] += slack
                    num_edge_walks_on_edges[e] += 1

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u,v) not in self.edges_to_ignore:
                if (
                    abs(data[self.flow_attr] - weight_from_walks[(u, v)])
                    > tolerance * num_edge_walks_on_edges[(u, v)] + slack_from_walks[(u, v)]
                ):
                    utils.logger.debug(f"{__name__}: Solution: {self._solution}")
                    utils.logger.debug(f"{__name__}: num_edge_walks_on_edges[(u, v)] = {num_edge_walks_on_edges[(u, v)]}")
                    utils.logger.debug(f"{__name__}: slack_from_walks[(u, v)] = {slack_from_walks[(u, v)]}")
                    utils.logger.debug(f"{__name__}: data[self.flow_attr] = {data[self.flow_attr]}")
                    utils.logger.debug(f"{__name__}: weight_from_walks[(u, v)] = {weight_from_walks[(u, v)]}")
                    utils.logger.debug(f"{__name__}: > {tolerance * num_edge_walks_on_edges[(u, v)] + slack_from_walks[(u, v)]}")

                    var_dict = {var: val for var, val in zip(self.solver.get_all_variable_names(), self.solver.get_all_variable_values())}
                    utils.logger.debug(f"{__name__}: Variable dictionary: {var_dict}")

                    return False

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.k:
            utils.logger.info(f"{__name__}: self.get_objective_value() = {self.get_objective_value()} self.solver.get_objective_value() = {self.solver.get_objective_value()}")
            return False
        
        return True

    def get_objective_value(self):

        self.check_is_solved()

        if self._solution is None:
            self.get_solution()

        # sum of slacks
        return sum(self._solution["slacks"])
    
    def get_lowerbound_k(self):

        if self._lowerbound_k != None:
            return self._lowerbound_k

        self._lowerbound_k = self.G.get_width(edges_to_ignore=self.edges_to_ignore)

        return self._lowerbound_k