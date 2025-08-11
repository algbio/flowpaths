import flowpaths.stdigraph as stdigraph
from flowpaths.utils import safetypathcovers
from flowpaths.utils import solverwrapper as sw
import flowpaths.utils as utils
import time
import copy
from abc import ABC, abstractmethod

class AbstractPathModelDiGraph(ABC):
    """
    
    """
    # storing some defaults
    optimize_with_safe_paths = True
    optimize_with_safe_sequences = False
    optimize_with_safe_zero_edges = True
    optimize_with_subpath_constraints_as_safe_sequences = True
    optimize_with_safety_as_subpath_constraints = False
    optimize_with_safety_from_largest_antichain = False

    def __init__(
        self,
        G: stdigraph.stDiGraph,
        k: int,
        subset_constraints: list = [],
        subset_constraints_coverage: float = 1,
        optimization_options: dict = None,
        solver_options: dict = {},
        solve_statistics: dict = {},
    ):
        """
        Parameters
        ----------

        - `G: stdigraph.stDiGraph`  
            
            The directed graph to be used.

        - `k: int`
            
            The number of s-t walks to be modeled.

        - `subset_constraints: list`, optional
            
            A list of lists, where each list is a *set* of edges (not necessarily contiguous). Defaults to an empty list.
            
            Each set of edges must appear in at least one solution path; if you also pass subpath_constraints_coverage, 
            then each set of edges must appear in at least sub_constraints_coverage fraction of some solution walk, see below.
        
        - `subpath_constraints_coverage: float`, optional
            
            Coverage fraction of the subset constraints that must be covered by some solution walk, in terms of number of edges. 
                - Defaults to 1 (meaning that 100% of the edges of the constraint need to be covered by some solution walk).
                
        - `optimization_options: dict`, optional 
            
            Dictionary of optimization options. Defaults to `None`, in which case the default values are used. See the [available optimizations](solver-options-optimizations.md). 
            If you pass any safety optimizations, you must also pass the dict entry `"trusted_edges_for_safety"` (see below). 
            If a child class has already solved the problem and has the solution paths, it can pass them via the dict entry `"external_solution_paths"` to skip the solver creation and encoding of paths (see below).
            
            - `"trusted_edges_for_safety": set`
        
                Set of trusted edges for safety. Defaults to `None`.

                !!! warning "Global optimality"
                    In order for the optimizations to still guarantee a global optimum, you must guarantee that:

                    1. The solution is made up of source-to-sink walks, and
                    2. Every edge in `trusted_edges_for_safety` appears in some solution walk, for all solutions. This naturally holds for several problems, for example [Minimum Flow Decomposition](minimum-flow-decomposition.md) or [k-Minimum Path Error] where in fact, under default settings, **all** edges appear in all solutions.

        - `solver_options: dict`, optional
            
            Dictionary of solver options. Defaults to `{}`, in which case the default values are used. 
            See the [available solver options](solver-options-optimizations.md).

        - `solve_statistics: dict`, optional
            
            Dictionary to store solve statistics. Defaults to `{}`.


        Raises
        ----------
        - ValueError: If `trusted_edges_for_safety` is not provided when optimizing with `optimize_with_safe_paths` or `optimize_with_safe_sequences`.
        """

        self.G = G
        if G.number_of_edges() == 0:
            utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
            raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
        self.id = self.G.id
        self.k = k
        
        self.subset_constraints = copy.deepcopy(subset_constraints)
        if self.subset_constraints is not None:
            self._check_valid_subset_constraints()

        self.subpath_constraints_coverage = subset_constraints_coverage
        if len(subset_constraints) > 0:
            if self.subpath_constraints_coverage <= 0 or self.subpath_constraints_coverage > 1:
                utils.logger.error(f"{__name__}: subpath_constraints_coverage must be in the range (0, 1]")
                raise ValueError("subpath_constraints_coverage must be in the range (0, 1]")
                
        self.solve_statistics = solve_statistics
        self.edge_vars = {}
        self.edge_vars_sol = {}
        self.subpaths_vars = {}

        self.solver_options = solver_options
        if self.solver_options is None:
            self.solver_options = {}
        self.threads = self.solver_options.get("threads", sw.SolverWrapper.threads)

        # optimizations
        if optimization_options is None:
            optimization_options = {}
        self.optimize_with_safe_paths = optimization_options.get("optimize_with_safe_paths", AbstractPathModelDiGraph.optimize_with_safe_paths)
        self.external_safe_paths = optimization_options.get("external_safe_paths", None)
        self.optimize_with_safe_sequences = optimization_options.get("optimize_with_safe_sequences", AbstractPathModelDiGraph.optimize_with_safe_sequences)
        self.optimize_with_subpath_constraints_as_safe_sequences = optimization_options.get("optimize_with_subpath_constraints_as_safe_sequences", AbstractPathModelDiGraph.optimize_with_subpath_constraints_as_safe_sequences)
        self.trusted_edges_for_safety = optimization_options.get("trusted_edges_for_safety", None)
        self.optimize_with_safe_zero_edges = optimization_options.get("optimize_with_safe_zero_edges", AbstractPathModelDiGraph.optimize_with_safe_zero_edges)
        self.external_solution_paths = optimization_options.get("external_solution_paths", None)
        self.allow_empty_paths = optimization_options.get("allow_empty_paths", False)
        self.optimize_with_safety_as_subpath_constraints = optimization_options.get("optimize_with_safety_as_subpath_constraints", AbstractPathModelDiGraph.optimize_with_safety_as_subpath_constraints)
        self.optimize_with_safety_from_largest_antichain = optimization_options.get("optimize_with_safety_from_largest_antichain", AbstractPathModelDiGraph.optimize_with_safety_from_largest_antichain)

        self._is_solved = None
        if self.external_solution_paths is not None:
            self._is_solved = True

        # some checks
        if self.optimize_with_safe_paths and self.external_safe_paths is None and self.trusted_edges_for_safety is None:
            utils.logger.error(f"{__name__}: trusted_edges_for_safety must be provided when optimizing with safe paths")
            raise ValueError("trusted_edges_for_safety must be provided when optimizing with safe lists")        
        if self.optimize_with_safe_sequences and self.external_safe_paths is not None:
            utils.logger.error(f"{__name__}: Cannot optimize with both external safe paths and safe sequences")
            raise ValueError("Cannot optimize with both external safe paths and safe sequences")

        if self.optimize_with_safe_paths and self.optimize_with_safe_sequences:
            utils.logger.error(f"{__name__}: Cannot optimize with both safe paths and safe sequences")
            raise ValueError("Cannot optimize with both safe paths and safe sequences")        
                
        self.safe_lists = []
        if self.external_safe_paths is not None:
            self.safe_lists = self.external_safe_paths
        elif self.optimize_with_safe_paths and not self.is_solved() and self.trusted_edges_for_safety is not None:
            start_time = time.perf_counter()
            self.safe_lists += safetypathcovers.safe_paths(
                G=self.G,
                edges_to_cover=self.trusted_edges_for_safety,
                no_duplicates=False,
                threads=self.threads,
            )
            self.solve_statistics["safe_paths_time"] = time.perf_counter() - start_time

        if self.optimize_with_safe_sequences and not self.is_solved():
            start_time = time.perf_counter()
            self.safe_lists += safetypathcovers.safe_sequences(
                G=self.G,
                edges_or_subpath_constraints_to_cover=self.trusted_edges_for_safety,
                no_duplicates=False,
                threads=self.threads,
            )
            self.solve_statistics["safe_sequences_time"] = time.perf_counter() - start_time

        if self.optimize_with_subpath_constraints_as_safe_sequences and len(self.subset_constraints) > 0 and not self.is_solved():
            if self.subpath_constraints_coverage == 1 and self.subpath_constraints_coverage_length in [1, None]:
                start_time = time.perf_counter()
                self.safe_lists += safetypathcovers.safe_sequences(
                    G=self.G,
                    edges_or_subpath_constraints_to_cover=self.subset_constraints,
                    no_duplicates=False,
                    threads=self.threads,
                )
                self.solve_statistics["optimize_with_subpath_constraints_as_safe_sequences"] = time.perf_counter() - start_time

        if self.optimize_with_safety_as_subpath_constraints:
            self.subset_constraints += self.safe_lists

    def create_solver_and_paths(self):
        """
        Creates a solver instance and encodes the paths in the graph.

        This method initializes the solver with the specified parameters and encodes the paths
        by creating variables for edges and subpaths.

        If external solution paths are provided, it skips the solver creation.

        !!! warning "Call this method before encoding other variables and constraints."
        
            Always call this method before encoding other variables and constraints on the paths.

        """
        self.solver = sw.SolverWrapper(**self.solver_options)

        self._encode_walks()

    def _encode_walks(self):
        
        # Encodes the paths in the graph by creating variables for edges and subpaths.

        # This method initializes the edge and subpath variables for the solver and adds constraints
        # to ensure the paths are valid according to the given subpath constraints and safe lists.
        
        self.edge_indexes = [
            (u, v, i) for i in range(self.k) for (u, v) in self.G.edges()
        ]
        self.path_indexes = [(i) for i in range(self.k)]
        if len(self.subset_constraints) > 0:
            self.subpath_indexes = [
                (i, j) for i in range(self.k) for j in range(len(self.subset_constraints))
            ]


        ################################
        #                              #
        #       Encoding paths         #
        #                              #
        ################################

        # The identifiers of the constraints come from https://arxiv.org/pdf/2201.10923 page 14-15

        self.edge_vars = self.solver.add_variables(self.edge_indexes, name_prefix="edge", lb=0, ub=1, var_type="integer")

        for i in range(self.k):
            
            if not self.allow_empty_paths:
                self.solver.add_constraint(
                    self.solver.quicksum(
                        self.edge_vars[(self.G.source, v, i)]
                        for v in self.G.successors(self.G.source)
                    )
                    == 1,
                    name=f"10a_i={i}",
                )
            else:
                self.solver.add_constraint(
                    self.solver.quicksum(
                        self.edge_vars[(self.G.source, v, i)]
                        for v in self.G.successors(self.G.source)
                    )
                    <= 1,
                    name=f"10a_i={i}",
                )
            # Not needed, follows from the others
            # self.solver.add_constraint(
            #     self.solver.quicksum(
            #         self.edge_vars[(u, self.G.sink, i)]
            #         for u in self.G.predecessors(self.G.sink)
            #     )
            #     == 1,
            #     name=f"10b_i={i}",
            # )

        for i in range(self.k):
            for v in self.G.nodes:  # find all edges u->v->w for v in V\{s,t}
                if v == self.G.source or v == self.G.sink:
                    continue
                self.solver.add_constraint(
                    self.solver.quicksum(self.edge_vars[(u, v, i)] for u in self.G.predecessors(v))
                    - self.solver.quicksum(self.edge_vars[(v, w, i)] for w in self.G.successors(v))
                    == 0,
                    f"10c_v={v}_i={i}",
                )

        ################################
        #                              #
        # Encoding subpath constraints #
        #                              #
        ################################

        # Example of a subpath constraint: R=[ [(1,3),(3,5)], [(0,1)] ], means that we have 2 paths to cover, the first one is 1-3-5. the second path is just a single edge 0-1

        if len(self.subset_constraints) > 0:
            self.subpaths_vars = self.solver.add_variables(
                self.subpath_indexes, name_prefix="r", lb=0, ub=1, var_type="integer")
        
            for i in range(self.k):
                for j in range(len(self.subset_constraints)):

                    if self.subpath_constraints_coverage_length is None:
                        # By default, the length of the constraints is its number of edges 
                        constraint_length = len(self.subset_constraints[j])
                        # And the fraction of edges that we need to cover is self.subpath_constraints_coverage
                        coverage_fraction = self.subpath_constraints_coverage
                        self.solver.add_constraint(
                            self.solver.quicksum(self.edge_vars[(e[0], e[1], i)] for e in self.subset_constraints[j])
                            >= constraint_length * coverage_fraction
                            * self.subpaths_vars[(i, j)],
                            name=f"7a_i={i}_j={j}",
                        )
                    else:
                        # If however we specified that the coverage fraction is in terms of edge lengths
                        # Then the constraints length is the sum of the lengths of the edges,
                        # where each edge without a length gets length 1
                        constraint_length = sum(self.G[u][v].get(self.length_attr, 1) for (u,v) in self.subset_constraints[j])
                        # And the fraction of edges that we need to cover is self.subpath_constraints_coverage_length
                        coverage_fraction = self.subpath_constraints_coverage_length
                        self.solver.add_constraint(
                            self.solver.quicksum(self.edge_vars[(e[0], e[1], i)] * self.G[e[0]][e[1]].get(self.length_attr, 1) for e in self.subset_constraints[j])
                            >= constraint_length * coverage_fraction
                            * self.subpaths_vars[(i, j)],
                            name=f"7a_i={i}_j={j}",
                        )
            for j in range(len(self.subset_constraints)):
                self.solver.add_constraint(
                    self.solver.quicksum(self.subpaths_vars[(i, j)] for i in range(self.k)) >= 1,
                    name=f"7b_j={j}",
                )

        ########################################
        #                                      #
        # Fixing variables based on safe lists #
        #                                      #
        ########################################

        if self.safe_lists is not None:
            paths_to_fix = self._get_paths_to_fix_from_safe_lists()

            if not self.optimize_with_safety_as_subpath_constraints:
                # iterating over safe lists
                for i in range(min(len(paths_to_fix), self.k)):
                    # print("Fixing variables for safe list #", i)
                    # iterate over the edges in the safe list to fix variables to 1
                    for u, v in paths_to_fix[i]:
                        self.solver.add_constraint(
                            self.edge_vars[(u, v, i)] == 1,
                            name=f"safe_list_u={u}_v={v}_i={i}",
                        )

                    if self.optimize_with_safe_zero_edges:
                        # get the endpoints of the longest safe path in the sequence
                        first_node, last_node = (
                            safetypathcovers.get_endpoints_of_longest_safe_path_in(paths_to_fix[i])
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


    def _get_paths_to_fix_from_safe_lists(self) -> list:
        
        # Returns the paths to fix based on the safe lists.
        # The method finds the longest safe list for each edge and returns the paths to fix based on the longest safe list.

        # If we have no safe lists, we return an empty list
        if self.safe_lists is None or len(self.safe_lists) == 0:
            return []

        # for i, safe_list in enumerate(self.safe_lists):
        #     utils.logger.debug(f"{__name__}: safe_list {i}: {safe_list}")        

        # utils.draw(self.G, 
        #            filename = "debug_safe_lists.pdf", 
        #            subpath_constraints = self.safe_lists)

        large_constant = 0
        if self.optimize_with_safety_from_largest_antichain:
            large_constant = self.G.number_of_edges() * self.G.number_of_edges()

        longest_safe_list = dict()
        for i, safe_list in enumerate(self.safe_lists):
            for edge in safe_list:
                if edge not in longest_safe_list:
                    longest_safe_list[edge] = i
                elif len(self.safe_lists[longest_safe_list[edge]]) < len(safe_list):
                    longest_safe_list[edge] = i

        len_of_longest_safe_list = {
            edge: large_constant + len(self.safe_lists[longest_safe_list[edge]])
            for edge in longest_safe_list
        }
        # for edge, length in len_of_longest_safe_list.items():
        #     utils.logger.debug(f"{__name__}: edge {edge} has longest safe list of length {length} at index {longest_safe_list[edge]}")

        _, edge_antichain = self.G.compute_max_edge_antichain(
            get_antichain=True, weight_function=len_of_longest_safe_list
        )
        utils.logger.debug(f"{__name__}: edge_antichain from safe lists SIZE: {len(edge_antichain)}")
        # utils.logger.debug(f"{__name__}: edge_antichain from safe lists: {len(edge_antichain)}")

        # paths_to_fix = list(
        #     map(lambda edge: self.safe_lists[longest_safe_list[edge]], edge_antichain)
        # )
        paths_to_fix = []
        for edge in edge_antichain:
            # utils.logger.debug(f"{__name__}: edge {edge} in edge_antichain, longest safe list idx: {longest_safe_list[edge]}, safe list: {self.safe_lists[longest_safe_list[edge]]}")
            paths_to_fix.append(self.safe_lists[longest_safe_list[edge]])

        utils.logger.debug(f"{__name__}: paths_to_fix from safe lists SIZE: {len(paths_to_fix)}")
        # utils.logger.debug(f"{__name__}: paths_to_fix from safe lists: {paths_to_fix}")
        
        # utils.draw(self.G, 
        #            filename = "debug_paths_to_fix.pdf", 
        #            subpath_constraints = paths_to_fix)

        return paths_to_fix
    
    def _check_valid_subset_constraints(self):
        """
        Checks if the subset constraints are valid.

        Parameters
        ----------
        - subset_constraints (list): The subset constraints to be checked.

        Returns
        ----------
        - True if the subset constraints are valid, False otherwise.

        The method checks if the subset constraints are valid by ensuring that:
        - `self.subset_constraints` is a list of lists
        - each subset is a non-empty list of tuples of nodes
        - each such tuple of nodes is an edge of the graph `self.G`
        """

        # Check that self.subset_constraints is a list of lists
        if not all(isinstance(subset, list) for subset in self.subset_constraints):
            utils.logger.error(f"{__name__}: subset_constraints must be a list of lists of edges.")
            raise ValueError("subset_constraints must be a list of lists of edges.")

        for subset in self.subset_constraints:
            # Check that each subpath has at least one edge
            if len(subset) == 0:
                utils.logger.error(f"{__name__}: subpath {subset} must have at least 1 edge.")
                raise ValueError(f"Subset {subset} must have at least 1 edge.")
            # Check that each subset is a list of tuples of two nodes (edges)
            if not all(isinstance(e, tuple) and len(e) == 2 for e in subset):
                utils.logger.error(f"{__name__}: each subset must be a list of edges, where each edge is a tuple of two nodes.")
                raise ValueError("Each subset must be a list of edges, where each edge is a tuple of two nodes.")
            # Check that each edge in the subset is in the graph
            for e in subset:
                if not self.G.has_edge(e[0], e[1]):
                    utils.logger.error(f"{__name__}: subset {subset} contains the edge {e} which is not in the graph.")
                    raise ValueError(f"Subset {subset} contains the edge {e} which is not in the graph.")


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
        utils.logger.info(f"{__name__}: solving...")

        # self.write_model(f"model-{self.id}.lp")
        start_time = time.perf_counter()
        self.solver.optimize()
        self.solve_statistics[f"milp_solve_time_for_num_paths_{self.k}"] = (
            time.perf_counter() - start_time
        )

        self.solve_statistics[f"milp_solver_status_for_num_paths_{self.k}"] = (
            self.solver.get_model_status()
        )

        if (
            self.solver.get_model_status() == "kOptimal"
            or self.solver.get_model_status() == 2
        ):
            self._is_solved = True
            utils.logger.info(f"{__name__}: solved successfully. Objective value: {self.get_objective_value()}")
            return True

        self._is_solved = False
        return False

    def check_is_solved(self):
        if not self.is_solved():
            utils.logger.error(f"{__name__}: Model not solved. If you want to solve it, call the `solve` method first.")
            raise Exception(
                "Model not solved. If you want to solve it, call the `solve` method first. \
                  If you already ran the `solve` method, then the model is infeasible, or you need to increase parameter time_limit.")
        
    def is_solved(self):
        return self._is_solved
    
    def set_solved(self):
        self._is_solved = True

    @abstractmethod
    def get_solution(self):
        """
        Implement this class in the child class to return the full solution of the model.
        The solution paths are obtained with the get_solution_paths method.
        """
        pass

    @abstractmethod
    def get_lowerbound_k(self):
        """
        Implement this class in the child class to return a lower bound on the number of solution paths to the model.
        If you have no lower bound, you should implement this method to return 1.
        """
        pass

    def get_solution_walks(self) -> list:
        """
        Retrieves the solution walks from the graph.

        This method returns the solution walks by calculating them based on the
        edge variable solutions.

        Returns
        ----------
        - A list of walks, where each walk is represented as a list of vertices.
        """

        if self.edge_vars_sol == {}:
            self.edge_vars_sol = self.solver.get_variable_values(
                "edge", [str, str, int], 
                binary_values=True,
            )

        # TODO: update this

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
                # print("Warning: No path found for path index", i)
            else:
                path = [vertex]
                while vertex != self.G.sink:
                    for out_neighbor in self.G.successors(vertex):
                        if self.edge_vars_sol[(str(vertex), str(out_neighbor), i)] == 1:
                            vertex = out_neighbor
                            break
                    path.append(vertex)
                if len(path) < 2:
                    utils.logger.error(f"{__name__}: Something went wrong, solution path {path} has less than 2 vertices. This should not happen. Make sure the stDAG has no edge from global source {self.G.source} to global sink {self.G.sink}.")
                    raise Exception(f"Something went wrong, solution path {path} has less than 2 vertices. This should not happen. Make sure the stDAG has no edge from global source {self.G.source} to global sink {self.G.sink}.")
                
                paths.append(path[1:-1])

        return paths

    @abstractmethod
    def is_valid_solution(self) -> bool:
        """
        Implement this class in the child class to perform a basic check whether the solution is valid.
        
        If you cannot perform such a check, provide an implementation that always returns True.
        """
        pass

    @abstractmethod
    def get_objective_value(self):
        """
        Implement this class in the child class to return the objective value of the model. This is needed to be able to
        compute the safe paths (i.e. those appearing any optimum solution) for any child class.

        A basic objective value is `k` (when we're trying to minimize the number of paths). If your model has a different
        objective, you should implement this method to return the objective value of the model. If your model has no objective value,
        you should implement this method to return None.
        """
        pass