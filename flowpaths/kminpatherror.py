import time
import networkx as nx
import stdigraph
import genericdagmodel as dagmodel
import graphviz as gv

class kMinPathError(dagmodel.GenericDAGModel):

    def __init__(self, G: nx.DiGraph, flow_attr: str, num_paths: int, weight_type: type = float, subpath_constraints: list = [], edges_to_ignore: list = [], **kwargs):
        """
        Initialize the Min Path Error model for a given number of paths.

        Parameters
        ----------
        - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
        - flow_attr (str): The attribute name from where to get the flow values on the edges.
        - num_paths (int): The number of paths to decompose in.
        - weight_type (type, optional): The type of weights (int or float). Default is int.
        - subpath_constraints (list, optional): List of subpath constraints. Default is an empty list.
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
        - ValueError: If the graph contains edges with negative (<0) flow values.
        """

        self.G = stdigraph.stDiGraph(G)

        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        self.edges_to_ignore = set(edges_to_ignore)
        self.edges_to_ignore.update(self.G.source_edges)
        self.edges_to_ignore.update(self.G.sink_edges)
        self.flow_attr = flow_attr
        self.w_max = num_paths * self.weight_type(self.get_max_flow_value_and_check_positive_flow())
    
        self.k = num_paths
        self.subpath_constraints = subpath_constraints

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.path_slacks_vars = {}
    
        self.path_weights_sol = None
        self.path_slacks_sol = None
        self.solution = None

        self.solve_statistics = {}

        # Call the constructor of the parent class genericDagModel
        kwargs["trusted_edges_for_safety"] = self.get_non_zero_flow_edges().difference(self.edges_to_ignore)
        kwargs["solve_statistics"] = self.solve_statistics
        super().__init__(self.G, num_paths, subpath_constraints = self.subpath_constraints, **kwargs)

        # This method is called from the super class genericDagModel
        self.create_solver_and_paths()

        # This method is called from the current class
        self.encode_minpatherror_decomposition()

        # This method is called from the current class to add the objective function
        self.encode_objective()

    def get_max_flow_value_and_check_positive_flow(self):
        """
        Determines the maximum flow value in the graph and checks for positive flow values.

        This method iterates over all edges in the graph, ignoring edges specified in 
        `self.edges_to_ignore`. It checks if each edge has the required flow attribute 
        specified by `self.flow_attr`. If an edge does not have this attribute, a 
        ValueError is raised. If an edge has a negative flow value, a ValueError is 
        raised. The method returns the maximum flow value found among all edges.

        Returns
        -------
        - float: The maximum flow value among all edges in the graph.

        Raises
        -------
        - ValueError: If an edge does not have the required flow attribute.
        - ValueError: If an edge has a negative flow value.
        """

        w_max = float('-inf')   

        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            if not self.flow_attr in data:
                raise ValueError(f"Edge ({u},{v}) does not have the required flow attribute '{self.flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data.")
            if data[self.flow_attr] < 0:
                raise ValueError(f"Edge ({u},{v}) has negative flow value {data[self.flow_attr]}. All flow values must be >=0.")
            w_max = max(w_max, data[self.flow_attr])

        return w_max

    def get_non_zero_flow_edges(self):
        """
        Get all edges with non-zero flow values.

        Returns
        -------
        set
            A set of edges (tuples) that have non-zero flow values.
        """
        
        non_zero_flow_edges = set()
        for u, v, data in self.G.edges(data=True):
            if (u,v) not in self.edges_to_ignore and data.get(self.flow_attr, 0) != 0:
                non_zero_flow_edges.add((u,v))

        return non_zero_flow_edges

    def encode_minpatherror_decomposition(self):
        """
        Encodes the minimum path error decomposition variables and constraints for the optimization problem.
        """
        
        self.pi_vars            = self.solver.add_variables(self.edge_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='p')
        self.path_weights_vars  = self.solver.add_variables(self.path_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='w')
        self.gamma_vars         = self.solver.add_variables(self.edge_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='g')
        self.path_slacks_vars    = self.solver.add_variables(self.path_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='s')

        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            
            f_u_v = data[self.flow_attr]

            for i in range(self.k):
                self.solver.add_constraint(self.pi_vars[(u,v,i)] <= self.edge_vars[(u,v,i)] * self.w_max,                                     name="10e_u={}_v={}_i={}".format(u,v,i))
                self.solver.add_constraint(self.pi_vars[(u,v,i)] <= self.path_weights_vars[(i)],                                              name="10f_u={}_v={}_i={}".format(u,v,i))
                self.solver.add_constraint(self.pi_vars[(u,v,i)] >= self.path_weights_vars[(i)] - (1 - self.edge_vars[(u,v,i)]) * self.w_max, name="10g_u={}_v={}_i={}".format(u,v,i))

            # gamma varts from https://helda.helsinki.fi/server/api/core/bitstreams/96693568-d973-4b43-a68f-bc796bbeb225/content 

            for i in range(self.k):
                self.solver.add_constraint(self.gamma_vars[(u,v,i)] <= self.edge_vars[(u,v,i)] * self.w_max,                                    name="12a_u={}_v={}_i={}".format(u,v,i))
                self.solver.add_constraint(self.gamma_vars[(u,v,i)] <= self.path_slacks_vars[(i)],                                              name="12b_u={}_v={}_i={}".format(u,v,i))
                self.solver.add_constraint(self.gamma_vars[(u,v,i)] >= self.path_slacks_vars[(i)] - (1 - self.edge_vars[(u,v,i)]) * self.w_max, name="12c_u={}_v={}_i={}".format(u,v,i))

            self.solver.add_constraint(f_u_v - sum(self.pi_vars[(u,v,i)] for i in range(self.k)) <=  sum(self.gamma_vars[(u,v,i)] for i in range(self.k)), name="9a_u={}_v={}_i={}".format(u,v,i))
            self.solver.add_constraint(f_u_v - sum(self.pi_vars[(u,v,i)] for i in range(self.k)) >= -sum(self.gamma_vars[(u,v,i)] for i in range(self.k)), name="9a_u={}_v={}_i={}".format(u,v,i))

    def encode_objective(self):

        self.solver.set_objective(sum(self.path_slacks_vars[(i)] for i in range(self.k)), sense='minimize')

    def __get_solution_weights_and_slacks(self) -> list:
        """
        Retrieves the solution weights from the solver and returns them as a list.
        This method first checks if the solver has been solved using the `check_solved` method.
        It then retrieves the variable names and values from the solver. For each variable that
        represents a weight (indicated by the variable name starting with 'w'), it extracts the
        weight index and assigns the corresponding value to the `path_weights_sol` list. The
        values are rounded if the weight type is `int`, and converted to float if the weight type
        is `float`. 
        
        The above is repeated for the slack variables, and the values are assigned to the
        `path_slacks_sol` list. 

        Returns
        -------
        - tuple (list, list): A tuple of lists of path weights, and of path slacks.
        """

        self.check_solved()
        
        varNames = self.solver.get_variable_names()
        varValues = self.solver.get_variable_values()
        self.path_weights_sol = [0]*len(range(0,self.k))
        self.path_slacks_sol  = [0]*len(range(0,self.k))

        for var, value in zip(varNames, varValues):
            if var[0] == 'w':
                path_index = int(var[1:].strip())
                self.path_weights_sol[path_index] = round(value) if self.weight_type == int else float(value)
            elif var[0] == 's':
                path_index = int(var[1:].strip())
                self.path_slacks_sol[path_index] = round(value) if self.weight_type == int else float(value)

        return self.path_weights_sol, self.path_slacks_sol
    
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

        if self.solution is not None:
            return self.solution

        self.check_solved()
        weights, slacks = self.__get_solution_weights_and_slacks()

        self.solution = (self.get_solution_paths(), weights, slacks)

        return self.solution
    
    def check_solution(self, tolerance = 0.001):
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
            raise ValueError("Solution is not available. Call get_solution() first.")

        solution_paths = self.solution[0]
        solution_weights = self.solution[1]
        solution_slacks = self.solution[2]
        solution_paths_of_edges = [[(path[i],path[i+1]) for i in range(len(path)-1)] for path in solution_paths]

        weight_from_paths = {(u,v):0 for (u,v) in self.G.edges()}
        slack_from_paths = {(u,v):0 for (u,v) in self.G.edges()}
        num_paths_on_edges = {e:0 for e in self.G.edges()}
        for weight, slack, path in zip(solution_weights, solution_slacks, solution_paths_of_edges):
            for e in path:
                weight_from_paths[e] += weight
                slack_from_paths[e] += slack
                num_paths_on_edges[e] += 1

        for (u, v, data) in self.G.edges(data=True):
            if self.flow_attr in data:
                if abs(data[self.flow_attr] - weight_from_paths[(u, v)]) <= tolerance * num_paths_on_edges[(u, v)] + slack_from_paths[(u, v)]:
                    return False

        return True