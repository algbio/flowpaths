import time
import networkx as nx
import stdigraph
import genericdagmodel as dagmodel

class kFlowDecomp(dagmodel.GenericDAGModel):

    def __init__(self, G: nx.DiGraph, flow_attr: str, num_paths: int, weight_type: type = int, \
                subpath_constraints: list = [], \
                optimize_with_safe_paths: bool = True, \
                optimize_with_safe_sequences: bool = False, \
                optimize_with_safe_zero_edges: bool = False, \
                optimize_with_greedy: bool = True, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false",\
                external_solver = "highs"):
        """
        Initialize the Flow Decompostion model for a given number of paths.

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
        - ValueError: If the graph does not satisfy flow conservation on nodes different from source or sink.
        - ValueError: If the graph contains edges with negative (<0) flow values.
        """

        self.G = stdigraph.stDiGraph(G)

        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        # Check requirements on input graph:
        # Check flow conservation
        if not self.check_flow_conservation(G, flow_attr):
            raise ValueError("The graph G does not satisfy flow conservation.")

        # Check that the flow is positive and get max flow value
        self.edges_to_ignore = set(self.G.source_edges)
        self.edges_to_ignore.update(self.G.sink_edges)
        self.flow_attr = flow_attr
        self.w_max = self.weight_type(self.get_max_flow_value_and_check_positive_flow())
    
        self.k = num_paths
        self.subpath_constraints = subpath_constraints

        self.pi_vars = {}
        self.path_weights_vars = {}
    
        self.path_weights_sol = None
        self.solution = None

        external_solution_paths = None
        self.solve_statistics = {}
        if optimize_with_greedy:
            if self.get_solution_with_greedy():
                external_solution_paths = self.solution[0]

        # Call the constructor of the parent class genericDagModel
        super().__init__(self.G, num_paths, \
                         subpath_constraints = self.subpath_constraints, \
                         optimize_with_safe_paths = optimize_with_safe_paths, \
                         optimize_with_safe_sequences = optimize_with_safe_sequences, \
                         optimize_with_safe_zero_edges = optimize_with_safe_zero_edges, \
                         external_solution_paths = external_solution_paths, \
                         trusted_edges_for_safety = self.get_non_zero_flow_edges(), \
                         solve_statistics = self.solve_statistics, \
                         threads = threads, \
                         time_limit = time_limit, \
                         presolve = presolve, \
                         log_to_console = log_to_console, \
                         external_solver=external_solver)  
        
        # If already solved with a previous method, we don't create solver, not add paths
        if self.solved:
            return

        # This method is called from the super class genericDagModel
        self.create_solver_and_paths()

        # This method is called from the current class modelMFD
        self.encode_flow_decomposition()

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
        (paths, weights) = self.decompose_using_max_bottleck()
        if len(paths) <= self.k:
            self.solution = (paths, weights)
            self.solved = True
            self.solve_statistics = {}
            self.solve_statistics["greedy_solve_time"] = time.time() - start_time
            return True
        
        return False

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
    
    def check_flow_conservation(self, G: nx.DiGraph, flow_attr) -> bool:
        """
        Check if the flow conservation property holds for the given graph.

        Parameters
        ----------
        - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
        - flow_attr (str): The attribute name from where to get the flow values on the edges.

        Returns
        -------
        - bool: True if the flow conservation property holds, False otherwise.
        """
        
        for v in G.nodes():
            if G.out_degree(v) == 0 or G.in_degree(v) == 0:
                continue
            out_flow = sum(flow for _,_,flow in G.out_edges(v, data=flow_attr))
            in_flow  = sum(flow for _,_,flow in G.in_edges(v, data=flow_attr))
            
            if out_flow != in_flow:
                return False
            
        return True

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
        
        self.pi_vars            = self.solver.add_variables(self.edge_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='p')
        self.path_weights_vars  = self.solver.add_variables(self.path_indexes, lb=0, ub=self.w_max, var_type='integer' if self.weight_type == int else 'continuous', name_prefix='w')

        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            f_u_v = data[self.flow_attr]

            for i in range(self.k):
                self.solver.add_constraint(self.pi_vars[(u,v,i)] <= self.edge_vars[(u,v,i)] * self.w_max, name="10e_u={}_v={}_i={}".format(u,v,i))
                self.solver.add_constraint(self.pi_vars[(u,v,i)] <= self.path_weights_vars[(i)], name="10f_u={}_v={}_i={}".format(u,v,i))
                self.solver.add_constraint(self.pi_vars[(u,v,i)] >= self.path_weights_vars[(i)] - (1 - self.edge_vars[(u,v,i)]) * self.w_max, name="10g_u={}_v={}_i={}".format(u,v,i))

            self.solver.add_constraint(sum(self.pi_vars[(u,v,i)] for i in range(self.k)) == f_u_v, name="10d_u={}_v={}_i={}".format(u,v,i))

    def __get_solution_weights(self) -> list:
        """
        Retrieves the solution weights from the solver and returns them as a list.
        This method first checks if the solver has been solved using the `check_solved` method.
        It then retrieves the variable names and values from the solver. For each variable that
        represents a weight (indicated by the variable name starting with 'w'), it extracts the
        weight index and assigns the corresponding value to the `path_weights_sol` list. The
        values are rounded if the weight type is `int`, and converted to float if the weight type
        is `float`.

        Returns
        -------
        - list: A list of solution weights.
        """

        self.check_solved()
        
        varNames = self.solver.get_variable_names()
        varValues = self.solver.get_variable_values()
        self.path_weights_sol = [0]*len(range(0,self.k))

        for index, var in enumerate(varNames):
            if var[0] == 'w':
                weight_index = int(var[1:].strip())
                if self.weight_type == int:
                    self.path_weights_sol[weight_index] = round(varValues[index]) # TODO: check if we can add tolerance here, how does it work with other solvers?
                elif self.weight_type == float:
                    self.path_weights_sol[weight_index] = float(varValues[index])

        return self.path_weights_sol
    
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
        self.solution = (self.get_solution_paths(), self.__get_solution_weights())

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

        solution_weights = self.solution[1]
        solution_paths = self.solution[0]
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
    
    def maxBottleckPath(self, G: nx.DiGraph):
        """
        Computes the maximum bottleneck path in a directed graph.
        
        Parameters
        ----------
        - G (nx.DiGraph): A directed graph where each edge has a flow attribute.
        
        Returns
        ----------
        - tuple: A tuple containing:
            - The value of the maximum bottleneck.
            - The path corresponding to the maximum bottleneck (list of nodes).
                If no s-t flow exists in the network, returns (None, None).
        """
        B = dict()
        maxInNeighbor = dict()
        maxBottleneckSink = None

        # Computing the B values with DP
        for v in nx.topological_sort(G):
            if G.in_degree(v) == 0:
                B[v] = float('inf')
            else:
                B[v] = float('-inf')
                for u in G.predecessors(v):
                    uBottleneck = min(B[u], G.edges[u,v][self.flow_attr])
                    if uBottleneck > B[v]:
                        B[v] = uBottleneck 
                        maxInNeighbor[v] = u
                if G.out_degree(v) == 0:
                    if maxBottleneckSink is None or B[v] > B[maxBottleneckSink]:
                        maxBottleneckSink = v

        
        # If no s-t flow exists in the network
        if B[maxBottleneckSink] == 0:
            return None, None
        
        # Recovering the path of maximum bottleneck
        reverse_path = [maxBottleneckSink]
        while G.in_degree(reverse_path[-1]) > 0:
            reverse_path.append(maxInNeighbor[reverse_path[-1]])

        return B[maxBottleneckSink], list(reversed(reverse_path))
    
    def decompose_using_max_bottleck(self):
        """
        Decomposes the flow greedily into paths using the maximum bottleneck algorithm.
        This method iteratively finds the path with the maximum bottleneck capacity
        in the graph and decomposes the flow along that path. The process continues
        until no more paths can be found.
        
        Returns
        ----------
        - tuple: A tuple containing two lists:
            - paths (list of lists): A list of paths, where each path is represented
              as a list of nodes.
            - weights (list): A list of weights (bottleneck capacities) corresponding to each path.
        """
        
        paths = list()
        weights = list()
        
        temp_G = nx.DiGraph()
        temp_G.add_nodes_from(self.G.nodes())
        temp_G.add_edges_from(self.G.edges(data=True))
        temp_G.remove_nodes_from([self.G.source, self.G.sink])
        
        while True:
            bottleneck, path = self.maxBottleckPath(temp_G)
            if path is None:
                break
                
            for i in range(len(path)-1):
                temp_G[path[i]][path[i+1]][self.flow_attr] -= bottleneck
            
            paths.append(path)
            weights.append(bottleneck)
            
        return (paths, weights)
