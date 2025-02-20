import time
import networkx as nx
import stdigraph
import utils.graphutils as gu
import genericpathmodeldag as pathmodel

class kFlowDecomp(pathmodel.GenericPathModelDAG):

    def __init__(self, G: nx.DiGraph, flow_attr: str, num_paths: int, weight_type: type = float, subpath_constraints: list = [], **kwargs):
        """
        Initialize the Flow Decompostion model for a given number of paths.

        Parameters
        ----------
        - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
        - flow_attr (str): The attribute name from where to get the flow values on the edges.
        - num_paths (int): The number of paths to decompose in.
        - weight_type (type, optional): The type of weights (int or float). Default is float.
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
        - ValueError: If the graph does not satisfy flow conservation on nodes different from source or sink.
        - ValueError: If the graph contains edges with negative (<0) flow values.
        """

        self.G = stdigraph.stDiGraph(G)

        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        # Check requirements on input graph:
        # Check flow conservation
        if not gu.check_flow_conservation(G, flow_attr):
            raise ValueError("The graph G does not satisfy flow conservation.")

        # Check that the flow is positive and get max flow value
        self.edges_to_ignore = set(self.G.source_edges)
        self.edges_to_ignore.update(self.G.sink_edges)
        self.flow_attr = flow_attr
        self.w_max = self.weight_type(self.G.get_max_flow_value_and_check_positive_flow(flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore))
    
        self.k = num_paths
        self.subpath_constraints = subpath_constraints

        self.pi_vars = {}
        self.path_weights_vars = {}
    
        self.path_weights_sol = None
        self.solution = None

        greedy_solution_paths = None
        self.solve_statistics = {}
        self.optimize_with_greedy = kwargs.get('optimize_with_greedy', True)
        if self.optimize_with_greedy:
            if self.get_solution_with_greedy():
                greedy_solution_paths = self.solution[0]

        # Call the constructor of the parent class genericDagModel
        kwargs["trusted_edges_for_safety"] = self.G.get_non_zero_flow_edges(flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore)
        kwargs["solve_statistics"] = self.solve_statistics
        kwargs["external_solution_paths"] = greedy_solution_paths
        super().__init__(self.G, num_paths, subpath_constraints = self.subpath_constraints, **kwargs)
        
        # If already solved with a previous method, we don't create solver, not add paths
        if self.solved:
            return

        # This method is called from the super class genericDagModel
        self.create_solver_and_paths()

        # This method is called from the current class modelMFD
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
        if self.solved:
            return
        
        # pi vars from https://arxiv.org/pdf/2201.10923 page 14
        self.pi_vars            = self.solver.add_variables(self.edge_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='p')
        self.path_weights_vars  = self.solver.add_variables(self.path_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='w')


        # We encode that for each edge (u,v), the sum of the weights of the paths going through the edge is equal to the flow value of the edge.
        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            f_u_v = data[self.flow_attr]

            # We encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)], 
            # assuming self.w_max is a bound for self.path_weights_vars[(i)]
            for i in range(self.k):
                self.solver.add_product_constraint(binary_var  = self.edge_vars[(u,v,i)],
                                                   product_var = self.path_weights_vars[(i)], 
                                                   equal_var   = self.pi_vars[(u,v,i)],
                                                   bound       = self.w_max, 
                                                   name        = "10_u={}_v={}_i={}".format(u,v,i))

            self.solver.add_constraint(sum(self.pi_vars[(u,v,i)] for i in range(self.k)) == f_u_v, name="10d_u={}_v={}_i={}".format(u,v,i))
   
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
        if len(paths) <= self.k:
            self.solution = (paths, weights)
            self.solved = True
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

        if self.solution is not None:
            return self.solution

        self.check_solved()
        weights_sol_dict = self.solver.get_variable_values('w', [int])
        self.path_weights_sol = [abs(round(weights_sol_dict[i])) if self.weight_type == int else abs(float(weights_sol_dict[i])) for i in range(self.k)]

        self.solution = (self.get_solution_paths(), self.path_weights_sol)

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
        solution_paths_of_edges = [[(path[i],path[i+1]) for i in range(len(path)-1)] for path in solution_paths]

        flow_from_paths = {(u,v):0 for (u,v) in self.G.edges()}
        num_paths_on_edges = {e:0 for e in self.G.edges()}
        for weight, path in zip(solution_weights, solution_paths_of_edges):
            for e in path:
                flow_from_paths[e] += weight
                num_paths_on_edges[e] += 1

        for (u, v, data) in self.G.edges(data=True):
            if self.flow_attr in data:
                if flow_from_paths[(u, v)] - data[self.flow_attr] > tolerance * num_paths_on_edges[(u, v)]: 
                    return False

        return True
    


    def draw_solution(self, show_flow_attr=True):

        import graphviz as gv

        self.check_solved()

        dot = gv.Digraph(format='pdf')
        dot.graph_attr['rankdir'] = 'LR'        # Display the graph in landscape mode
        dot.node_attr['shape']    = 'rectangle' # Rectangle nodes

        colors = ['red','blue','green','purple','brown','cyan','yellow','pink','grey']

        for u,v,data in self.G.edges(data=True):
            if u == self.G.source or v == self.G.sink:
                continue
            if show_flow_attr and data[self.flow_attr] != None:
                dot.edge(str(u),str(v),str(data[self.flow_attr]))
            else:
                dot.edge(str(u),str(v))

        solution_paths,solution_weights = self.get_solution()

        for path in solution_paths:
            pathColor = colors[len(path)+73 % len(colors)]
            for i in range(len(path)-1):
                dot.edge(str(path[i]), str(path[i+1]), fontcolor=pathColor, color=pathColor, penwidth='2.0') #label=str(weight)
            if len(path) == 1:
                dot.node(str(path[0]), color=pathColor, penwidth='2.0')
            
   