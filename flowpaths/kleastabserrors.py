import networkx as nx
import flowpaths.stdag as stdag
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import copy


class kLeastAbsErrors(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        k: int,
        flow_attr_origin: str = "edge",
        weight_type: type = float,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        length_attr: str = None,
        elements_to_ignore: list = [],
        error_scaling: dict = {},
        additional_starts: list = [],
        additional_ends: list = [],
        solution_weights_superset: list = None,
        optimization_options: dict = None,
        solver_options: dict = {},
        trusted_edges_for_safety: list = None,
    ):
        """
        This class implements the k-LeastAbsoluteErrors problem, namely it looks for a decomposition of a weighted DAG into 
        $k$ weighted paths, minimizing the absolute errors on the edges. The error on an edge 
        is defined as the absolute value of the difference between the weight of the edge and the sum of the weights of 
        the paths that go through it.

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed acyclic graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html).

        - `flow_attr: str`
            
            The attribute name from where to get the flow values on the edges.

        - `k: int`
            
            The number of paths to decompose in.

        - `flow_attr_origin: str`, optional

            The origin of the flow attribute. Default is `"edge"`. Options:
            
            - `"edge"`: the flow attribute is assumed to be on the edges of the graph.
            - `"node"`: the flow attribute is assumed to be on the nodes of the graph. See [the documentation](node-expanded-digraph.md) on how node-weighted graphs are handled.

        - `weight_type: int | float`, optional
            
            The type of the weights and slacks (`int` or `float`). Default is `float`.

         - `subpath_constraints: list`, optional
            
            List of subpath constraints. Default is an empty list. 
            Each subpath constraint is a list of edges that must be covered by some solution path, according 
            to the `subpath_constraints_coverage` or `subpath_constraints_coverage_length` parameters (see below).

        - `subpath_constraints_coverage: float`, optional
            
            Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            
            Defaults to `1.0`, meaning that 100% of the edges (or nodes, if `flow_attr_origin` is `"node"`) of 
            the constraint need to be covered by some solution path). 
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `subpath_constraints_coverage_length: float`, optional
            
            Coverage length of the subpath constraints. Default is `None`. If set, this overrides `subpath_constraints_coverage`, 
            and the coverage constraint is expressed in terms of the subpath constraint length. 
            `subpath_constraints_coverage_length` is then the fraction of the total length of the constraint (specified via `length_attr`) needs to appear in some solution path.
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `length_attr: str`, optional
            
            The attribute name from where to get the edge lengths (or node length, if `flow_attr_origin` is `"node"`). Defaults to `None`.
            
            - If set, then the subpath lengths (above) are in terms of the edge/node lengths specified in the `length_attr` field of each edge/node.
            - If set, and an edge/node has a missing edge length, then it gets length 1.
        
        - `elements_to_ignore: list`, optional

            List of edges (or nodes, if `flow_attr_origin` is `"node"`) to ignore when adding constrains on flow explanation by the weighted paths. 
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `error_scaling: dict`, optional
            
            Dictionary `edge: factor` (or `node: factor`, if `flow_attr_origin` is `"node"`)) storing the error scale factor (in [0,1]) of every edge, which scale the allowed difference between edge/node weight and path weights.
            Default is an empty dict. If an edge/node has a missing error scale factor, it is assumed to be 1. The factors are used to scale the 
            difference between the flow value of the edge/node and the sum of the weights of the paths going through the edge/node. See [ignoring edges documentation](ignoring-edges.md)
        
        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list.

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list.

        - `solution_weights_superset: list`, optional

            List of allowed weights for the paths. Default is `None`. 
            If set, the model will use the solution path weights only from this set, with the property that **every weight in the superset
            appears at most once in the solution weight**.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).

        - `trusted_edges_for_safety: list`, optional

            List of edges that are trusted to appear in an optimal solution. Default is `None`. 
            If set, the model can apply the safety optimizations for these edges, so it can be significantly faster.
            See [optimizations documentation](solver-options-optimizations.md#2-optimizations)

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
            self.G_internal = nedg.NodeExpandedDiGraph(G, node_flow_attr=flow_attr, node_length_attr=length_attr)
            subpath_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subpath_constraints)
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
            subpath_constraints_internal = subpath_constraints
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

        self.G = stdag.stDAG(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subpath_constraints = subpath_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)
        self.trusted_edges_for_safety = trusted_edges_for_safety_internal
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
        self.original_k = k
        self.solution_weights_superset = solution_weights_superset
        self.optimization_options = optimization_options or {}        

        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.length_attr = length_attr

        if self.solution_weights_superset is not None:
            self.k = len(self.solution_weights_superset)
            self.optimization_options["allow_empty_paths"] = True
            self.optimization_options["optimize_with_safe_paths"] = False
            self.optimization_options["optimize_with_safe_sequences"] = False
            self.optimization_options["optimize_with_safe_zero_edges"] = False
            if len(self.subpath_constraints) > 0:
                self.optimization_options["optimize_with_subpath_constraints_as_safe_sequences"] = True
                self.optimization_options["optimize_with_safety_as_subpath_constraints"] = True
        
        self.flow_attr = flow_attr
        self.w_max = self.k * self.weight_type(
            self.G.get_max_flow_value_and_check_non_negative_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )
        self.w_max = max(self.w_max, max(self.solution_weights_superset or [0]))

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.edge_errors_vars = {}

        self.path_weights_sol = None
        self.edge_errors_sol = None
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}
        
        # If we get subpath constraints, and the coverage fraction is 1
        # then we know their edges must appear in the solution, so we add their edges to the trusted edges for safety
        self.optimization_options["trusted_edges_for_safety"] = set(self.trusted_edges_for_safety or [])
        if self.subpath_constraints is not None:
            if (self.subpath_constraints_coverage == 1.0 and self.subpath_constraints_coverage_length is None) \
                or self.subpath_constraints_coverage_length == 1:
                for constraint in self.subpath_constraints:
                    self.optimization_options["trusted_edges_for_safety"].update(constraint)

        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            self.k,
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            length_attr=self.length_attr,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class 
        self._encode_leastabserrors_decomposition()

        # This method is called from the current class    
        self._encode_solution_weights_superset()

        # This method is called from the current class to add the objective function
        self._encode_objective()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_leastabserrors_decomposition(self):

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
                self.solver.add_binary_continuous_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    continuous_var=self.path_weights_vars[(i)],
                    product_var=self.pi_vars[(u, v, i)],
                    lb=0,
                    ub=self.w_max,
                    name=f"10_u={u}_v={v}_i={i}",
                )


            # Encoding the error on the edge (u, v) as the difference between 
            # the flow value of the edge and the sum of the weights of the paths that go through it (pi variables)
            # If we minimize the sum of edge_errors_vars, then we are minimizing the sum of the absolute errors.
            self.solver.add_constraint(
                f_u_v - sum(self.pi_vars[(u, v, i)] for i in range(self.k)) <= self.edge_errors_vars[(u, v)],
                name=f"9aa_u={u}_v={v}_i={i}",
            )

            self.solver.add_constraint(
                self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k)) - f_u_v <= self.edge_errors_vars[(u, v)],
                name=f"9ab_u={u}_v={v}_i={i}",
            )

    def _encode_solution_weights_superset(self):

        if self.solution_weights_superset is not None:

            if len(self.solution_weights_superset) != self.k:
                utils.logger.error(f"{__name__}: solution_weights_superset must have length {self.k}, not {len(self.solution_weights_superset)}")
                raise ValueError(f"solution_weights_superset must have length {self.k}, not {len(self.solution_weights_superset)}")
            if not self.allow_empty_paths:
                utils.logger.error(f"{__name__}: solution_weights_superset is not allowed when allow_empty_paths is False")
                raise ValueError(f"solution_weights_superset is not allowed when allow_empty_paths is False")
            
            # We state that the weight of the i-th path equals the i-th entry of the solution_weights_superset
            for i in range(self.k):
                if self.solution_weights_superset[i] > self.w_max:
                    utils.logger.error(f"{__name__}: solution_weights_superset[{i}] must be less than or equal to {self.w_max}, not {self.solution_weights_superset[i]}")
                    raise ValueError(f"solution_weights_superset[{i}] must be less than or equal to {self.w_max}, not {self.solution_weights_superset[i]}")
                self.solver.add_constraint(
                    self.path_weights_vars[i] == self.solution_weights_superset[i],
                    name=f"solution_weights_superset_{i}",
                )

            # We state that at most self.original_k paths can be used
            self.solver.add_constraint(            
                self.solver.quicksum(
                    self.solver.quicksum(
                            self.edge_vars[(self.G.source, v, i)]
                            for v in self.G.successors(self.G.source)
                    ) for i in range(self.k)
                ) <= self.original_k,
                name="max_paths_original_k_paths",
            )

    def _encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(
                self.edge_errors_vars[(u, v)] * self.edge_error_scaling.get((u, v), 1) if self.edge_error_scaling.get((u, v), 1) != 1 else self.edge_errors_vars[(u, v)]
                for (u,v) in self.edge_indexes_basic), 
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
        
            A dictionary containing the solution paths (key `"paths"`) and their corresponding weights (key `"weights"`), and the edge errors (key `"edge_errors"`).

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
        self.edge_errors_sol = self.solver.get_values(self.edge_errors_vars)
        for (u,v) in self.edge_indexes_basic:
            self.edge_errors_sol[(u,v)] = round(self.edge_errors_sol[(u,v)]) if self.weight_type == int else float(self.edge_errors_sol[(u,v)])

        if self.flow_attr_origin == "edge":
            self._solution = {
                "paths": self.get_solution_paths(),
                "weights": self.path_weights_sol,
                "edge_errors": self.edge_errors_sol # This is a dictionary with keys (u,v) and values the error on the edge (u,v)
            }
        elif self.flow_attr_origin == "node":
            self._solution = {
                "_paths_internal": self.get_solution_paths(),
                "paths": self.G_internal.get_condensed_paths(self.get_solution_paths()),
                "weights": self.path_weights_sol,
                "edge_errors": self.edge_errors_sol # This is a dictionary with keys (u,v) and values the error on the edge (u,v)
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
        solution_errors = self._solution["edge_errors"]
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
                if (
                    abs(data[self.flow_attr] - weight_from_paths[(u, v)])
                    > tolerance * max(1,num_paths_on_edges[(u, v)]) + solution_errors[(u, v)]
                ):
                    utils.logger.debug(
                        f"{__name__}: Invalid solution for edge ({u}, {v}): "
                        f"flow value {data[self.flow_attr]} != weight from paths {weight_from_paths[(u, v)]} "
                        f"+ error {solution_errors[(u, v)]} (tolerance: {tolerance * max(1,num_paths_on_edges[(u, v)])})"
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

        # sum of edge errors
        edge_errors = self.get_solution()["edge_errors"]
        return sum(edge_errors.values())
    
    def get_lowerbound_k(self):

        return 1