import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.genericpathmodeldag as pathmodel


class kMinPathError(pathmodel.GenericPathModelDAG):

    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        num_paths: int,
        weight_type: type = float,
        subpath_constraints: list = [],
        edges_to_ignore: list = [],
        **kwargs,
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
        - edges_to_ignore (list, optional): List of edges to ignore when adding constrains on flow explanation by the weighted paths and their slack. Default is an empty list.
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

        self.G = stdigraph.stDiGraph(G)

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
        self.kwargs = kwargs

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.path_slacks_vars = {}

        self.path_weights_sol = None
        self.path_slacks_sol = None
        self.solution = None

        self.solve_statistics = {}

        # Call the constructor of the parent class GenericPathModelDAG
        kwargs["trusted_edges_for_safety"] = self.G.get_non_zero_flow_edges(
            flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
        ).difference(self.edges_to_ignore)
        kwargs["solve_statistics"] = self.solve_statistics
        super().__init__(
            self.G, num_paths, subpath_constraints=self.subpath_constraints, encode_edge_position=True, **kwargs
        )

        # This method is called from the super class GenericPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class 
        self.encode_minpatherror_decomposition()

        # This method is called from the current class to add the objective function
        self.encode_objective()

    def encode_minpatherror_decomposition(self):
        """
        Encodes the minimum path error decomposition variables and constraints for the optimization problem.
        """
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

        # gamma vars from https://helda.helsinki.fi/server/api/core/bitstreams/96693568-d973-4b43-a68f-bc796bbeb225/content
        self.gamma_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="gamma",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        self.path_slacks_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="slack",
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
                self.solver.add_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    product_var=self.path_weights_vars[(i)],
                    equal_var=self.pi_vars[(u, v, i)],
                    bound=self.w_max,
                    name=f"10_u={u}_v={v}_i={i}",
                )

            # We encode that edge_vars[(u,v,i)] * self.path_slacks_vars[(i)] = self.gamma_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_slacks_vars[(i)]
            for i in range(self.k):
                self.solver.add_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    product_var=self.path_slacks_vars[(i)],
                    equal_var=self.gamma_vars[(u, v, i)],
                    bound=self.w_max,
                    name=f"12_u={u}_v={v}_i={i}",
                )

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
        - tuple: A tuple containing the solution paths, their corresponding weights, and their corresponding slacks.

        Raises:
        - AssertionError: If the solution returned by the MILP solver is not a valid flow decomposition.
        """

        if self.solution is not None:
            return self.solution

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

        self.solution = (
            self.get_solution_paths(),
            self.path_weights_sol,
            self.path_slacks_sol,
        )

        return self.solution

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

        if self.solution is None:
            self.get_solution()

        solution_paths = self.solution[0]
        solution_weights = self.solution[1]
        solution_slacks = self.solution[2]
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

                    var_dict = {var: val for var, val in zip(self.solver.get_all_variable_names(),self.solver.get_all_variable_values())}
                    # print(var_dict)
                    return False

        return True

    def get_objective_value(self):

        self.check_is_solved()

        # sum of slacks
        return sum(self.solution[2])