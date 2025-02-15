import highspy
import time
import networkx as nx
import stDiGraph
import genericDAGModel
import solverWrapper

TOLERANCE = 0.001

class modelFD(genericDAGModel.genericDAGModel):

    def __init__(self, G: nx.DiGraph, flow_attr: str, num_paths: int, weight_type: type = int, \
                subpath_constraints: list = [], \
                edges_to_ignore: set = set(), \
                optimize_with_safe_paths: bool = False, \
                optimize_with_safe_sequences: bool = True, \
                optimize_with_safe_zero_edges: bool = False, \
                optimize_with_greedy: bool = False, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false",\
                external_solver = "highspy"):
            
        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        # Check requirements on input graph:
        # Check flow conservation
        if not self.check_flow_conservation(G, flow_attr):
            raise ValueError("The graph G does not satisfy flow conservation.")

        # Check that the flow is positive and get max flow value
        self.w_max = self.weight_type(self.get_max_flow_value_and_check_positive_flow(G, flow_attr, edges_to_ignore))

        # Check that the graph is acyclic
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("The graph G must be acyclic.")

        self.G = stDiGraph.stDiGraph(G)
    
        self.flow_attr = flow_attr
        self.k = num_paths
        self.subpath_constraints = subpath_constraints
        self.edges_to_ignore = edges_to_ignore
        self.edges_to_ignore.update(self.G.source_edges)
        self.edges_to_ignore.update(self.G.sink_edges)

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
        
        start_time = time.time()
        (paths, weights) = self.decompose_using_max_bottleck()
        if len(paths) <= self.k:
            self.solution = (paths, weights)
            self.solved = True
            self.solve_statistics = {}
            self.solve_statistics["greedy_solve_time"] = time.time() - start_time
            return True
        
        return False

    # This function also checks that the flow is positive
    def get_max_flow_value_and_check_positive_flow(self, G: nx.DiGraph, flow_attr: str, edges_to_ignore: list = []):

        w_max = float('-inf')   

        for u, v, data in G.edges(data=True):
            if (u,v) in edges_to_ignore:
                continue
            if not flow_attr in data:
                raise ValueError(f"Edge ({u},{v}) does not have the required flow attribute '{self.flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data.")
            if data[flow_attr] < 0:
                raise ValueError(f"Edge ({u},{v}) has negative flow value {data[flow_attr]}. All flow values must be >=0.")
            w_max = max(w_max, data[flow_attr])

        return w_max
    
    def check_flow_conservation(self, G: nx.DiGraph, flow_attr) -> bool:
        
        for v in G.nodes():
            if G.out_degree(v) == 0 or G.in_degree(v) == 0:
                continue
            out_flow = sum(flow for (v,w,flow) in G.out_edges(v, data=flow_attr))
            in_flow  = sum(flow for (u,v,flow) in G.in_edges(v, data=flow_attr))
            
            if out_flow != in_flow:
                return False
            
        return True

    def get_non_zero_flow_edges(self):
        
        non_zero_flow_edges = set()
        for u, v, data in self.G.edges(data=True):
            if (u,v) not in self.edges_to_ignore and data.get(self.flow_attr, 0) != 0:
                non_zero_flow_edges.add((u,v))

        return non_zero_flow_edges

    def encode_flow_decomposition(self):

        # If already solved, no need to encode further
        if self.solved:
            return

        if self.weight_type == int:
            wtype = highspy.HighsVarType.kInteger
        elif self.weight_type == float:
            wtype = highspy.HighsVarType.kContinuous
        
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

        if self.solution is not None:
            return self.solution

        self.check_solved()
        self.solution = (self.get_solution_paths(), self.__get_solution_weights())

        if not self.check_solution():
            raise AssertionError("Something went wrong. The solution returned by the MILP solver is not a flow decomposition.")

        return self.solution
    
    def check_solution(self):

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
                if flow_from_paths[(u, v)] - data[self.flow_attr] > TOLERANCE * num_paths_on_edges[(u, v)]: 
                    return False

        return True
    
    def maxBottleckPath(self, G: nx.DiGraph):
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
    

class modelMFD:
    def __init__(self, G: nx.DiGraph, flow_attr: str, weight_type: type = int, \
                subpath_constraints: list = [], \
                edges_to_ignore: set = set(), \
                optimize_with_safe_paths: bool = False, \
                optimize_with_safe_sequences: bool = True, \
                optimize_with_safe_zero_edges: bool = False, \
                optimize_with_greedy: bool = False, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false", \
                external_solver = "highspy"):
        
        stG = stDiGraph.stDiGraph(G)
        self.lowerbound = stG.width

        self.G = G
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.subpath_constraints = subpath_constraints
        self.edges_to_ignore = edges_to_ignore
        self.optimize_with_safe_paths = optimize_with_safe_paths
        self.optimize_with_safe_sequences = optimize_with_safe_sequences
        self.optimize_with_safe_zero_edges = optimize_with_safe_zero_edges
        self.optimize_with_greedy = optimize_with_greedy
        self.threads = threads
        self.time_limit = time_limit
        self.presolve = presolve
        self.log_to_console = log_to_console
        self.solve_statistics = {}
        self.solution = None
        self.solved = False
        self.external_solver = external_solver

    def solve(self) -> bool:
        start_time = time.time()
        for i in range(self.lowerbound, self.G.number_of_edges()):
            fd_model = modelFD(G = self.G, flow_attr = self.flow_attr, num_paths = i, weight_type = self.weight_type, \
                subpath_constraints = self.subpath_constraints, \
                edges_to_ignore = self.edges_to_ignore, \
                optimize_with_safe_paths = self.optimize_with_safe_paths, \
                optimize_with_safe_sequences = self.optimize_with_safe_sequences, \
                optimize_with_safe_zero_edges = self.optimize_with_safe_zero_edges, \
                optimize_with_greedy = self.optimize_with_greedy, \
                threads = self.threads, \
                time_limit = self.time_limit, \
                presolve = self.presolve, \
                log_to_console = self.log_to_console, \
                external_solver = self.external_solver)
            
            fd_model.solve()

            if fd_model.solved:
                self.solution = fd_model.get_solution()
                self.solved = True
                self.solve_statistics = fd_model.solve_statistics
                self.solve_statistics["mfd_solve_time"] = time.time() - start_time
                return True
        return False
    
    def get_solution(self):
        
        self.check_solved()
        return self.solution
    
    def check_solved(self):       
        if not self.solved or self.solution is None:
            raise Exception("Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit.")



