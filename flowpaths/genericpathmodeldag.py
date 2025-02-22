import flowpaths.stdigraph as stdigraph
from flowpaths.utils import safety
from flowpaths.utils import solverwrapper
import time


class GenericPathModelDAG:
    def __init__(
        self,
        G: stdigraph.stDiGraph,
        num_paths: int,
        subpath_constraints: list = None,
        encode_edge_position: bool = False,
        **kwargs,
    ):
        """
        This is a generic class modelling a path finding ILP in a DAG.

        Parameters
        ----------
        - G (stDiGraph.stDiGraph): The directed acyclic graph (DAG) to be used.
        - num_paths (int): The number of paths to be computed.
        - subpath_constraints (list, optional): Constraints for subpaths. Defaults to None.
        - optimize_with_safe_paths (bool, optional): Whether to optimize with safe paths. Defaults to False.
        - optimize_with_safe_sequences (bool, optional): Whether to optimize with safe sequences. Defaults to False.
        - optimize_with_safe_zero_edges (bool, optional): Whether to optimize with safe zero edges. Defaults to False.
        - trusted_edges_for_safety (set, optional): Set of trusted edges for safety. Defaults to None.
        - external_solution_paths (list, optional): External solution paths. Defaults to None.
        - solve_statistics (dict, optional): Dictionary to store solve statistics. Defaults to {}.
        - threads (int, optional): Number of threads to use. Defaults to 4.
        - time_limit (int, optional): Time limit for solving. Defaults to 300.
        - presolve (str, optional): Presolve option. Defaults to "on".
        - log_to_console (str, optional): Log to console option. Defaults to "false".
        - external_solver (str, optional): External solver to use. Defaults to "highs".

        Raises
        ----------
        - ValueError: If `trusted_edges_for_safety` is not provided when optimizing with safe lists.
        - ValueError: If both `optimize_with_safe_paths` and `optimize_with_safe_sequences` are set to True.
        """

        self.G = G
        self.id = self.G.id
        self.k = num_paths
        self.subpath_constraints = subpath_constraints

        self.solve_statistics = kwargs.get("solve_statistics", {})
        self.edge_vars = {}
        self.edge_vars_sol = {}
        self.subpaths_vars = {}
        self.encode_edge_position = encode_edge_position
        self.edge_position_vars = {}

        self.threads = kwargs.get("threads", 4)
        self.time_limit = kwargs.get("time_limit", 300)
        self.presolve = kwargs.get("presolve", "on")
        self.log_to_console = kwargs.get("log_to_console", "false")
        self.external_solver = kwargs.get("external_solver", "highs")

        self.external_solution_paths = kwargs.get("external_solution_paths", None)
        if self.external_solution_paths is None:
            self.is_solved = None
        else:
            self.is_solved = True

        # optimizations
        self.optimize_with_safe_paths = kwargs.get("optimize_with_safe_paths", True)
        self.optimize_with_safe_sequences = kwargs.get("optimize_with_safe_sequences", False)
        self.trusted_edges_for_safety = kwargs.get("trusted_edges_for_safety", None)
        self.optimize_with_safe_zero_edges = kwargs.get("optimize_with_safe_zero_edges", True)

        self.safe_lists = None
        if self.optimize_with_safe_paths and not self.is_solved:
            start_time = time.time()
            self.safe_lists = safety.safe_paths(
                self.G,
                self.trusted_edges_for_safety,
                no_duplicates=False,
                threads=self.threads,
            )
            self.solve_statistics["safe_paths_time"] = time.time() - start_time

        if self.optimize_with_safe_sequences and not self.is_solved:
            start_time = time.time()
            self.safe_lists = safety.safe_sequences(
                self.G,
                self.trusted_edges_for_safety,
                no_duplicates=False,
                threads=self.threads,
            )
            self.solve_statistics["safe_sequences_time"] = time.time() - start_time

        # some checks
        if self.safe_lists is not None and self.trusted_edges_for_safety is None:
            raise ValueError(
                "trusted_edges_for_safety must be provided when optimizing with safe lists"
            )
        if self.optimize_with_safe_paths and self.optimize_with_safe_sequences:
            raise ValueError("Cannot optimize with both safe paths and safe sequences")

    def create_solver_and_paths(self):
        """
        Creates a solver instance and encodes the paths in the graph.

        This method initializes the solver with the specified parameters and encodes the paths
        by creating variables for edges and subpaths.

        If external solution paths are provided, it skips the solver creation.
        """
        if self.external_solution_paths is not None:
            return

        self.solver = solverwrapper.SolverWrapper(
            solver_type=self.external_solver,
            threads=self.threads,
            time_limit=self.time_limit,
            presolve=self.presolve,
            log_to_console=self.log_to_console,
        )

        self.encode_paths()

    def encode_paths(self):
        """
        Encodes the paths in the graph by creating variables for edges and subpaths.

        This method initializes the edge and subpath variables for the solver and adds constraints
        to ensure the paths are valid according to the given subpath constraints and safe lists.
        """
        self.edge_indexes = [
            (u, v, i) for i in range(self.k) for (u, v) in self.G.edges()
        ]
        self.path_indexes = [(i) for i in range(self.k)]
        if self.subpath_constraints:
            self.subpath_indexes = [
                (i, j) for i in range(self.k) for j in range(len(self.subpath_constraints))
            ]

        self.edge_vars = self.solver.add_variables(
            self.edge_indexes, name_prefix="edge", lb=0, ub=1, var_type="integer"
        )
        if self.subpath_constraints:
            self.subpaths_vars = self.solver.add_variables(
                self.subpath_indexes, name_prefix="r", lb=0, ub=1, var_type="integer"
            )

        # The identifiers of the constraints come from https://arxiv.org/pdf/2201.10923 page 14-15

        for i in range(self.k):
            self.solver.add_constraint(
                sum(
                    self.edge_vars[(self.G.source, v, i)]
                    for v in self.G.successors(self.G.source)
                )
                == 1,
                name="10a_i={}".format(i),
            )
            self.solver.add_constraint(
                sum(
                    self.edge_vars[(u, self.G.sink, i)]
                    for u in self.G.predecessors(self.G.sink)
                )
                == 1,
                name="10b_i={}".format(i),
            )

        for i in range(self.k):
            for v in self.G.nodes:  # find all edges u->v->w for v in V\{s,t}
                if v == self.G.source or v == self.G.sink:
                    continue
                self.solver.add_constraint(
                    sum(self.edge_vars[(u, v, i)] for u in self.G.predecessors(v))
                    - sum(self.edge_vars[(v, w, i)] for w in self.G.successors(v))
                    == 0,
                    "10c_v={}_i={}".format(v, i),
                )

        # Example of a subpath constraint: R=[ [(1,3),(3,5)], [(0,1)] ], means that we have 2 paths to cover, the first one is 1-3-5. the second path is just a single edge 0-1
        if self.subpath_constraints:
            for i in range(self.k):
                for j in range(len(self.subpath_constraints)):
                    edgevars_on_subpath = list(
                        map(
                            lambda e: self.edge_vars[(e[0], e[1], i)],
                            self.subpath_constraints[j],
                        )
                    )
                    self.solver.add_constraint(
                        sum(edgevars_on_subpath)
                        >= len(self.subpath_constraints[j])
                        * self.subpaths_vars[(i, j)],
                        name="7a_i={}_j={}".format(i, j),
                    )
            for j in range(len(self.subpath_constraints)):
                self.solver.add_constraint(
                    sum(self.subpaths_vars[(i, j)] for i in range(self.k)) >= 1,
                    name="7b_j={}".format(j),
                )

        # Encoding position variables

        # edge_position_vars[(u, v, i)] = position (i.e., index) 
        # of the edge (u, v) in the path i, starting from position 0. 
        if self.encode_edge_position:
            self.edge_position_vars = self.solver.add_variables(
                self.edge_indexes, name_prefix="position", lb=0, ub=self.G.number_of_nodes(), var_type="integer"
            )
            # print("Adding position constraints")
            # print("self.G.edges()", self.G.edges())
            for i in range(self.k):
                for (u,v) in self.G.edges():
                    # print(f"Adding position constraint for edge ({u}, {v}) in path {i}")
                    # print(self.G.reachable_edges_rev_from[u])
                    self.solver.add_constraint(
                        self.edge_position_vars[(u, v, i)] == sum(self.edge_vars[(edge[0], edge[1], i)] for edge in self.G.reachable_edges_rev_from[u]),
                        name=f"position_u={u}_v={v}_i={i}"
                    )

        # Fixing variables based on safe lists
        if self.safe_lists is not None:
            paths_to_fix = self.__get_paths_to_fix_from_safe_lists()

            # iterating over safe lists
            for i in range(min(len(paths_to_fix), self.k)):
                # print("Fixing variables for safe list #", i)
                # iterate over the edges in the safe list to fix variables to 1
                for u, v in paths_to_fix[i]:
                    self.solver.add_constraint(
                        self.edge_vars[(u, v, i)] == 1,
                        name="safe_list_u={}_v={}_i={}".format(u, v, i),
                    )

                if self.optimize_with_safe_zero_edges:
                    # get the endpoints of the longest safe path in the sequence
                    first_node, last_node = (
                        safety.get_endpoints_of_longest_safe_path_in(paths_to_fix[i])
                    )
                    # get the reachable nodes from the last node
                    reachable_nodes = self.G.reachable_nodes_from[last_node]
                    # get the backwards reachable nodes from the first node
                    reachable_nodes_reverse = self.G.reachable_nodes_rev_from[first_node]
                    # get the edges in the path
                    path_edges = set((u, v) for (u, v) in paths_to_fix[i])

                    for u, v in self.G.base_graph.edges():
                        if (
                            (u, v) not in path_edges
                            and u not in reachable_nodes
                            and v not in reachable_nodes_reverse
                        ):
                            # print(f"Adding zero constraint for edge ({u}, {v}) in path {i}")
                            self.solver.add_constraint(
                                self.edge_vars[(u, v, i)] == 0,
                                name=f"safe_list_zero_edge_u={u}_v={v}_i={i}",
                            )

    def __get_paths_to_fix_from_safe_lists(self):
        longest_safe_list = dict()
        for i, safe_list in enumerate(self.safe_lists):
            for edge in safe_list:
                if edge not in longest_safe_list:
                    longest_safe_list[edge] = i
                elif len(self.safe_lists[longest_safe_list[edge]]) < len(safe_list):
                    longest_safe_list[edge] = i

        len_of_longest_safe_list = {
            edge: len(self.safe_lists[longest_safe_list[edge]])
            for edge in longest_safe_list
        }

        _, edge_antichain = self.G.compute_max_edge_antichain(
            get_antichain=True, weight_function=len_of_longest_safe_list
        )

        paths_to_fix = list(
            map(lambda edge: self.safe_lists[longest_safe_list[edge]], edge_antichain)
        )

        return paths_to_fix

    def solve(self) -> bool:
        """
        Solves the optimization model for the current instance.

        Returns
        ----------
        - True if the model is solved successfully, False otherwise.

        The method first checks if an external solution is already provided. If so, it sets the
        solved attribute to True and returns True.

        If not, it optimizes the model using the solver, and records the solve time and solver status
        in the solve_statistics dictionary. If the solver status indicates an optimal solution
        (either 'kOptimal' (highs) or status code 2 (gurobi)), it sets the solved attribute to True and returns True.
        Otherwise, it sets the solved attribute to False and returns False.
        """
        # If we already received an external solution, we don't need to solve the model
        if self.external_solution_paths is not None:
            self.is_solved = True
            return True

        # self.write_model(f"model-{self.id}.lp")
        start_time = time.time()
        self.solver.optimize()
        self.solve_statistics[f"milp_solve_time_for_num_paths_{self.k}"] = (
            time.time() - start_time
        )

        self.solve_statistics[f"milp_solver_status_for_num_paths_{self.k}"] = (
            self.solver.get_model_status()
        )

        if (
            self.solver.get_model_status() == "kOptimal"
            or self.solver.get_model_status() == 2
        ):
            self.is_solved = True
            return True

        self.is_solved = False
        return False

    def write_model(self, filename: str):
        """
        Writes the current model to a file.

        Parameters
        ----------
        - filename (str): The path to the file where the model will be written.
        """
        self.solver.write_model(filename)

    def check_is_solved(self):
        if not self.is_solved:
            raise Exception(
                "Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit."
            )
        
    def is_solved(self):
        return self.is_solved

    def get_solution_paths(self) -> list:
        """
        Retrieves the solution paths from the graph.

        This method returns the solution paths either from the external solution paths
        if they are provided at initialization time, or by calculating them based on the
        edge variable solutions.

        Returns
        ----------
        - A list of paths, where each path is represented as a list of vertices.
        """
        if self.external_solution_paths is not None:
            return self.external_solution_paths

        if self.edge_vars_sol == {}:
            self.edge_vars_sol = self.solver.get_variable_values(
                "edge", [str, str, int], 
                binary_values=True,
            )

        paths = []
        for i in range(self.k):
            vertex = self.G.source
            # checking if there is a path from source to sink
            found_path = False
            for out_neighbor in self.G.successors(vertex):
                if self.edge_vars_sol[(str(vertex), str(out_neighbor), i)] == 1:
                    found_path = True
                    break
            if not found_path:
                path = []
                paths.append(path)
                print("Warning: No path found for path index", i)
            else:
                path = [vertex]
                while vertex != self.G.sink:
                    for out_neighbor in self.G.successors(vertex):
                        if self.edge_vars_sol[(str(vertex), str(out_neighbor), i)] == 1:
                            vertex = out_neighbor
                            break
                    path.append(vertex)
                if len(path) < 2:
                    raise Exception(f"Something went wrong, solution path {path} has less than 2 vertices. this should not happen. Make sure the stDiGraph has no edge from global source {self.G.source} to global sink {self.G.sink}.")
                
                paths.append(path[1:-1])

        return paths


    def verify_edge_position(self):
        
        if not self.encode_edge_position:
            return True
        
        self.check_is_solved()

        paths = self.get_solution_paths()

        edge_position_sol = self.solver.get_variable_values("position", [str, str, int])

        for path_index, path in enumerate(paths):
            for edge_position, (u,v) in enumerate(zip(path[:-1], path[1:])):
                # +1 because the solution paths don't have the edge from global source
                if round(edge_position_sol[(str(u), str(v), path_index)]) != edge_position + 1:
                    return False
        return True