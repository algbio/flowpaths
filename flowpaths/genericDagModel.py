import highspy
import stDiGraph

class genericDagModel:

    def __init__(self,G : stDiGraph, num_paths: int, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false"):
        self.G = G
        self.k = num_paths
        self.edge_vars = {}
        self.edge_vars_sol = {}
        self.solved = None

        self.threads = threads
        self.time_limit = time_limit
        self.presolve = presolve
        self.log_to_console = log_to_console

    def create_solver(self):
        self.solver = highspy.Highs()
        self.solver.setOptionValue("threads", self.threads)
        self.solver.setOptionValue("time_limit", self.time_limit)
        self.solver.setOptionValue("presolve", self.presolve)
        self.solver.setOptionValue("log_to_console", self.log_to_console)

    def encode_paths(self):
        self.edge_indexes    = [ (u,v,i) for i in range(self.k) for (u, v) in self.G.edges() ]
        self.path_indexes    = [ (    i) for i in range(self.k)                              ]

        self.edge_vars = self.solver.addVariables(self.edge_indexes, lb=0,  ub=1, type=highspy.HighsVarType.kInteger, name_prefix='e')

        #The identifiers of the constraints come from https://arxiv.org/pdf/2201.10923 page 14-15

        for i in range(self.k):
            self.solver.addConstr( sum(self.edge_vars[(self.G.source,   v ,             i)] for v in self.G.successors(self.G.source)) == 1,  name="10a_i={}".format(i) )
            self.solver.addConstr( sum(self.edge_vars[(u,               self.G.sink,    i)] for u in self.G.predecessors(self.G.sink)) == 1,  name="10b_i={}".format(i) )

        for i in range(self.k):
            for v in self.G.nodes: #find all wedges u->v->w for v in V\{s,t}
                if v == self.G.source or v == self.G.sink:
                    continue
                self.solver.addConstr( sum(self.edge_vars[(u, v, i)] for u in self.G.predecessors(v)) - \
                                       sum(self.edge_vars[(v, w, i)] for w in self.G.successors(v)) == 0, "10c_v={}_i={}".format(v,i) )        

    def solve(self) -> bool:
        self.solver.run()
        
        if self.solver.getModelStatus() == highspy.HighsModelStatus.kOptimal:
            self.solved = True
            return True
        
        self.solved = False
        return False
    
    def write_model(self, filename: str):
        self.solver.writeModel(filename)

    def check_solved(self):
        
        if not self.solved:
            raise("Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit.")

    def __get_path_variables_values(self):

        self.check_solved()

        varNames = self.solver.allVariableNames()
        varValues = self.solver.allVariableValues()

        for index, var in enumerate(varNames):
            if var[0] == 'e':
                elements = var.replace('(',',').replace(')',',').split(',')
                u = elements[1].strip(' \'')
                v = elements[2].strip(' \'')
                i = int(elements[3].strip())
                self.edge_vars_sol[(u,v,i)] = int(varValues[index])

    def get_solution_paths(self) -> list:

        if self.edge_vars_sol == {}:
            self.__get_path_variables_values()

        paths = []
        for i in range(self.k):
            vertex = self.G.source
            path = [vertex]
            while vertex != self.G.sink:
                for out_neighbor in self.G.successors(vertex):
                    if self.edge_vars_sol[(str(vertex),str(out_neighbor),i)] == 1:
                        vertex = out_neighbor
                        break
                path.append(vertex)
            paths.append(path)

        return paths

