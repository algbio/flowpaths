import highspy
import stDiGraph
import safety
import time

# TODO
# - optimize using safe sequences by fixing variables

class genericDagModel:

    def __init__(self, G : stDiGraph, num_paths: int, \
                subpath_constraints: list = None, \
                optimize_with_safe_paths: bool = False, \
                optimize_with_safe_sequences: bool = False, \
                trusted_edges_for_safety: set = None, \
                external_solution_paths: list = None, \
                solve_statistics: dict = {}, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false"):
        
        self.G = G
        self.k = num_paths
        self.subpath_constraints = subpath_constraints
        self.solve_statistics = solve_statistics
        self.edge_vars = {}
        self.edge_vars_sol = {}
        self.subpaths_vars    = {}

        self.threads = threads
        self.time_limit = time_limit
        self.presolve = presolve
        self.log_to_console = log_to_console

        self.external_solution_paths = external_solution_paths
        if self.external_solution_paths == None:
            self.solved = None
        else:
            self.solved = True

        # optimizations
        self.safe_lists = None
        if optimize_with_safe_paths and not self.solved:
            start_time = time.time()
            self.safe_lists = safety.safe_paths(self.G, trusted_edges_for_safety, no_duplicates=False)
            self.solve_statistics["safe_paths_time"] = time.time() - start_time

        if optimize_with_safe_sequences and not self.solved:
            start_time = time.time()
            self.safe_lists = safety.safe_sequences(self.G, trusted_edges_for_safety, no_duplicates=False)
            self.solve_statistics["safe_sequences_time"] = time.time() - start_time

        # some checks
        if self.safe_lists != None and trusted_edges_for_safety == None:
            raise ValueError("trusted_edges_for_safety must be provided when optimizing with safe lists")
        if optimize_with_safe_paths and optimize_with_safe_sequences:
            raise ValueError("Cannot optimize with both safe paths and safe sequences")



    def create_solver_and_paths(self):
        if self.external_solution_paths != None:
            return
        
        self.solver = highspy.Highs()
        self.solver.setOptionValue("threads", self.threads)
        self.solver.setOptionValue("time_limit", self.time_limit)
        self.solver.setOptionValue("presolve", self.presolve)
        self.solver.setOptionValue("log_to_console", self.log_to_console)

        self.encode_paths()

    def encode_paths(self):
        self.edge_indexes    = [ (u,v,i) for i in range(self.k) for (u, v) in self.G.edges() ]
        self.path_indexes    = [ (    i) for i in range(self.k)                              ]
        self.subpath_indexes = [ (i,j  ) for i in range(self.k) for j in range(len(self.subpath_constraints)) ]

        
        self.edge_vars = self.solver.addVariables(self.edge_indexes, lb=0,  ub=1, type=highspy.HighsVarType.kInteger, name_prefix='e')
        if self.subpath_constraints != []:
            self.subpaths_vars  = self.solver.addVariables(self.subpath_indexes, lb=0, ub=1, type=highspy.HighsVarType.kInteger, name_refix='r')

        #The identifiers of the constraints come from https://arxiv.org/pdf/2201.10923 page 14-15

        for i in range(self.k):
            self.solver.addConstr( sum(self.edge_vars[(self.G.source,   v ,             i)] for v in self.G.successors(self.G.source)) == 1,  name="10a_i={}".format(i) )
            self.solver.addConstr( sum(self.edge_vars[(u,               self.G.sink,    i)] for u in self.G.predecessors(self.G.sink)) == 1,  name="10b_i={}".format(i) )

        for i in range(self.k):
            for v in self.G.nodes: #find all edges u->v->w for v in V\{s,t}
                if v == self.G.source or v == self.G.sink:
                    continue
                self.solver.addConstr( sum(self.edge_vars[(u, v, i)] for u in self.G.predecessors(v)) - \
                                       sum(self.edge_vars[(v, w, i)] for w in self.G.successors(v)) == 0, "10c_v={}_i={}".format(v,i) )        
        
        #Example of a subpath constraint: R=[ [(1,3),(3,5)], [(0,1)] ], means that we have 2 paths to cover, the first one is 1-3-5. the second path is just a single edge 0-1
        if self.subpath_constraints:
            for i in range(self.k):
                for j in range(len(self.subpath_constraints)):
                    edgevars_on_subpath = list(map(lambda e: self.edge_vars[(e[0],e[1],i)], self.subpath_constraints[j]))
                    self.solver.addConstr( sum(edgevars_on_subpath) >= len(self.subpath_constraints[j]) * self.subpaths_vars[(i,j)], name="7a_i={}_j={}".format(i,j) )
            for j in range(len(self.subpath_constraints)):
                self.solver.addConstr( sum(self.subpaths_vars[(i,j)] for i in range(self.k)) >= 1, name="7b_j={}".format(j) )
        
        # Fixing variables based on safe lists
        if self.safe_lists != None:
            paths_to_fix = self.__get_paths_to_fix_from_safe_lists()
            for i in range(min(len(paths_to_fix), self.k)):
                for (u,v) in paths_to_fix[i]:
                    self.solver.addConstr( self.edge_vars[(u,v,i)] == 1, name="safe_list_u={}_v={}_i={}".format(u,v,i) )

    def __get_paths_to_fix_from_safe_lists(self):
        
        longest_safe_list = dict()
        for i, safe_list in enumerate(self.safe_lists):
            for edge in safe_list:
                if edge not in longest_safe_list:
                    longest_safe_list[edge] = i
                elif len(self.safe_lists[longest_safe_list[edge]]) < len(safe_list):
                    longest_safe_list[edge] = i

        len_of_longest_safe_list = {edge: len(self.safe_lists[longest_safe_list[edge]]) for edge in longest_safe_list}

        _, edge_antichain = self.G.compute_max_edge_antichain(get_antichain=True, weight_function=len_of_longest_safe_list)
        
        paths_to_fix      = list(map(lambda edge : self.safe_lists[longest_safe_list[edge]] , edge_antichain))

        return paths_to_fix

    def solve(self) -> bool:

        if self.external_solution_paths != None:
            self.solved = True
            return True

        start_time = time.time()
        self.solver.run()
        self.solve_statistics["milp_solve_time"] = time.time() - start_time

        self.solve_statistics["milp_solver_status"] = self.solver.getModelStatus().name
        
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
                self.edge_vars_sol[(u,v,i)] = round(varValues[index]) # TODO: check if we can add tolerance here, how does it work with other solvers?

    def get_solution_paths(self) -> list:

        if self.external_solution_paths != None:
            return self.external_solution_paths

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

