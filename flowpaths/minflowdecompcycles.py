import time
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.kflowdecompcycles as kflowdecompcycles
import flowpaths.abstractwalkmodeldigraph as walkmodel
import flowpaths.utils.solverwrapper as sw
import flowpaths.utils.graphutils as gu
import flowpaths.mingenset as mgs
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import copy

class MinFlowDecompCycles(walkmodel.AbstractWalkModelDiGraph):
    """
    A class to decompose a network flow if a general directed graph into a minimum number of weighted s-t walks.
    """

    # Default optimization parameters
    use_min_gen_set_lowerbound = False
    optimize_with_given_weights = False
    optimize_with_given_weights_num_free_walks = 0
    add_min_gen_set_to_given_weights = False

    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        flow_attr_origin: str = "edge",
        weight_type: type = int,
        subset_constraints: list = [],
        subset_constraints_coverage: float = 1.0,
        elements_to_ignore: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = {},
        solver_options: dict = {},
    ):
        """
        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html), possibly with cycles.

        - `flow_attr : str`
            
            The attribute name from where to get the flow values on the edges.

        - `flow_attr_origin : str`, optional

            The origin of the flow attribute. Default is `"edge"`. Options:
            
            - `"edge"`: the flow attribute is assumed to be on the edges of the graph.
            - `"node"`: the flow attribute is assumed to be on the nodes of the graph. See [the documentation](node-expanded-digraph.md) on how node-weighted graphs are handled.

        - `weight_type : type`, optional
            
            The type of weights (`int` or `float`). Default is `int`.

        - `subset_constraints : list`, optional
            
            List of subset constraints. Default is an empty list. 
            Each subset constraint is a list of edges that must be covered by some solution walks, in any order, according 
            to the `subset_constraints_coverage` parameter (see below).

        - `subset_constraints_coverage: float`, optional
            
            Coverage fraction of the subset constraints that must be covered by some solution walk. 

            Defaults to `1.0`, meaning that 100% of the edges (or nodes, if `flow_attr_origin` is `"node"`) of
            the constraint need to be covered by some solution walk).
            See [subset constraints documentation](subset-constraints.md#3-relaxing-the-constraint-coverage)

        - `elements_to_ignore : list`, optional

            List of edges (or nodes, if `flow_attr_origin` is `"node"`) to ignore when adding constrains on flow explanation by the weighted walks. 
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `additional_starts: list`, optional
            
            List of additional start nodes of the walks. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `additional_ends: list`, optional

            List of additional end nodes of the walks. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `optimization_options : dict`, optional
            
            Dictionary with the optimization options. Default is an empty dict. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).

        Raises
        ------
        `ValueError`

        - If `weight_type` is not `int` or `float`.
        - If some edge does not have the flow attribute specified as `flow_attr`.
        - If the graph does not satisfy flow conservation on nodes different from source or sink.
        - If the graph contains edges with negative (<0) flow values.
        - If `flow_attr_origin` is not "node" or "edge".
        """

        # Handling node-weighted graphs
        self.flow_attr_origin = flow_attr_origin
        if self.flow_attr_origin == "node":
            if G.number_of_nodes() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no nodes. Please provide a graph with at least one node.")
                raise ValueError(f"The input graph G has no nodes. Please provide a graph with at least one node.")
            if len(additional_starts) + len(additional_ends) == 0:
                self.G_internal = nedg.NodeExpandedDiGraph(
                    G=G, 
                    node_flow_attr=flow_attr
                )
            else:
                self.G_internal = nedg.NodeExpandedDiGraph(
                    G=G, 
                    node_flow_attr=flow_attr,
                    additional_starts=additional_starts,
                    additional_ends=additional_ends,
                )
            subset_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subset_constraints)
            additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
            additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)
            
            edges_to_ignore_internal = self.G_internal.edges_to_ignore
            if not all(isinstance(element_to_ignore, str) for element_to_ignore in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of nodes (i.e strings), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of nodes (i.e strings), not {elements_to_ignore}")
            edges_to_ignore_internal += [self.G_internal.get_expanded_edge(node) for node in elements_to_ignore]
            edges_to_ignore_internal = list(set(edges_to_ignore_internal))

        elif self.flow_attr_origin == "edge":
            if G.number_of_edges() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
                raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
            if len(additional_starts) + len(additional_ends) > 0:
                utils.logger.error(f"additional_starts and additional_ends are not supported when flow_attr_origin is 'edge'.")
                raise ValueError(f"additional_starts and additional_ends are not supported when flow_attr_origin is 'edge'.")
            self.G_internal = G
            subset_constraints_internal = subset_constraints
            if not all(isinstance(edge, tuple) and len(edge) == 2 for edge in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
            edges_to_ignore_internal = elements_to_ignore
            additional_starts_internal = additional_starts
            additional_ends_internal = additional_ends

        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")

        self.G = self.G_internal
        self.subset_constraints = subset_constraints_internal
        self.edges_to_ignore = edges_to_ignore_internal
        self.additional_starts = additional_starts_internal
        self.additional_ends = additional_ends_internal

        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.subset_constraints_coverage = subset_constraints_coverage
        self.optimization_options = optimization_options
        self.solver_options = solver_options
        self.time_limit = self.solver_options.get("time_limit", sw.SolverWrapper.time_limit)
        self.solve_time_start = None
        self.solve_time_ilp_total = 0

        self.solve_statistics = {}
        self._solution = None
        self._lowerbound_k = None
        self._is_solved = False

        # Get the max flow value on an edge
        self.w_max = max(self.G.edges[edge][self.flow_attr] 
                          for edge in self.G.edges 
                          if self.flow_attr in self.G.edges[edge]
                          and edge not in self.edges_to_ignore) if self.G.number_of_edges() > 0 else 0

        # Internal variables
        self._generating_set = None
        self._given_weights_model: kflowdecompcycles.kFlowDecompCycles | None = None
        self._mingenset_model: mgs.MinGenSet | None = None
        self._source_flow = None

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}")

    def solve(self) -> bool:
        """
        Attempts to solve the flow decomposition problem using a model with varying number of walks.

        This method iterates over a range of possible walk numbers, creating and solving a flow decomposition model for each count.
        If a solution is found, it stores the solution and relevant statistics, and returns True. If no solution is found after
        iterating through all possible walk numbers, it returns False.

        Returns:
            bool: True if a solution is found, False otherwise.

        Note:
            This overloads the `solve()` method from `AbstractWalkModelDiGraph` class.
        """
        self.solve_time_start = time.perf_counter()
        utils.logger.info(f"{__name__}: starting to solve the MinFlowDecompCycles model for graph id = {utils.fpid(self.G)}")

        if self.optimization_options.get("optimize_with_given_weights", MinFlowDecompCycles.optimize_with_given_weights):            
            self._solve_with_given_weights()

        for i in range(self.get_lowerbound_k(), self.G.number_of_edges()):
            utils.logger.info(f"{__name__}: solving with k = {i}")
            fd_model = None
            # Checking if we have already found a solution with the same number of walks
            # via the min gen set and given weights approach
            if self._given_weights_model is not None and self._given_weights_model.is_solved():
                if len(self._given_weights_model.get_solution(remove_empty_walks=True)["walks"]) == i:
                    fd_model = self._given_weights_model

            if fd_model is None:
                fd_solver_options = copy.deepcopy(self.solver_options)
                fd_solver_options["time_limit"] = self.time_limit - self.solve_time_elapsed
                fd_model = kflowdecompcycles.kFlowDecompCycles(
                    G=self.G,
                    flow_attr=self.flow_attr,
                    k=i,
                    weight_type=self.weight_type,
                    subset_constraints=self.subset_constraints,
                    subset_constraints_coverage=self.subset_constraints_coverage,
                    elements_to_ignore=self.edges_to_ignore,
                    additional_starts=self.additional_starts,
                    additional_ends=self.additional_ends,
                    optimization_options=self.optimization_options,
                    solver_options=fd_solver_options,
                )
                fd_model.solve()

            self.solve_statistics = fd_model.solve_statistics
            self.solve_time_ilp_total += self.solve_statistics.get("solve_time_ilp", 0)
            self.solve_statistics["solve_time"] = self.solve_time_elapsed
            self.solve_statistics["solve_time_ilp"] = self.solve_time_ilp_total
            self.solve_statistics["min_gen_set_solve_time"] = self._mingenset_model.solve_statistics.get("total_solve_time", 0) if self._mingenset_model is not None else 0

            # If the previous run exceeded the time limit, 
            # we still stop the search, even if we might have managed to solve it
            if self.solve_time_elapsed > self.time_limit:
                return False

            if fd_model.is_solved():
                self._solution = fd_model.get_solution(remove_empty_walks=True)
                if self.flow_attr_origin == "node":
                    # If the flow_attr_origin is "node", we need to convert the solution walks from the expanded graph to walks in the original graph.
                    self._solution["_walks_internal"] = self._solution["walks"]
                    self._solution["walks"] = self.G_internal.get_condensed_paths(self._solution["walks"])
                self.set_solved()
                self.fd_model = fd_model
                return True
            elif fd_model.solver.get_model_status() == sw.SolverWrapper.infeasible_status:
                utils.logger.info(f"{__name__}: model is infeasible for k = {i}")
            else:
                # If the model is not solved and the status is not infeasible,
                # it means that the solver stopped because of an unexpected termination,
                # thus we cannot conclude that the model is infeasible.
                # In this case, we stop the search.
                return False

        return False

    def _get_source_flow(self):
        if self._source_flow is None:
            self._source_flow = 0
            for v in self.G.nodes():
                out_flow = sum(data.get(self.flow_attr, 0) for _, _, data in self.G.out_edges(v, data=True))
                in_flow  = sum(data.get(self.flow_attr, 0) for _, _, data in self.G.in_edges(v, data=True))
                if out_flow > in_flow:
                    self._source_flow = self._source_flow + (out_flow - in_flow)
            utils.logger.debug(f"{__name__}: source_flow = {self._source_flow}")
            return self._source_flow
        else:
            return self._source_flow

    def _get_lowerbound_with_min_gen_set(self) -> int:

        min_gen_set_start_time = time.perf_counter()
        all_weights = list(set({self.G.edges[e][self.flow_attr] for e in self.G.edges() if self.flow_attr in self.G.edges[e]}))
        # Get the source_flow as the sum of the out_flow - in_flow, for all nodes
        source_flow = self._get_source_flow()
        current_lowerbound_k = self._lowerbound_k if self._lowerbound_k is not None else 1
        min_gen_set_lowerbound = None

        mingenset_solver_options = copy.deepcopy(self.solver_options)
        if "time_limit" in mingenset_solver_options:
            mingenset_solver_options["time_limit"] = self.time_limit - self.solve_time_elapsed

        self._mingenset_model = mgs.MinGenSet(
            numbers = all_weights, 
            total = source_flow, 
            weight_type = self.weight_type,
            max_multiplicity=self.w_max,
            lowerbound = current_lowerbound_k,
            remove_complement_values=True,
            remove_sums_of_two=True,
            solver_options = mingenset_solver_options,
            )
        self._mingenset_model.solve()
    
        # If we solved the min gen set problem, we store it and the model, and return the number of elements in the generating set
        if self._mingenset_model.is_solved():        
            self._generating_set = self._mingenset_model.get_solution()
            min_gen_set_lowerbound = len(self._generating_set)
            utils.logger.info(f"{__name__}: found a min gen set solution with {min_gen_set_lowerbound} elements ({self._generating_set})")
            self._mingenset_model.solve_statistics["total_solve_time"] = time.perf_counter() - min_gen_set_start_time
        else:
            utils.logger.error(f"{__name__}: did NOT find a min gen set solution")
            self._mingenset_model = None

        return min_gen_set_lowerbound

    def _solve_with_given_weights(self) -> bool:

        given_weights_start_time = time.perf_counter()

        all_weights = set({self.G.edges[e][self.flow_attr] for e in self.G.edges() if self.flow_attr in self.G.edges[e]})
        all_weights_list = list(all_weights)
        
        # We call this so that the generating set is computed and stored in the class, if this optimization is activated
        _ = self.get_lowerbound_k()

        if self._generating_set is not None:
            if self.optimization_options.get("add_min_gen_set_to_given_weights", MinFlowDecompCycles.add_min_gen_set_to_given_weights):
                all_weights.update(self._generating_set)
            all_weights_list = list(all_weights)

        given_weights_optimization_options = copy.deepcopy(self.optimization_options)
        given_weights_optimization_options["optimize_with_safe_sequences"] = False
        given_weights_optimization_options["optimize_with_safety_as_subset_constraints"] = False
        given_weights_optimization_options["optimize_with_max_safe_antichain_as_subset_constraints"] = True
        given_weights_optimization_options["allow_empty_walks"] = True
        given_weights_optimization_options["given_weights"] = all_weights_list
        utils.logger.info(f"{__name__}: Solving with given weights = {sorted(given_weights_optimization_options['given_weights'])}")

        given_weights_kfd_solver_options = copy.deepcopy(self.solver_options)
        if "time_limit" in given_weights_kfd_solver_options:
            given_weights_kfd_solver_options["time_limit"] = self.time_limit - self.solve_time_elapsed

        given_weights_kfd_solver = kflowdecompcycles.kFlowDecompCycles(
            G=self.G,
            k = len(given_weights_optimization_options["given_weights"]) + self.optimization_options.get("optimize_with_given_weights_num_free_walks", MinFlowDecompCycles.optimize_with_given_weights_num_free_walks),
            flow_attr=self.flow_attr,
            weight_type=self.weight_type,
            subset_constraints=self.subset_constraints,
            subset_constraints_coverage=self.subset_constraints_coverage,
            elements_to_ignore=self.edges_to_ignore,
            optimization_options=given_weights_optimization_options,
            solver_options=given_weights_kfd_solver_options,
            )
        given_weights_kfd_solver.solve()

        if given_weights_kfd_solver.is_solved():
            self._given_weights_model = given_weights_kfd_solver
            sol = self._given_weights_model.get_solution(remove_empty_walks=True)
            utils.logger.info(f"{__name__}: found an MFD solution with given weights in {len(sol['walks'])} walks weights {sol['weights']}")
            self._given_weights_model.solve_statistics["given_weights_solve_time"] = time.perf_counter() - given_weights_start_time
        else:
            utils.logger.info(f"{__name__}: did NOT found an MFD solution with given weights")


    @property
    def solve_time_elapsed(self):
        """
        Returns the elapsed time since the start of the solve process.

        Returns
        -------
        - `float`
        
            The elapsed time in seconds.
        """
        return time.perf_counter() - self.solve_time_start if self.solve_time_start is not None else 0

    def get_solution(self):
        """
        Retrieves the solution for the flow decomposition problem.

        Returns
        -------
        - `solution: dict`

            A dictionary containing the solution walks (key `"walks"`) and their corresponding weights (key `"weights"`).

        Raises
        -------
        - `exception` If model is not solved.
        """
        self.check_is_solved()
        return self._solution
    
    def get_objective_value(self):

        self.check_is_solved()

        # Number of walks
        return len(self._solution["walks"])

    def is_valid_solution(self) -> bool:

        return self.fd_model.is_valid_solution()
    
    def get_lowerbound_k(self):

        utils.logger.info(f"{__name__}: computing lowerbound_k")

        if self._lowerbound_k != None:
            return self._lowerbound_k
        
        stDiGraph = stdigraph.stDiGraph(self.G)

        # Checking if we have been given some lowerbound to start with
        self._lowerbound_k = self.optimization_options.get("lowerbound_k", 1)

        self._lowerbound_k = max(self._lowerbound_k, stDiGraph.get_width(edges_to_ignore=self.edges_to_ignore))

        if self.optimization_options.get("use_min_gen_set_lowerbound", MinFlowDecompCycles.use_min_gen_set_lowerbound):  
            mingenset_lowerbound = self._get_lowerbound_with_min_gen_set()
            if mingenset_lowerbound is not None:
                self._lowerbound_k = max(self._lowerbound_k, mingenset_lowerbound)

        return self._lowerbound_k
