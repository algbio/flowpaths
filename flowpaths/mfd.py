import highspy
import stDiGraph
import genericDagModel

class modelMFD(genericDagModel.genericDagModel):

    def __init__(self, G : stDiGraph, flow_attr: str, num_paths: int, weight_type: type = int,\
                edges_to_ignore: set = set(),\
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false"):
        super().__init__(G, num_paths, threads, time_limit, presolve, log_to_console)    
    
        self.G = G
        self.flow_attr = flow_attr
        self.k = num_paths
        self.edges_to_ignore = edges_to_ignore
        self.edges_to_ignore.update(self.G.source_edges)
        self.edges_to_ignore.update(self.G.sink_edges)
        
        self.pi_vars = {}
        self.path_weights = {}
        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type
    
        self.path_weights_sol = [0]*len(range(0,self.k))
        
        # These methods are called from the super class genericDagModel
        self.create_solver()
        self.encode_paths()

        # This method is called from the current class modelMFD
        self.encode_flow_decomposition()

        # From genericDagModel
        self.write_model(f"mfd-model-{G.id}.lp")

    def encode_flow_decomposition(self):
        
        self.w_max = 0
        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            if not self.flow_attr in data:
                raise ValueError(f"Edge ({u},{v}) does not have the required flow attribute '{self.flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data.")
            if data.get(self.flow_attr, 0) > self.w_max:
                self.w_max = data.get(self.flow_attr, 0)

        if self.weight_type == int:
            wtype = highspy.HighsVarType.kInteger
        elif self.weight_type == float:
            wtype = highspy.HighsVarType.kContinuous
        
        self.pi_vars        = self.solver.addVariables(self.edge_indexes, lb=0, ub=self.w_max, type=wtype, name_prefix='p')
        self.path_weights   = self.solver.addVariables(self.path_indexes, lb=0, ub=self.w_max, type=wtype, name_prefix='w')

        for u, v, data in self.G.edges(data=True):
            if (u,v) in self.edges_to_ignore:
                continue
            f_u_v = data.get(self.flow_attr, 0)

            for i in range(self.k):
                self.solver.addConstr( self.pi_vars[(u,v,i)] <= self.edge_vars[(u,v,i)] * self.w_max                                  , "10e_u={}_v={}_i={}".format(u,v,i) )
                self.solver.addConstr( self.pi_vars[(u,v,i)] <= self.path_weights[(i)]                                                , "10f_u={}_v={}_i={}".format(u,v,i) )
                self.solver.addConstr( self.pi_vars[(u,v,i)] >= self.path_weights[(i)] - (1 - self.edge_vars[(u,v,i)]) * self.w_max   , "10g_u={}_v={}_i={}".format(u,v,i) )

            self.solver.addConstr( sum(self.pi_vars[(u,v,i)] for i in range(self.k)) == f_u_v                    , "10d_u={}_v={}_i={}".format(u,v,i) )

    def __get_solution_weights(self) -> list:

        self.check_solved()
        
        varNames = self.solver.allVariableNames()
        varValues = self.solver.allVariableValues()

        for index, var in enumerate(varNames):
            if var[0] == 'w':
                weight_index = int(var[1:].strip())
                self.path_weights_sol[weight_index] = self.weight_type(varValues[index])

        return self.path_weights_sol
    
    def get_solution(self):

        self.check_solved()

        return (self.get_solution_paths(), self.__get_solution_weights())