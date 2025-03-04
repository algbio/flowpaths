import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.abstractpathmodeldag as pathmodel


class kMinPathError(pathmodel.AbstractPathModelDAG):
    """
    This class implements the k-MinPathError model from 
    Dias, Tomescu, "Accurate Flow Decomposition via Robust Integer Linear Programming", IEEE/ACM TCBB 2024
    https://doi.org/10.1109/TCBB.2024.3433523
    (see also https://helda.helsinki.fi/server/api/core/bitstreams/96693568-d973-4b43-a68f-bc796bbeb225/content)

    Given an edge-weighted DAG, this model looks for k paths, with associated weights and slacks, such that for every edge (u,v), 
    the sum of the weights of the paths going through (u,v) minus the flow value of (u,v) is at most 
    the sum of the slacks of the paths going through (u,v). The objective is to minimize the sum of the slacks.

    The paths start in any source node of the graph and end in any sink node of the graph. You can allow for additional 
    start or end nodes by specifying them in the `additional_starts` and `additional_ends` parameters.
    """
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        k: int,
        weight_type: type = float,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        edge_length_attr: str = None,
        edges_to_ignore: list = [],
        edge_error_scaling: dict = {},
        path_length_ranges: list = [],
        path_length_factors: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = None,
        solver_options: dict = None,
    ):
        """
        Initialize the Min Path Error model for a given number of paths.

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed acyclic graph, as networkx DiGraph.

        - `flow_attr: str`
            
            The attribute name from where to get the flow values on the edges.

        - `k: int`
            
            The number of paths to decompose in.

        - `weight_type: int | float`, optional
            
            The type of the weights and slacks (`int` or `float`). Default is `float`.

         - `subpath_constraints : list`, optional
            
            List of subpath constraints. Default is an empty list. 
            Each subpath constraint is a list of edges that must be covered by some solution path, according 
            to the `subpath_constraints_coverage` or `subpath_constraints_coverage_length` parameters (see below).

        - `subpath_constraints_coverage : float`, optional
            
            Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            
            Defaults to `1.0` (meaning that 100% of the edges of the constraint need to be covered by some solution path). See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `subpath_constraints_coverage_length : float`, optional
            
            Coverage length of the subpath constraints. Default is `None`. If set, this overrides `subpath_constraints_coverage`, 
            and the coverage constraint is expressed in terms of the subpath constraint length. 
            `subpath_constraints_coverage_length` is then the fraction of the total length of the constraint (specified via `edge_length_attr`) needs to appear in some solution path.
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `edges_to_ignore: list`, optional
            
            List of edges to ignore when adding constrains on flow explanation by the weighted paths and their slack.
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `edge_error_scaling: dict`, optional
            
            Dictionary `edge: factor` storing the error scale factor (in [0,1]) of every edge, which scale the allowed difference between edge weight and path weights.
            Default is an empty dict. If an edge has a missing error scale factor, it is assumed to be 1. The factors are used to scale the 
            difference between the flow value of the edge and the sum of the weights of the paths going through the edge.

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
            
            List of additional start nodes of the paths. Default is an empty list.

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

        Raises
        ----------
        - `ValueError`
            
            - If `weight_type` is not int or float.
            - If some edge does not have the flow attribute specified as `flow_attr`.
            - If `path_length_factors` is not empty and `weight_type` is float.
            - If the number of path length ranges is not equal to the number of error scale factors.
            - If the edge error scaling factor is not between 0 and 1.
            - If the graph contains edges with negative (<0) flow values.            
        """

        self.G = stdigraph.stDiGraph(G, additional_starts=additional_starts, additional_ends=additional_ends)

        if weight_type not in [int, float]:
            raise ValueError(
                f"weight_type must be either int or float, not {weight_type}"
            )
        self.weight_type = weight_type

        self.edges_to_ignore = set(edges_to_ignore).union(self.G.source_sink_edges)

        self.flow_attr = flow_attr
        self.w_max = k * self.weight_type(
            self.G.get_max_flow_value_and_check_positive_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )

        self.k = k
        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr
        self.edge_error_scaling = edge_error_scaling
        # Checking that every entry in self.edge_error_scaling is between 0 and 1
        for key, value in self.edge_error_scaling.items():
            if value < 0 or value > 1:
                raise ValueError(f"Edge error scaling factor for edge {key} must be between 0 and 1.")
            if value == 0:
                self.edges_to_ignore.add(key)
            
        self.path_length_ranges = path_length_ranges
        self.path_length_factors = path_length_factors
        if len(self.path_length_ranges) != len(self.path_length_factors):
            raise ValueError("The number of path length ranges must be equal to the number of error scale factors.")
        if len(self.path_length_factors) > 0 and self.weight_type == float:
            raise ValueError("Error scale factors are only allowed for integer weights.")

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.path_slacks_vars = {}

        self.path_weights_sol = None
        self.path_slacks_sol = None
        self.path_slacks_scaled_sol = None
        self.__solution = None
        self.__lowerbound_k = None

        self.solve_statistics = {}

        self.optimization_options = optimization_options or {}
        self.optimization_options["trusted_edges_for_safety"] = self.G.get_non_zero_flow_edges(
            flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
        ).difference(self.edges_to_ignore)
        
        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            k, 
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            edge_length_attr=self.edge_length_attr,
            encode_edge_position=True,
            encode_path_length=True,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics,
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class 
        self.__encode_minpatherror_decomposition()

        # This method is called from the current class to add the objective function
        self.__encode_objective()

    def __encode_minpatherror_decomposition(self):

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
        # assuming self.w_max is a bound for self.path_wslacks_vars[(i)]
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

    def __encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(self.path_slacks_vars[(i)] for i in range(self.k)), sense="minimize"
        )

    def get_solution(self):
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

        if self.__solution is not None:
            return self.__solution

        self.check_is_solved()

        weights_sol_dict = self.solver.get_variable_values("weights", [int])
        self.path_weights_sol = [
            (
                round(weights_sol_dict[i])
                if self.weight_type == int
                else float(weights_sol_dict[i])
            )
            for i in range(self.k)
        ]
        slacks_sol_dict = self.solver.get_variable_values("slack", [int])
        self.path_slacks_sol = [
            (
                round(slacks_sol_dict[i])
                if self.weight_type == int
                else float(slacks_sol_dict[i])
            )
            for i in range(self.k)
        ]

        self.__solution = {
            "paths": self.get_solution_paths(),
            "weights": self.path_weights_sol,
            "slacks": self.path_slacks_sol
        }

        if len(self.path_length_factors) > 0:
            slacks_scaled_sol_dict = self.solver.get_variable_values("scaled_slack", index_types=[int])
            self.path_slacks_scaled_sol = [slacks_scaled_sol_dict[i] for i in range(self.k)]

            self.__solution["scaled_slacks"] = self.path_slacks_scaled_sol

        return self.__solution

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

        if self.__solution is None:
            self.get_solution()

        solution_paths = self.__solution["paths"]
        solution_weights = self.__solution["weights"]
        solution_slacks = self.__solution["slacks"]
        if len(self.path_length_factors) > 0:
            solution_slacks = self.__solution["scaled_slacks"]
        solution_paths_of_edges = [
            [(path[i], path[i + 1]) for i in range(len(path) - 1)]
            for path in solution_paths
        ]

        weight_from_paths = {(u, v): 0 for (u, v) in self.G.edges()}
        slack_from_paths = {(u, v): 0 for (u, v) in self.G.edges()}
        num_paths_on_edges = {e: 0 for e in self.G.edges()}
        for weight, slack, path in zip(
            solution_weights, solution_slacks, solution_paths_of_edges
        ):
            for e in path:
                weight_from_paths[e] += weight
                slack_from_paths[e] += slack
                num_paths_on_edges[e] += 1

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u,v) not in self.edges_to_ignore:
                if (
                    abs(data[self.flow_attr] - weight_from_paths[(u, v)])
                    > tolerance * num_paths_on_edges[(u, v)] + slack_from_paths[(u, v)]
                ):
                    # print(self.solution)
                    # print("num_paths_on_edges[(u, v)]", num_paths_on_edges[(u, v)])
                    # print("slack_from_paths[(u, v)]", slack_from_paths[(u, v)])
                    # print("data[self.flow_attr] = ", data[self.flow_attr])
                    # print(f"weight_from_paths[({u}, {v})]) = ", weight_from_paths[(u, v)])
                    # print("> ", tolerance * num_paths_on_edges[(u, v)] + slack_from_paths[(u, v)])

                    # var_dict = {var: val for var, val in zip(self.solver.get_all_variable_names(),self.solver.get_all_variable_values())}
                    # print(var_dict)

                    # return False
                    pass

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.k:
            print("self.get_objective_value()", self.get_objective_value())
            print("self.solver.get_objective_value()", self.solver.get_objective_value())
            return False
        
        # Checking that the error scale factor is correctly encoded
        if len(self.path_length_factors) > 0:
            path_length_sol = self.solver.get_variable_values("path_length", [int])
            slack_sol = self.solver.get_variable_values("slack", [int])
            path_slack_scaled_sol = self.solver.get_variable_values("path_slack_scaled", [int])
            scaled_slack_sol = self.solver.get_variable_values("scaled_slack", [int])
            
            for i in range(self.k):
                # Checking which interval the path length is in,
                # and then checking if the error scale factor is correctly encoded, 
                for index, interval in enumerate(self.path_length_ranges):
                    if path_length_sol[i] >= interval[0] and path_length_sol[i] <= interval[1]:
                        if abs(path_slack_scaled_sol[i] - self.path_length_factors[index]) > tolerance:
                            print("path_length_sol", path_length_sol)
                            print("slack_sol", slack_sol)
                            print("path_slack_scaled_sol", path_slack_scaled_sol)
                            print("scaled_slack_sol", scaled_slack_sol)

                            return False

        if not self.verify_edge_position():
            return False
        
        if not self.verify_path_length():
            return False

        # var_dict = {var: val for var, val in zip(self.solver.get_all_variable_names(),self.solver.get_all_variable_values())}
        # print(var_dict)
        # self.solver.write_model("kminpatherror.lp")

        # gamma_sol = self.solver.get_variable_values("gamma", [str, str, int])
        # pi_sol = self.solver.get_variable_values("pi", [str, str, int])

        # print("pi_sol", pi_sol)
        # print("gamma_sol", gamma_sol)

        return True

    def get_objective_value(self):

        self.check_is_solved()

        if self.__solution is None:
            self.get_solution()

        # sum of slacks
        return sum(self.__solution["slacks"])
    
    def get_lowerbound_k(self):

        if self.__lowerbound_k != None:
            return self.__lowerbound_k

        weight_function = dict()
        for e in self.G.edges():
            if e not in self.edges_to_ignore:
                weight_function[e] = 1

        self.__lowerbound_k = self.G.compute_max_edge_antichain(get_antichain=False, weight_function=weight_function)

        return self.__lowerbound_k