import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.abstractpathmodeldag as pathmodel


class kLeastAbsErrors(pathmodel.AbstractPathModelDAG):
    """
    This class implements the k-LeastAbsoluteErrors, namely it looks for a decomposition of a weighted DAG into 
    k weighted paths (specified by `num_paths`), minimizing the absolute errors on the edges. The error on an edge 
    is defiened as the absolute value of the difference between the weight of the edge and the sum of the weights of 
    the paths that go through it.
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
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = None,
        solver_options: dict = None,
        trusted_edges_for_safety: list = None,
    ):
        """
        Initialize the Least Absolute Errors model for a given number of paths.

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
            
            List of edges to ignore when adding constrains on flow explanation by the weighted paths.
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `edge_error_scaling: dict`, optional
            
            Dictionary `edge: factor` storing the error scale factor (in [0,1]) of every edge, which scale the allowed difference between edge weight and path weights.
            Default is an empty dict. If an edge has a missing error scale factor, it is assumed to be 1. The factors are used to scale the 
            difference between the flow value of the edge and the sum of the weights of the paths going through the edge.
        
        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list.

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

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
        """

        self.G = stdigraph.stDiGraph(G, additional_starts=additional_starts, additional_ends=additional_ends)

        if weight_type not in [int, float]:
            raise ValueError(
                f"weight_type must be either int or float, not {weight_type}"
            )
        self.weight_type = weight_type

        self.edges_to_ignore = set(edges_to_ignore).union(self.G.source_sink_edges)
        # Checking that every entry in self.edge_error_scaling is between 0 and 1
        self.edge_error_scaling = edge_error_scaling
        for key, value in self.edge_error_scaling.items():
            if value < 0 or value > 1:
                raise ValueError(f"Edge error scaling factor for edge {key} must be between 0 and 1.")

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
        

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.edge_errors_vars = {}

        self.path_weights_sol = None
        self.edge_errors_sol = None
        self.__solution = None
        self.__lowerbound_k = None

        self.solve_statistics = {}

        self.optimization_options = optimization_options or {}        
        
        # If we get subpath constraints, and the coverage fraction is 1
        # then we know their edges must appear in the solution, so we add their edges to the trusted edges for safety
        self.optimization_options["trusted_edges_for_safety"] = set(trusted_edges_for_safety or [])
        if self.subpath_constraints is not None:
            if (self.subpath_constraints_coverage == 1.0 and self.subpath_constraints_coverage_length is None) \
                or self.subpath_constraints_coverage_length == 1:
                for constraint in self.subpath_constraints:
                    self.optimization_options["trusted_edges_for_safety"].update(constraint)


        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            self.G, 
            k, 
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            edge_length_attr=self.edge_length_attr,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class 
        self.__encode_leastabserrors_decomposition()

        # This method is called from the current class to add the objective function
        self.__encode_objective()

    def __encode_leastabserrors_decomposition(self):

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
            name_prefix="errorofedge",
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
                name=f"9aa_u={u}_v={v}_i={i}",
            )

    def __encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(
                self.edge_errors_vars[(u, v)] 
                * self.edge_error_scaling.get((u, v), 1)
                for (u,v) in self.edge_indexes_basic), 
            sense="minimize"
        )

    def get_solution(self):
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
        self.edge_errors_sol = self.solver.get_variable_values("errorofedge", [str, str])
        print("self.edge_errors_sol", self.edge_errors_sol)
        for (u,v) in self.edge_indexes_basic:
            self.edge_errors_sol[(u,v)] = round(self.edge_errors_sol[(u,v)]) if self.weight_type == int else float(self.edge_errors_sol[(u,v)])

        self.__solution = {
            "paths": self.get_solution_paths(),
            "weights": self.path_weights_sol,
            "edge_errors": self.edge_errors_sol # This is a dictionary with keys (u,v) and values the error on the edge (u,v)
        }

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
        - `get_solution()` must be called before this method.
        - The solution is considered valid if the flow from paths is equal
            (up to `TOLERANCE * num_paths_on_edges[(u, v)]`) to the flow value of the graph edges.
        """

        if self.__solution is None:
            self.get_solution()

        solution_paths = self.__solution["paths"]
        solution_weights = self.__solution["weights"]
        solution_errors = self.__solution["edge_errors"]
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
                    > tolerance * num_paths_on_edges[(u, v)] + solution_errors[(u, v)]
                ):
                    return False

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.k:
            return False

        return True

    def get_objective_value(self):

        self.check_is_solved()

        # sum of edge errors
        return sum(self.edge_errors_sol[(u, v)] for (u,v) in self.edge_indexes_basic)
    
    def get_lowerbound_k(self):

        return 1