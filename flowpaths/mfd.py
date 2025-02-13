import highspy
import networkx as nx
import stDiGraph
import genericDagModel

class modelMFD(genericDagModel.genericDagModel):

    def __init__(self, G: nx.DiGraph, flow_attr: str, num_paths: int, weight_type: type = int,\
                subpath_constraints: list = [], \
                edges_to_ignore: set = set(),\
                optimize_with_safe_paths: bool = False, \
                optimize_with_safe_sequences: bool = True, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false"):
            
        self.G = stDiGraph.stDiGraph(G)

        if not self.check_flow_conservation(G, flow_attr):
            raise( ValueError("The graph G does not satisfy flow conservation."))
    
        self.flow_attr = flow_attr
        self.k = num_paths
        self.subpath_constraints = subpath_constraints
        self.edges_to_ignore = edges_to_ignore
        self.edges_to_ignore.update(self.G.source_edges)
        self.edges_to_ignore.update(self.G.sink_edges)
        
        self.pi_vars = {}
        self.path_weights = {}
        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        self.w_max = self.weight_type(self.get_max_flow_value(G, flow_attr, self.edges_to_ignore))
    
        self.path_weights_sol = None
        self.solution = None

        # Call the constructor of the parent class genericDagModel
        super().__init__(self.G, num_paths, \
                         subpath_constraints = self.subpath_constraints, \
                         optimize_with_safe_paths = optimize_with_safe_paths, \
                         optimize_with_safe_sequences = optimize_with_safe_sequences, \
                         trusted_edges_for_safety = self.get_non_zero_flow_edges(), \
                         threads = threads, \
                         time_limit = time_limit, \
                         presolve = presolve, \
                         log_to_console = log_to_console)  
        
        # This method is called from the super class genericDagModel
        self.create_solver_and_paths()

        # This method is called from the current class modelMFD
        self.encode_flow_decomposition()

        # From genericDagModel
        self.write_model(f"mfd-model-{self.G.id}.lp")

    def get_max_flow_value(self, G: nx.DiGraph, flow_attr: str, edges_to_ignore: list = []):

        w_max = float('-inf')   

        for u, v, data in G.edges(data=True):
            if (u,v) in edges_to_ignore:
                continue
            if not flow_attr in data:
                raise ValueError(f"Edge ({u},{v}) does not have the required flow attribute '{self.flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data.")
            w_max = max(w_max, data[flow_attr])

        return w_max

    def get_non_zero_flow_edges(self):
        
        non_zero_flow_edges = set()
        for u, v, data in self.G.edges(data=True):
            if (u,v) not in self.edges_to_ignore and data.get(self.flow_attr, 0) != 0:
                non_zero_flow_edges.add((u,v))

        return non_zero_flow_edges

    def encode_flow_decomposition(self):

        if self.weight_type == int:
            wtype = highspy.HighsVarType.kInteger
        elif self.weight_type == float:
            wtype = highspy.HighsVarType.kContinuous
        
        self.pi_vars        = self.solver.addVariables(self.edge_indexes, lb=0, ub=self.w_max, type=wtype, name_prefix='p')
        self.path_weights   = self.solver.addVariables(self.path_indexes, lb=0, ub=self.w_max, type=wtype, name_prefix='w')

        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            f_u_v = data[self.flow_attr]

            for i in range(self.k):
                self.solver.addConstr( self.pi_vars[(u,v,i)] <= self.edge_vars[(u,v,i)] * self.w_max                                  , "10e_u={}_v={}_i={}".format(u,v,i) )
                self.solver.addConstr( self.pi_vars[(u,v,i)] <= self.path_weights[(i)]                                                , "10f_u={}_v={}_i={}".format(u,v,i) )
                self.solver.addConstr( self.pi_vars[(u,v,i)] >= self.path_weights[(i)] - (1 - self.edge_vars[(u,v,i)]) * self.w_max   , "10g_u={}_v={}_i={}".format(u,v,i) )

            self.solver.addConstr( sum(self.pi_vars[(u,v,i)] for i in range(self.k)) == f_u_v                    , "10d_u={}_v={}_i={}".format(u,v,i) )

    def __get_solution_weights(self) -> list:

        self.check_solved()
        
        varNames = self.solver.allVariableNames()
        varValues = self.solver.allVariableValues()
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

        self.check_solved()
        self.solution = (self.get_solution_paths(), self.__get_solution_weights())

        if not self.check_solution():
            raise(AssertionError("Something went wrong. The solution returned by the MILP solver is not a flow decomposition."))

        return self.solution
    
    def check_solution(self):

        if self.solution is None:
            raise(ValueError("Solution is not available. Call get_solution() first."))

        solution_weights = self.solution[1]
        solution_paths = self.solution[0]
        solution_paths_of_edges = [[(path[i],path[i+1]) for i in range(len(path)-1)] for path in solution_paths]

        flow_from_paths = {(u,v):0 for (u,v) in self.G.edges()}
        for weight, path in zip(solution_weights, solution_paths_of_edges):
            for e in path:
                flow_from_paths[e] += weight

        for (u, v, data) in self.G.edges(data=True):
            if self.flow_attr in data:
                if flow_from_paths[(u, v)] != data[self.flow_attr]:
                    return False

        return True
    
    def check_flow_conservation(self, G: nx.DiGraph, flow_attr) -> bool:
        
        for v in G.nodes():
            if G.out_degree(v) == 0 or G.in_degree(v) == 0:
                continue
            out_flow = sum(flow for (v,w,flow) in G.out_edges(v, data=flow_attr))
            in_flow  = sum(flow for (u,v,flow) in G.in_edges(v, data=flow_attr))
            
            if out_flow != in_flow:
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
        # Making a copy of flowDict, otherwise the changes we make in this function 
        # will carry over to the global variable flowDict
        
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