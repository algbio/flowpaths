import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.abstractwalkmodeldigraph as walkmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import copy
import numpy as np
import time

class kLeastAbsErrorsCycles(walkmodel.AbstractWalkModelDiGraph):
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
        trusted_edges_for_safety: list = None,
        trusted_edges_for_safety_percentile: float = None,
    ):
        """
        This class implements the k-LeastAbsoluteErrors problem, namely it looks for a decomposition of a weighted general directed graph, possibly with cycles, into 
        $k$ weighted walks, minimizing the absolute errors on the edges. The error on an edge 
        is defined as the absolute value of the difference between the weight of the edge and the sum of the weights of 
        the walks that go through it.

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

        - `trusted_edges_for_safety: list`, optional

            List of edges that are trusted to appear in an optimal solution. Default is `None`. 
            If set, the model can apply the safety optimizations for these edges, so it can be significantly faster.
            See [optimizations documentation](solver-options-optimizations.md#2-optimizations)

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
            trusted_edges_for_safety_internal = [self.G_internal.get_expanded_edge(edge) for edge in trusted_edges_for_safety] if trusted_edges_for_safety else []

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
            trusted_edges_for_safety_internal = trusted_edges_for_safety or []
            error_scaling_internal = error_scaling
        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")

        self.G = stdigraph.stDiGraph(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subset_constraints = subset_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)
        self.trusted_edges_for_safety = set(trusted_edges_for_safety_internal)

        if len(self.trusted_edges_for_safety) == 0 and trusted_edges_for_safety_percentile is not None:            
            # Select edges where the flow_attr value is >= trusted_edges_for_safety_percentile (using self.G)
            flow_values = [self.G.edges[edge][flow_attr] for edge in self.G.edges() if flow_attr in self.G.edges[edge]]
            percentile = np.percentile(flow_values, trusted_edges_for_safety_percentile) if flow_values else 0
            self.trusted_edges_for_safety = set(edge for edge in self.G.edges() if flow_attr in self.G.edges[edge] and self.G.edges[edge][flow_attr] >= percentile)
            utils.logger.info(f"{__name__}: trusted_edges_for_safety set using using percentile {trusted_edges_for_safety_percentile} = {percentile} to {self.trusted_edges_for_safety}")

        self.edge_error_scaling = error_scaling_internal
        # If the error scaling factor is 0, we ignore the edge
        self.edges_to_ignore |= {edge for edge, factor in self.edge_error_scaling.items() if factor == 0}

        # Remove from trusted_edges_for_safety the edges in edges_to_ignore
        self.trusted_edges_for_safety -= self.edges_to_ignore

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
            self.k = self.G.get_width(list(self.edges_to_ignore))
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
        self.edge_errors_vars = {}

        self.path_weights_sol = None
        self.edge_errors_sol = None
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}
        self.solve_time_start = time.perf_counter()
        
        # If we get subset constraints, and the coverage fraction is 1
        # then we know their edges must appear in the solution, so we add their edges to the trusted edges for safety
        self.optimization_options["trusted_edges_for_safety"] = self.trusted_edges_for_safety or set()
        if self.subset_constraints is not None:
            if self.subset_constraints_coverage == 1.0:
                for constraint in self.subset_constraints:
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
        self._encode_leastabserrors_decomposition()

        # This method is called from the current class to add the objective function
        self._encode_objective()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_leastabserrors_decomposition(self):

        # pi vars 
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
        
        self.edge_errors_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="ee",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )

        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                continue

            f_u_v = data[self.flow_attr]

            # We encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_weights_vars[(i)]
            for i in range(self.k):
                self.solver.add_integer_continuous_product_constraint(
                    integer_var=self.edge_vars[(u, v, i)],
                    continuous_var=self.path_weights_vars[(i)],
                    product_var=self.pi_vars[(u, v, i)],
                    lb=0,
                    ub=self.w_max,
                    name=f"u={u}_v={v}_i={i}_10",
                )

            # Encoding the error on the edge (u, v) as the difference between 
            # the flow value of the edge and the sum of the weights of the walks that go through it (pi variables)
            # If we minimize the sum of edge_errors_vars, then we are minimizing the sum of the absolute errors.
            self.solver.add_constraint(
                f_u_v - sum(self.pi_vars[(u, v, i)] for i in range(self.k)) <= self.edge_errors_vars[(u, v)],
                name=f"u={u}_v={v}_i={i}_9aa",
            )

            self.solver.add_constraint(
                self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k)) - f_u_v <= self.edge_errors_vars[(u, v)],
                name=f"u={u}_v={v}_i={i}_9ab",
            )

    def _encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(
                self.edge_errors_vars[(u, v)] * self.edge_error_scaling.get((u, v), 1) if self.edge_error_scaling.get((u, v), 1) != 1 else self.edge_errors_vars[(u, v)]
                for (u,v) in self.edge_indexes_basic), 
            sense="minimize"
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
        for walk, weight in zip(solution["walks"], solution["weights"]):
            if len(walk) > 1:
                non_empty_walks.append(walk)
                non_empty_weights.append(weight)

        solution_copy["walks"] = non_empty_walks
        solution_copy["weights"] = non_empty_weights
        return solution_copy

    def get_solution(self, remove_empty_walks=True):
        """
        Retrieves the solution for the flow decomposition problem.

        If the solution has already been computed and cached as `self.solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution walks, weights, slacks
        and caches the solution.


        Returns
        -------
        - `solution: dict`

            A dictionary containing the solution walks (key `"walks"`) and their corresponding weights (key `"weights"`), and the edge errors (key `"edge_errors"`).

        Raises
        -------
        - `exception` If model is not solved.
        """

        if self._solution is not None:
            return self._remove_empty_walks(self._solution) if remove_empty_walks else self._solution

        self.check_is_solved()

        weights_sol_dict = self.solver.get_values(self.path_weights_vars)

        utils.logger.debug(f"{__name__}: weights_sol_dict = {weights_sol_dict}")

        self.path_weights_sol = [
            (
                round(weights_sol_dict[i])
                if self.weight_type == int
                else float(weights_sol_dict[i])
            )
            for i in range(self.k)
        ]
        self.edge_errors_sol = self.solver.get_values(self.edge_errors_vars)
        for (u,v) in self.edge_indexes_basic:
            self.edge_errors_sol[(u,v)] = round(self.edge_errors_sol[(u,v)]) if self.weight_type == int else float(self.edge_errors_sol[(u,v)])

        if self.flow_attr_origin == "edge":
            self._solution = {
                "walks": self.get_solution_walks(),
                "weights": self.path_weights_sol,
                "edge_errors": self.edge_errors_sol # This is a dictionary with keys (u,v) and values the error on the edge (u,v)
            }
        elif self.flow_attr_origin == "node":
            self._solution = {
                "_walks_internal": self.get_solution_walks(),
                "walks": self.G_internal.get_condensed_paths(self.get_solution_walks()),
                "weights": self.path_weights_sol,
                "edge_errors": self.edge_errors_sol # This is a dictionary with keys (u,v) and values the error on the edge (u,v)
            }

        return self._remove_empty_walks(self._solution) if remove_empty_walks else self._solution

    def is_valid_solution(self, tolerance=0.001):
        """
        Checks if the solution is valid by comparing the flow from walks with the flow attribute in the graph edges.

        Raises
        ------
        - ValueError: If the solution is not available (i.e., self.solution is None).

        Returns
        -------
        - bool: True if the solution is valid, False otherwise.

        Notes
        -------
        - `get_solution()` must be called before this method.
        - The solution is considered valid if the flow from walks is equal
            (up to `TOLERANCE * num_edge_walks_on_edges[(u, v)]`) to the flow value of the graph edges.
        """

        if self._solution is None:
            self.get_solution()

        solution_walks = self._solution.get("_walks_internal", self._solution["walks"])
        solution_weights = self._solution["weights"]
        solution_errors = self._solution["edge_errors"]
        solution_walks_of_edges = [
            [(walk[i], walk[i + 1]) for i in range(len(walk) - 1)]
            for walk in solution_walks
        ]

        weight_from_walks = {(u, v): 0 for (u, v) in self.G.edges()}
        num_edge_walks_on_edges = {e: 0 for e in self.G.edges()}
        for weight, walk in zip(solution_weights, solution_walks_of_edges):
            for e in walk:
                weight_from_walks[e] += weight
                num_edge_walks_on_edges[e] += 1

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u,v) not in self.edges_to_ignore:
                if (
                    abs(data[self.flow_attr] - weight_from_walks[(u, v)])
                    > tolerance * max(1,num_edge_walks_on_edges[(u, v)]) + solution_errors[(u, v)]
                ):
                    utils.logger.debug(
                        f"{__name__}: Invalid solution for edge ({u}, {v}): "
                        f"flow value {data[self.flow_attr]} != weight from walks {weight_from_walks[(u, v)]} "
                        f"+ error {solution_errors[(u, v)]} (tolerance: {tolerance * max(1,num_edge_walks_on_edges[(u, v)])})"
                    )
                    return False

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.k:
            utils.logger.debug(
                f"{__name__}: Invalid solution: objective value {self.get_objective_value()} != solver objective value {self.solver.get_objective_value()} (tolerance: {tolerance * self.k})"
            )
            return False

        return True

    def get_objective_value(self):

        self.check_is_solved()

        # sum of edge errors
        edge_errors = self.get_solution()["edge_errors"]
        return sum(edge_errors.values())
    
    def get_lowerbound_k(self):

        return 1