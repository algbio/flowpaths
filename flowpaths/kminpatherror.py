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
        num_paths: int,
        weight_type: type = float,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        edge_length_attr: str = None,
        edges_to_ignore: list = [],
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
        - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
        - flow_attr (str): The attribute name from where to get the flow values on the edges.
        - num_paths (int): The number of paths to decompose in.
        - weight_type (type, optional): The type of the weights and slacks (int or float). Default is float.
        - subpath_constraints (list, optional): List of subpath constraints. Default is an empty list.
        - subpath_constraints_coverage (float, optional): Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            Defaults to 1 (meaning that 100% of the edges of the constraint need to be covered by some solution path).
        - edges_to_ignore (list, optional): List of edges to ignore when adding constrains on flow explanation by the weighted paths and their slack. Default is an empty list.
        - path_length_ranges (list, optional): List of ranges for the path lengths. Default is an empty list.
        - error_scale_factor (list, optional): List of error scale factors, which scale the allowed difference between edge weight and path weights. Default is an empty list.
        - additional_starts (list, optional): List of additional start nodes of the paths. Default is an empty list.
        - additional_ends (list, optional): List of additional end nodes of the paths. Default is an empty list.
        - optimize_with_safe_paths (bool, optional): Whether to optimize with safe paths. Default is True.
        - optimize_with_safe_sequences (bool, optional): Whether to optimize with safe sequences. Default is False.
        - optimize_with_safe_zero_edges (bool, optional): Whether to optimize with safe zero edges. Default is False.
        - threads (int, optional): Number of threads to use. Default is 4.
        - time_limit (int, optional): Time limit for the solver in seconds. Default is 300.
        - presolve (str, optional): Presolve option for the solver. Default is "on".
        - log_to_console (str, optional): Whether to log solver output to console. Default is "false".
        - external_solver (str, optional): External solver to use. Default is "highs".

        Raises
        ----------
        - ValueError: If `weight_type` is not int or float.
        - ValueError: If some edge does not have the flow attribute specified as `flow_attr`.
        - ValueError: If the graph contains edges with negative (<0) flow values.
        """

        self.G = stdigraph.stDiGraph(G, additional_starts=additional_starts, additional_ends=additional_ends)

        if weight_type not in [int, float]:
            raise ValueError(
                f"weight_type must be either int or float, not {weight_type}"
            )
        self.weight_type = weight_type

        self.edges_to_ignore = set(edges_to_ignore).union(self.G.source_sink_edges)

        self.flow_attr = flow_attr
        self.w_max = num_paths * self.weight_type(
            self.G.get_max_flow_value_and_check_positive_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )

        self.k = num_paths
        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr
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

        self.solve_statistics = {}

        self.optimization_options = optimization_options or {}
        self.optimization_options["trusted_edges_for_safety"] = self.G.get_non_zero_flow_edges(
            flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
        ).difference(self.edges_to_ignore)
        
        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            num_paths, 
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
        self.encode_minpatherror_decomposition()

        # This method is called from the current class to add the objective function
        self.encode_objective()

    def encode_minpatherror_decomposition(self):
        """
        Encodes the minimum path error decomposition variables and constraints for the optimization problem.
        """

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

            # We encode that abs(f_u_v - sum(self.pi_vars[(u, v, i)] for i in range(self.k))) <= sum(self.gamma_vars[(u, v, i)] for i in range(self.k))
            self.solver.add_constraint(
                f_u_v - sum(self.pi_vars[(u, v, i)] for i in range(self.k))
                <= sum(self.gamma_vars[(u, v, i)] for i in range(self.k)),
                name=f"9aa_u={u}_v={v}_i={i}",
            )
            self.solver.add_constraint(
                f_u_v - sum(self.pi_vars[(u, v, i)] for i in range(self.k))
                >= -sum(self.gamma_vars[(u, v, i)] for i in range(self.k)),
                name=f"9ab_u={u}_v={v}_i={i}",
            )

    def encode_objective(self):

        self.solver.set_objective(
            sum(self.path_slacks_vars[(i)] for i in range(self.k)), sense="minimize"
        )

    def get_solution(self):
        """
        Retrieves the solution for the flow decomposition problem.

        If the solution has already been computed and cached as `self.solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution paths, weights, slacks
        and caches the solution.

        Returns
        -------
        - tuple: A tuple containing
            - the list ofsolution paths, 
            - the list of their corresponding weights, 
            - the list of their corresponding slacks.
            - the list of their corresponding scaled slacks (if path_error_scale_factors is not empty); continuous values

        Raises:
        - AssertionError: If the solution returned by the MILP solver is not a valid flow decomposition.
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

        self.__solution = (
            self.get_solution_paths(),
            self.path_weights_sol,
            self.path_slacks_sol,
        )

        if len(self.path_length_factors) > 0:
            slacks_scaled_sol_dict = self.solver.get_variable_values("scaled_slack", index_types=[int])
            self.path_slacks_scaled_sol = [slacks_scaled_sol_dict[i] for i in range(self.k)]

            self.__solution = (
                self.get_solution_paths(),
                self.path_weights_sol,
                self.path_slacks_sol,
                self.path_slacks_scaled_sol
            )

        return self.__solution

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
        - get_solution() must be called before this method.
        - The solution is considered valid if the flow from paths is equal
            (up to `TOLERANCE * num_paths_on_edges[(u, v)]`) to the flow value of the graph edges.
        """

        if self.__solution is None:
            self.get_solution()

        solution_paths = self.__solution[0]
        solution_weights = self.__solution[1]
        solution_slacks = self.__solution[2]
        if len(self.path_length_factors) > 0:
            solution_slacks = self.__solution[3]
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
                # within tolerance to self.error_scale_factor[index]
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

        # sum of slacks
        return sum(self.__solution[2])