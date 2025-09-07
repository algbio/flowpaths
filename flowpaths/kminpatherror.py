import networkx as nx
import flowpaths.stdag as stdag
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import copy


class kMinPathError(pathmodel.AbstractPathModelDAG):
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
        path_length_ranges: list = [],
        path_length_factors: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        solution_weights_superset: list = None,
        optimization_options: dict = None,
        solver_options: dict = None,
    ):
        """
        This class implements the k-MinPathError model from 
        Dias, Tomescu, [Accurate Flow Decomposition via Robust Integer Linear Programming](https://doi.org/10.1109/TCBB.2024.3433523), IEEE/ACM TCBB 2024 (see [preprint](https://helda.helsinki.fi/server/api/core/bitstreams/96693568-d973-4b43-a68f-bc796bbeb225/content))

        Given an edge-weighted DAG, this model looks for k paths, with associated weights and slacks, such that for every edge (u,v), 
        the sum of the weights of the paths going through (u,v) minus the flow value of (u,v) is at most 
        the sum of the slacks of the paths going through (u,v). The objective is to minimize the sum of the slacks.

        The paths start in any source node of the graph and end in any sink node of the graph. You can allow for additional 
        start or end nodes by specifying them in the `additional_starts` and `additional_ends` parameters.

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed acyclic graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html).

        - `flow_attr: str`
            
            The attribute name from where to get the flow values on the edges.

        - `k: int`
            
            The number of paths to decompose in. 

            !!! note "Unknown $k$"
                If you do not have a good guess for $k$, you can pass `k=None` and the model will set $k$ to the edge width of the graph.

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
            `subpath_constraints_coverage_length` is then the fraction of the total length of the constraint (specified via `length_attr`, see below) needs to appear in some solution path.
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

        - `path_length_ranges: list`, optional
            
            List of ranges for the solution path lengths. Default is an empty list. If this list is not empty, the solution path slacks are scaled by the
            corresponding factor in `path_length_factors` depending on the length of the solution path.

            !!! example "Example"
                If you pass
                ```
                path_length_ranges    = [[0, 15], [16, 18], [19, 20], [21, 30], [31, 100000]]
                path_length_factors   = [ 1.6   ,  1.0    ,  1.3    ,  1.7    ,  1.0        ]    
                ```
                For example, if a path has length in the range [0, 15], its slack will be multiplied by 1.6 when comparing the 
                flow value of the edge to the sum of path slacks, but this multiplier will have no effect on the objective function.
                That is, in the objective function we still minimize the sum of path slacks, not the sum of scaled path slacks.
        
        - `path_length_factors: list`, optional

            List of slack scale factors, based on the path lengths. Default is an empty list. If this list is not empty, the path slacks are scaled by the
            corresponding factor in `path_length_factors` depending on the length of the path. See the above example.

        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `solution_weights_superset: list`, optional

            List of allowed weights for the paths. Default is `None`. 
            If set, the model will use the solution path weights only from this set, with the property that **every weight in the superset
            appears at most once in the solution weight**.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).

        Raises
        ----------
        - `ValueError`
            
            - If `weight_type` is not int or float.
            - If some edge does not have the flow attribute specified as `flow_attr`.
            - If `path_length_factors` is not empty and `weight_type` is float.
            - If the number of path length ranges is not equal to the number of error scale factors.
            - If the edge error scaling factor is not between 0 and 1.
            - If the graph contains edges with negative (<0) flow values.  
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
            error_scaling_internal = error_scaling
        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")

        self.G = stdag.stDAG(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subpath_constraints = subpath_constraints_internal
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

        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.length_attr = length_attr

        self.flow_attr = flow_attr

        self.k = k
        # If k is not specified, we set k to the edge width of the graph
        if self.k is None:
            self.k = self.G.get_width(list(self.edges_to_ignore))
        self.original_k = self.k
        self.solution_weights_superset = solution_weights_superset
        self.optimization_options = optimization_options or {}        

        if self.solution_weights_superset is not None:
            self.k = len(self.solution_weights_superset)
            self.optimization_options["allow_empty_paths"] = True
            self.optimization_options["optimize_with_safe_paths"] = False
            self.optimization_options["optimize_with_safe_sequences"] = False
            self.optimization_options["optimize_with_safe_zero_edges"] = False
            self.optimization_options["optimize_with_subpath_constraints_as_safe_sequences"] = True
            self.optimization_options["optimize_with_safety_as_subpath_constraints"] = True

        self.w_max = self.k * self.weight_type(
            self.G.get_max_flow_value_and_check_non_negative_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )
        self.w_max = max(self.w_max, max(self.solution_weights_superset or [0]))

        self.path_length_ranges = path_length_ranges
        self.path_length_factors = path_length_factors
        if len(self.path_length_ranges) != len(self.path_length_factors):
            utils.logger.error(f"{__name__}: The number of path length ranges must be equal to the number of error scale factors.")
            raise ValueError("The number of path length ranges must be equal to the number of error scale factors.")
        if len(self.path_length_factors) > 0 and self.weight_type == float:
            utils.logger.error(f"{__name__}: Error scale factors are only allowed for integer weights.")
            raise ValueError("Error scale factors are only allowed for integer weights.")

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.path_slacks_vars = {}

        self.path_weights_sol = None
        self.path_slacks_sol = None
        self.path_slacks_scaled_sol = None
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}

        self.optimization_options["trusted_edges_for_safety"] = self.G.get_non_zero_flow_edges(
            flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
        ).difference(self.edges_to_ignore)
        
        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            self.k, 
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            length_attr=self.length_attr,
            encode_edge_position=True,
            encode_path_length=True,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics,
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class 
        self._encode_minpatherror_decomposition()

        # This method is called from the current class    
        self._encode_solution_weights_superset()

        # This method is called from the current class to add the objective function
        self._encode_objective()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_minpatherror_decomposition(self):

        # path weights 
        self.path_weights_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="weights",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        
        # pi vars from https://arxiv.org/pdf/2201.10923 page 14
        # We will encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)],
        # assuming self.w_max is a bound for self.path_weights_vars[(i)]
        self.pi_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="pi",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        
        # path slacks
        self.path_slacks_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="slack",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        
        # gamma vars from https://helda.helsinki.fi/server/api/core/bitstreams/96693568-d973-4b43-a68f-bc796bbeb225/content
        # We will encode that edge_vars[(u,v,i)] * self.path_slacks_vars[(i)] = self.gamma_vars[(u,v,i)],
        # assuming self.w_max is a bound for self.path_slacks_vars[(i)]
        self.gamma_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="gamma",
            lb=0,
            ub=self.w_max,
            var_type="continuous",
        )

        if len(self.path_length_factors) > 0:

            # path_error_scale_vars[(i)] will give the error scale factor for path i
            self.slack_factors_vars = self.solver.add_variables(
                self.path_indexes,
                name_prefix="path_slack_scaled",
                lb=min(self.path_length_factors),
                ub=max(self.path_length_factors),
                var_type="continuous"
            )

            # Getting the right error scale factor depending on the path length
            # if path_length_vars[(i)] in [ranges[i][0], ranges[i][1]] then slack_factors_vars[(i)] = constants[i].
            for i in range(self.k):
                self.solver.add_piecewise_constant_constraint(
                    x=self.path_length_vars[(i)], 
                    y=self.slack_factors_vars[(i)],
                    ranges = self.path_length_ranges, 
                    constants = self.path_length_factors,
                    name_prefix=f"error_scale_{i}"
                )

            self.scaled_slack_vars = self.solver.add_variables(
                self.path_indexes,
                name_prefix="scaled_slack",
                lb=0,
                ub=self.w_max * max(self.path_length_factors),
                var_type="continuous",
            )

            # We encode that self.scaled_slack_vars[i] = self.slack_factors_vars[i] * self.path_slacks_vars[i]
            for i in range(self.k):
                self.solver.add_integer_continuous_product_constraint(
                    integer_var=self.path_slacks_vars[i],
                    continuous_var=self.slack_factors_vars[i],
                    product_var=self.scaled_slack_vars[i],
                    lb=0,
                    ub=self.w_max * max(self.path_length_factors),
                    name=f"scaled_slack_i{i}",
                )
                        
        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                continue

            f_u_v = data[self.flow_attr]
            edge_error_scaling_u_v = self.edge_error_scaling.get((u, v), 1)

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

            # We encode that edge_vars[(u,v,i)] * self.path_slacks_vars[(i)] = self.gamma_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_slacks_vars[(i)]

            for i in range(self.k):
                # We take either the scaled slack or the regular slack
                slack_var = self.path_slacks_vars[i] if len(self.path_length_factors) == 0 else self.scaled_slack_vars[i]

                self.solver.add_binary_continuous_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    continuous_var=slack_var,
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
                    utils.logger.error(f"{__name__}: solution_weights_superset[{i}] = {self.solution_weights_superset[i]} > w_max = {self.w_max}")
                    raise ValueError(f"solution_weights_superset[{i}] = {self.solution_weights_superset[i]} > w_max = {self.w_max}")
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
            self.solver.quicksum(self.path_slacks_vars[(i)] for i in range(self.k)), sense="minimize"
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
        non_empty_slacks = []
        non_empty_scaled_slacks = []
        for path, weight, slack, scaled_slack in zip(solution["paths"], solution["weights"], solution["slacks"], solution.get("scaled_slacks", solution["slacks"])):
            if len(path) > 1:
                non_empty_paths.append(path)
                non_empty_weights.append(weight)
                non_empty_slacks.append(slack)
                non_empty_scaled_slacks.append(scaled_slack)

        solution_copy["paths"] = non_empty_paths
        solution_copy["weights"] = non_empty_weights
        solution_copy["slacks"] = non_empty_slacks
        if "scaled_slacks" in solution_copy:
            solution_copy["scaled_slacks"] = non_empty_scaled_slacks

        return solution_copy

    def get_solution(self, remove_empty_paths=True):
        """
        Retrieves the solution for the flow decomposition problem.

        If the solution has already been computed and cached as `self.solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution paths, weights, slacks
        and caches the solution.

        !!! warning "Warning"
            Make sure you called `.solve()` before calling this method.

        Returns
        -------
        - `solution: dict`
        
            A dictionary containing the solution paths (key `"paths"`) and their corresponding weights (key `"weights"`) and slacks (key `"slacks"`). 
            If `path_length_factors` is not empty, it also contains the scaled slacks (key `"scaled_slacks"`).

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
                "paths": self.get_solution_paths(),
                "weights": self.path_weights_sol,
                "slacks": self.path_slacks_sol
                }
        elif self.flow_attr_origin == "node":
            self._solution = {
                "_paths_internal": self.get_solution_paths(),
                "paths": self.G_internal.get_condensed_paths(self.get_solution_paths()),
                "weights": self.path_weights_sol,
                "slacks": self.path_slacks_sol
                }

        if len(self.path_length_factors) > 0:
            slacks_scaled_sol_dict = self.solver.get_values(self.scaled_slack_vars)
            self.path_slacks_scaled_sol = [slacks_scaled_sol_dict[i] for i in range(self.k)]

            self._solution["scaled_slacks"] = self.path_slacks_scaled_sol

        return self._remove_empty_paths(self._solution) if remove_empty_paths else self._solution

    def is_valid_solution(self, tolerance=0.001):
        """
        Checks if the solution is valid by checking of the weighted paths and their slacks satisfy the constraints of the problem. 

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
        - The solution is considered valid if the flow from paths is equal
            (up to `tolerance * num_paths_on_edges[(u, v)]`) to the flow value of the graph edges.
        """

        if self._solution is None:
            self.get_solution()

        if tolerance < 0:
            utils.logger.error(f"{__name__}: tolerance must be non-negative, not {tolerance}")
            raise ValueError(f"tolerance must be non-negative, not {tolerance}")

        solution_paths = self._solution.get("_paths_internal", self._solution["paths"])
        solution_weights = self._solution["weights"]
        solution_slacks = self._solution["slacks"]
        if len(self.path_length_factors) > 0:
            solution_slacks = self._solution["scaled_slacks"]
        for path in solution_paths:
            if len(path) == 1:
                utils.logger.error(f"{__name__}: Encountered a solution path with length 1, which is not allowed.")
                raise ValueError("Solution path with length 1 encountered.")
        solution_paths_of_edges = [
            [(path[i], path[i + 1]) for i in range(len(path) - 1)]
            for path in solution_paths
        ]

        weight_from_paths = {e: 0 for e in self.G.edges()}
        slack_from_paths = {e: 0 for e in self.G.edges()}
        num_paths_on_edges = {e: 0 for e in self.G.edges()}
        for weight, slack, path in zip(
            solution_weights, solution_slacks, solution_paths_of_edges
        ):
            for e in path:
                if e in weight_from_paths:
                    weight_from_paths[e] += weight
                    slack_from_paths[e] += slack
                    num_paths_on_edges[e] += 1

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u,v) not in self.edges_to_ignore:
                if (
                    abs(data[self.flow_attr] - weight_from_paths[(u, v)])
                    > tolerance * num_paths_on_edges[(u, v)] + slack_from_paths[(u, v)]
                ):
                    utils.logger.debug(f"{__name__}: Solution: {self._solution}")
                    utils.logger.debug(f"{__name__}: num_paths_on_edges[(u, v)] = {num_paths_on_edges[(u, v)]}")
                    utils.logger.debug(f"{__name__}: slack_from_paths[(u, v)] = {slack_from_paths[(u, v)]}")
                    utils.logger.debug(f"{__name__}: data[self.flow_attr] = {data[self.flow_attr]}")
                    utils.logger.debug(f"{__name__}: weight_from_paths[(u, v)] = {weight_from_paths[(u, v)]}")
                    utils.logger.debug(f"{__name__}: > {tolerance * num_paths_on_edges[(u, v)] + slack_from_paths[(u, v)]}")
                    
                    var_dict = {var: val for var, val in zip(self.solver.get_all_variable_names(), self.solver.get_all_variable_values())}
                    utils.logger.debug(f"{__name__}: Variable dictionary: {var_dict}")

                    return False

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.k:
            utils.logger.info(f"{__name__}: self.get_objective_value() = {self.get_objective_value()} self.solver.get_objective_value() = {self.solver.get_objective_value()}")
            return False
        
        # Checking that the error scale factor is correctly encoded
        if len(self.path_length_factors) > 0:
            path_length_sol = self.solver.get_values(self.path_length_vars)
            slack_sol = self.solver.get_values(self.path_slacks_vars)
            path_slack_scaled_sol = self.solver.get_values(self.slack_factors_vars)
            scaled_slack_sol = self.solver.get_values(self.scaled_slack_vars) 
            
            for i in range(self.k):
                # Checking which interval the path length is in,
                # and then checking if the error scale factor is correctly encoded, 
                for index, interval in enumerate(self.path_length_ranges):
                    if path_length_sol[i] >= interval[0] and path_length_sol[i] <= interval[1]:
                        if abs(path_slack_scaled_sol[i] - self.path_length_factors[index]) > tolerance:
                            utils.logger.debug(f"{__name__}: path_length_sol: {path_length_sol}")
                            utils.logger.debug(f"{__name__}: slack_sol: {slack_sol}")
                            utils.logger.debug(f"{__name__}: path_slack_scaled_sol: {path_slack_scaled_sol}")
                            utils.logger.debug(f"{__name__}: scaled_slack_sol: {scaled_slack_sol}")

                            return False

        if not self.verify_edge_position():
            return False
        
        if not self.verify_path_length():
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