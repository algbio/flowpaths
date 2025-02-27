import time
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.utils.graphutils as gu
import flowpaths.abstractpathmodeldag as pathmodel


class kFlowDecomp(pathmodel.AbstractPathModelDAG):
    """
    Class to decompose a flow into a given number of weighted paths.
    """
    # storing some defaults
    optimize_with_greedy = True

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
        optimization_options: dict = None,
        solver_options: dict = None,
    ):
        """
        Initialize the Flow Decompostion model for a given number of paths `num_paths`.

        Parameters
        ----------
        - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
        - flow_attr (str): The attribute name from where to get the flow values on the edges.
        - num_paths (int): The number of paths to decompose in.
        - weight_type (type, optional): The type of weights (int or float). Default is float.
        - subpath_constraints (list, optional): List of subpath constraints. Default is an empty list.
        - subpath_constraints_coverage (float, optional): Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            Defaults to 1 (meaning that 100% of the edges of the constraint need to be covered by some solution path).
        - optimize_with_safe_paths (bool, optional): Whether to optimize with safe paths. Default is True.
        - optimize_with_safe_sequences (bool, optional): Whether to optimize with safe sequences. Default is False.
        - optimize_with_safe_zero_edges (bool, optional): Whether to optimize with safe zero edges. Default is False.
        - optimize_with_greedy (bool, optional): Whether to optimize with a greedy algorithm. Default is True.
              If set to True, the model will first try to solve the problem with a greedy algorithm based on
              always removing the path of maximum bottleneck. If the size of such greedy decomposition matches the width of the graph,
              the greedy decomposition is optimal, and the model will return the greedy decomposition as the solution.
              If the greedy decomposition does not match the width, then the model will proceed to solve the problem with the MILP model.
        - threads (int, optional): Number of threads to use. Default is 4.
        - time_limit (int, optional): Time limit for the solver in seconds. Default is 300.
        - presolve (str, optional): Presolve option for the solver. Default is "on".
        - log_to_console (str, optional): Whether to log solver output to console. Default is "false".
        - external_solver (str, optional): External solver to use. Default is "highs".

        Raises
        ----------
        - ValueError: If `weight_type` is not int or float.
        - ValueError: If some edge does not have the flow attribute specified as `flow_attr`.
        - ValueError: If the graph does not satisfy flow conservation on nodes different from source or sink.
        - ValueError: If the graph contains edges with negative (<0) flow values.
        """

        self.G = stdigraph.stDiGraph(G)

        if weight_type not in [int, float]:
            raise ValueError(
                f"weight_type must be either int or float, not {weight_type}"
            )
        self.weight_type = weight_type

        # Check requirements on input graph:
        # Check flow conservation
        if not gu.check_flow_conservation(G, flow_attr):
            raise ValueError("The graph G does not satisfy flow conservation.")

        # Check that the flow is positive and get max flow value
        self.edges_to_ignore = self.G.source_sink_edges
        self.flow_attr = flow_attr
        self.w_max = self.weight_type(
            self.G.get_max_flow_value_and_check_positive_flow(
                flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore
            )
        )

        self.k = num_paths
        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr

        self.pi_vars = {}
        self.path_weights_vars = {}

        self.path_weights_sol = None
        self.__solution = None

        
        self.solve_statistics = {}
        self.optimization_options = optimization_options or {}

        greedy_solution_paths = None
        self.optimize_with_greedy = self.optimization_options.get("optimize_with_greedy", kFlowDecomp.optimize_with_greedy)
        if self.optimize_with_greedy:
            if self.get_solution_with_greedy():
                greedy_solution_paths = self.__solution[0]
                self.optimization_options["external_solution_paths"] = greedy_solution_paths
        self.optimization_options["trusted_edges_for_safety"] = self.G.get_non_zero_flow_edges(flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore)

        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            num_paths, 
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            edge_length_attr=self.edge_length_attr, 
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics,
        )

        # If already solved with a previous method, we don't create solver, not add paths
        if self.is_solved():
            return

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class to encode the flow decomposition
        self.encode_flow_decomposition()

    def encode_flow_decomposition(self):
        """
        Encodes the flow decomposition constraints for the given graph.
        This method sets up the path weight variables and the edge variables encoding
        the sum of the weights of the paths going through the edge.

        The method performs the following steps:
        1. Checks if the problem is already solved to avoid redundant encoding.
        2. Initializes the sum of path weights variables (`pi_vars`) and path weight variables (`path_weights_vars`).
        3. Iterates over each edge in the graph and adds constraints to ensure:

        Returns
        -------
        - None
        """

        # If already solved, no need to encode further
        if self.is_solved():
            return

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
            name_prefix="w",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )

        # We encode that for each edge (u,v), the sum of the weights of the paths going through the edge is equal to the flow value of the edge.
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

            self.solver.add_constraint(
                sum(self.pi_vars[(u, v, i)] for i in range(self.k)) == f_u_v,
                name=f"10d_u={u}_v={v}_i={i}",
            )

    def get_solution_with_greedy(self):
        """
        Attempts to find a solution using a greedy algorithm.
        This method first decomposes the problem using the maximum bottleneck approach.
        If the number of paths obtained is less than or equal to the specified limit `k`,
        it sets the solution and marks the problem as solved. It also records the time
        taken to solve the problem using the greedy approach.

        Returns
        -------
        - bool: True if a solution is found using the greedy algorithm, False otherwise.
        """

        start_time = time.time()
        (paths, weights) = self.G.decompose_using_max_bottleck(self.flow_attr)

        # Check if the greedy decomposition satisfies the subpath contraints
        if self.subpath_constraints:
            for subpath in self.subpath_constraints:
                if self.subpath_constraints_coverage_length is None:
                    # By default, the length of the constraints is its number of edges 
                    constraint_length = len(subpath)
                    # And the fraction of edges that we need to cover is self.subpath_constraints_coverage
                    coverage_fraction = self.subpath_constraints_coverage
                else:
                    constraint_length = sum(self.G[u][v].get(self.edge_length_attr, 1) for (u,v) in subpath)
                    coverage_fraction = self.subpath_constraints_coverage_length
                # If the subpath is not covered enough by the greedy decomposition, we return False
                if gu.max_occurrence(subpath, paths, edge_lengths={(u,v): self.G[u][v].get(self.edge_length_attr, 1) for (u,v) in subpath}) < constraint_length * coverage_fraction:
                    return False
            
        if len(paths) <= self.k:
            self.__solution = (paths, weights)
            self.set_solved()
            self.solve_statistics = {}
            self.solve_statistics["greedy_solve_time"] = time.time() - start_time
            return True

        return False

    def get_solution(self):
        """
        Retrieves the solution for the flow decomposition problem.

        If the solution has already been computed and cached as `self.solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution paths and weights,
        and caches the solution.

        Returns
        -------
        - tuple: A tuple containing the solution paths and their corresponding weights.

        Raises:
        - AssertionError: If the solution returned by the MILP solver is not a valid flow decomposition.
        """

        if self.__solution is not None:
            return self.__solution

        self.check_is_solved()
        weights_sol_dict = self.solver.get_variable_values("w", [int])
        self.path_weights_sol = [
            (
                round(weights_sol_dict[i])
                if self.weight_type == int
                else float(weights_sol_dict[i])
            )
            for i in range(self.k)
        ]

        self.__solution = (self.get_solution_paths(), self.path_weights_sol)

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
            raise ValueError("Solution is not available. Call get_solution() first.")

        solution_paths = self.__solution[0]
        solution_weights = self.__solution[1]
        solution_paths_of_edges = [
            [(path[i], path[i + 1]) for i in range(len(path) - 1)]
            for path in solution_paths
        ]

        flow_from_paths = {(u, v): 0 for (u, v) in self.G.edges()}
        num_paths_on_edges = {e: 0 for e in self.G.edges()}
        for weight, path in zip(solution_weights, solution_paths_of_edges):
            for e in path:
                flow_from_paths[e] += weight
                num_paths_on_edges[e] += 1

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u,v) not in self.edges_to_ignore:
                if (
                    abs(flow_from_paths[(u, v)] - data[self.flow_attr])
                    > tolerance * num_paths_on_edges[(u, v)]
                ):
                    return False

        return True
    
    def get_objective_value(self):
        
        self.check_is_solved()

        return self.num_paths
