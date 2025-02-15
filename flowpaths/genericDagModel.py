import stDiGraph
import networkx as nx
import safety
import solverWrapper
import time

class genericDAGModel:

    def __init__(self, G: stDiGraph.stDiGraph, num_paths: int, \
                 subpath_constraints: list = None, \
                 optimize_with_safe_paths: bool = False, \
                 optimize_with_safe_sequences: bool = False, \
                 optimize_with_safe_zero_edges: bool = False, \
                 trusted_edges_for_safety: set = None, \
                 external_solution_paths: list = None, \
                 solve_statistics: dict = {}, \
                 threads: int = 4, \
                 time_limit: int = 300, \
                 presolve = "on", \
                 log_to_console = "false", \
                 external_solver = "highs"):
        
        self.G = G
        self.id = self.G.id
        self.k = num_paths
        self.subpath_constraints = subpath_constraints
        self.solve_statistics = solve_statistics
        self.edge_vars = {}
        self.edge_vars_sol = {}
        self.subpaths_vars = {}

        self.threads = threads
        self.time_limit = time_limit
        self.presolve = presolve
        self.log_to_console = log_to_console
        self.external_solver = external_solver

        self.external_solution_paths = external_solution_paths
        if self.external_solution_paths is None:
            self.solved = None
        else:
            self.solved = True

        # optimizations
        self.optimize_with_safe_zero_edges = optimize_with_safe_zero_edges
        self.optimize_with_safe_paths = optimize_with_safe_paths
        self.optimize_with_safe_sequences = optimize_with_safe_sequences
        self.safe_lists = None
        if self.optimize_with_safe_paths and not self.solved:
            start_time = time.time()
            self.safe_lists = safety.safe_paths(self.G, trusted_edges_for_safety, no_duplicates=False)
            self.solve_statistics["safe_paths_time"] = time.time() - start_time

        if self.optimize_with_safe_sequences and not self.solved:
            start_time = time.time()
            self.safe_lists = safety.safe_sequences(self.G, trusted_edges_for_safety, no_duplicates=False)
            self.solve_statistics["safe_sequences_time"] = time.time() - start_time

        # some checks
        if self.safe_lists is not None and trusted_edges_for_safety is None:
            raise ValueError("trusted_edges_for_safety must be provided when optimizing with safe lists")
        if optimize_with_safe_paths and optimize_with_safe_sequences:
            raise ValueError("Cannot optimize with both safe paths and safe sequences")

    def create_solver_and_paths(self):
        if self.external_solution_paths is not None:
            return

        self.solver = solverWrapper.solverWrapper(solver_type=self.external_solver, 
                                                  threads=self.threads, 
                                                  time_limit=self.time_limit, 
                                                  presolve=self.presolve, 
                                                  log_to_console=self.log_to_console)
        
        self.encode_paths()

    def encode_paths(self):
        self.edge_indexes = [(u, v, i) for i in range(self.k) for (u, v) in self.G.edges()]
        self.path_indexes = [(i) for i in range(self.k)]
        self.subpath_indexes = [(i, j) for i in range(self.k) for j in range(len(self.subpath_constraints))]

        self.edge_vars = self.solver.add_variables(self.edge_indexes, lb=0, ub=1, var_type='integer', name_prefix='e')
        if self.subpath_constraints:
            self.subpaths_vars = self.solver.add_variables(self.subpath_indexes, lb=0, ub=1, var_type='integer', name_prefix='r')

        # The identifiers of the constraints come from https://arxiv.org/pdf/2201.10923 page 14-15

        for i in range(self.k):
            self.solver.add_constraint(sum(self.edge_vars[(self.G.source, v, i)] for v in self.G.successors(self.G.source)) == 1, name="10a_i={}".format(i))
            self.solver.add_constraint(sum(self.edge_vars[(u, self.G.sink, i)] for u in self.G.predecessors(self.G.sink)) == 1, name="10b_i={}".format(i))

        for i in range(self.k):
            for v in self.G.nodes:  # find all edges u->v->w for v in V\{s,t}
                if v == self.G.source or v == self.G.sink:
                    continue
                self.solver.add_constraint(sum(self.edge_vars[(u, v, i)] for u in self.G.predecessors(v)) -
                                           sum(self.edge_vars[(v, w, i)] for w in self.G.successors(v)) == 0, "10c_v={}_i={}".format(v, i))

        # Example of a subpath constraint: R=[ [(1,3),(3,5)], [(0,1)] ], means that we have 2 paths to cover, the first one is 1-3-5. the second path is just a single edge 0-1
        if self.subpath_constraints:
            for i in range(self.k):
                for j in range(len(self.subpath_constraints)):
                    edgevars_on_subpath = list(map(lambda e: self.edge_vars[(e[0], e[1], i)], self.subpath_constraints[j]))
                    self.solver.add_constraint(sum(edgevars_on_subpath) >= len(self.subpath_constraints[j]) * self.subpaths_vars[(i, j)], name="7a_i={}_j={}".format(i, j))
            for j in range(len(self.subpath_constraints)):
                self.solver.add_constraint(sum(self.subpaths_vars[(i, j)] for i in range(self.k)) >= 1, name="7b_j={}".format(j))

        # Fixing variables based on safe lists
        if self.safe_lists is not None:
            paths_to_fix = self.__get_paths_to_fix_from_safe_lists()
            
            # iterating over safe lists
            for i in range(min(len(paths_to_fix), self.k)):
                # print("Fixing variables for safe list #", i)
                # iterate over the edges in the safe list to fix variables to 1
                for (u, v) in paths_to_fix[i]:
                    self.solver.add_constraint(self.edge_vars[(u, v, i)] == 1, name="safe_list_u={}_v={}_i={}".format(u, v, i))
                
                if self.optimize_with_safe_zero_edges:
                    # print("Optimizing with safe zero edges for safe list", paths_to_fix[i])
                    # get the edges not reachable from the end of a safe list
                    first_node = paths_to_fix[i][0][0] 
                    last_node = paths_to_fix[i][-1][1]
                    if self.optimize_with_safe_sequences:
                        # finding the longest safe path in a sequence
                        left_node = paths_to_fix[i][0][0]
                        right_node =paths_to_fix[i][0][1]
                        length_safe_path = 1
                        max_left_node = left_node
                        max_right_node = right_node
                        max_length_safe_path = 1

                        # iterating through the edges of the safe sequence
                        for j in range(len(paths_to_fix[i])-1):
                            # at the first break in the sequence, last_node =  the node before the break
                            if paths_to_fix[i][j][1] == paths_to_fix[i][j+1][0]:
                                right_node = paths_to_fix[i][j+1][1]
                                length_safe_path += 1
                            else:
                                if length_safe_path > max_length_safe_path:
                                    max_length_safe_path = length_safe_path
                                    max_left_node = left_node
                                    max_right_node = right_node
                                left_node = paths_to_fix[i][j+1][0]
                                right_node = paths_to_fix[i][j+1][1]
                                length_safe_path = 1

                        first_node = max_left_node
                        last_node = max_right_node                    
                    # print("first_node", first_node)
                    # print("last_node", last_node)
                    reachable_nodes = set()
                    if last_node != self.G.sink:
                        reachable_nodes = {last_node}
                        successors = nx.dfs_successors(self.G, source=last_node)
                        # print("successors", successors)
                        for node in successors:
                            # print("node", node)
                            # print("successors[node]", successors[node])
                            for reachable_node in successors[node]:
                                reachable_nodes.add(reachable_node)
                            
                    # print("reachable_nodes", reachable_nodes, "from source", last_node)
                    
                    reachable_nodes_reverse = set()
                    if first_node != self.G.source:
                        reachable_nodes_reverse = {first_node}
                        rev_G = nx.DiGraph(self.G)
                        rev_G = rev_G.reverse(copy = True)
                        predecessors = nx.dfs_successors(rev_G, source=first_node)
                        for node in predecessors:
                            # print("node", node)
                            # print("predecessors[node]", predecessors[node])
                            for reachable_node_reverse in predecessors[node]:
                                reachable_nodes_reverse.add(reachable_node_reverse)
                    # print("reachable_nodes_reverse", reachable_nodes_reverse, "from source", first_node)    

                    path_edges = set((u,v) for (u, v) in paths_to_fix[i])
                    # print("path_edges", path_edges)

                    for (u, v) in self.G.base_graph.edges():
                        if (u, v) not in path_edges and \
                            u not in reachable_nodes and v not in reachable_nodes_reverse:
                            # print(f"Adding zero constraint for edge ({u}, {v}) in path {i}")
                            self.solver.add_constraint(self.edge_vars[(u, v, i)] == 0, name="safe_list_zero_edge_u={}_v={}_i={}".format(u, v, i))
                    
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
        
        paths_to_fix = list(map(lambda edge: self.safe_lists[longest_safe_list[edge]], edge_antichain))

        return paths_to_fix

    def solve(self) -> bool:
        # If we already received an external solution, we don't need to solve the model
        if self.external_solution_paths is not None:
            self.solved = True
            return True

        self.write_model(f"model-{self.id}.lp")
        start_time = time.time()
        self.solver.optimize()
        self.solve_statistics[f"milp_solve_time_for_num_paths_{self.k}"] = time.time() - start_time

        self.solve_statistics[f"milp_solver_status_for_num_paths_{self.k}"] = self.solver.get_model_status()
        
        if self.solver.get_model_status() == 'kOptimal' or self.solver.get_model_status() == 2:
            self.solved = True
            return True
        
        self.solved = False
        return False
    
    def write_model(self, filename: str):
        self.solver.write_model(filename)

    def check_solved(self):       
        if not self.solved:
            raise Exception("Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit.")

    def __get_path_variables_values(self):
        self.check_solved()

        varNames = self.solver.get_variable_names()
        varValues = self.solver.get_variable_values()

        for index, var in enumerate(varNames):
            if var[0] == 'e':
                elements = var.replace('(',',').replace(')',',').split(',')
                u = elements[1].strip(' \'')
                v = elements[2].strip(' \'')
                i = int(elements[3].strip())
                self.edge_vars_sol[(u, v, i)] = abs(round(varValues[index]))  # TODO: check if we can add tolerance here, how does it work with other solvers?

    def get_solution_paths(self) -> list:
        if self.external_solution_paths is not None:
            return self.external_solution_paths

        if self.edge_vars_sol == {}:
            self.__get_path_variables_values()

        paths = []
        for i in range(self.k):
            vertex = self.G.source
            path = [vertex]
            while vertex != self.G.sink:
                for out_neighbor in self.G.successors(vertex):
                    if self.edge_vars_sol[(str(vertex), str(out_neighbor), i)] == 1:
                        vertex = out_neighbor
                        break
                path.append(vertex)
            paths.append(path)

        return paths

