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
    A class to decompose a network flow if a general directed graph into a minimum number of weighted s-t paths.
    """

    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        flow_attr_origin: str = "edge",
        weight_type: type = float,
        subset_constraints: list = [],
        subset_constraints_coverage: float = 1.0,
        elements_to_ignore: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = {},
        solver_options: dict = {},
    ):
        """
        Initialize the Minimum Flow Decomposition model, minimizing the number of walks.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed graph, as networkx DiGraph, possibly with cycles.

        - `flow_attr : str`
            
            The attribute name from where to get the flow values on the edges.

        - `flow_attr_origin : str`, optional

            The origin of the flow attribute. Default is `"edge"`. Options:
            
            - `"edge"`: the flow attribute is assumed to be on the edges of the graph.
            - `"node"`: the flow attribute is assumed to be on the nodes of the graph. See [the documentation](node-expanded-digraph.md) on how node-weighted graphs are handled.

        - `weight_type : type`, optional
            
            The type of weights (`int` or `float`). Default is `float`.

        - `subset_constraints : list`, optional
            
            List of subset constraints. Default is an empty list. 
            Each subset constraint is a list of edges that must be covered by some solution path, according 
            to the `subset_constraints_coverage` or `subset_constraints_coverage_length` parameters (see below).

        - `subset_constraints_coverage: float`, optional
            
            Coverage fraction of the subset constraints that must be covered by some solution paths. 
            
            Defaults to `1.0`, meaning that 100% of the edges (or nodes, if `flow_attr_origin` is `"node"`) of 
            the constraint need to be covered by some solution path). 
            See [subset constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `elements_to_ignore : list`, optional

            List of edges (or nodes, if `flow_attr_origin` is `"node"`) to ignore when adding constrains on flow explanation by the weighted paths. 
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md). **You can set this only if `flow_attr_origin` is `"node"`**.

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md). **You can set this only if `flow_attr_origin` is `"node"`**.

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

        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")

        self.G = self.G_internal
        self.subset_constraints = subset_constraints_internal
        self.edges_to_ignore = edges_to_ignore_internal
        
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.subset_constraints_coverage = subset_constraints_coverage
        self.optimization_options = optimization_options
        self.solver_options = solver_options
        self.time_limit = self.solver_options.get("time_limit", sw.SolverWrapper.time_limit)
        self.solve_time_start = None

        self.solve_statistics = {}
        self._solution = None
        self._lowerbound_k = None
        self._is_solved = None

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}")

    def solve(self) -> bool:
        """
        Attempts to solve the flow decomposition problem using a model with varying number of paths.

        This method iterates over a range of possible path numbers, creating and solving a flow decomposition model for each count.
        If a solution is found, it stores the solution and relevant statistics, and returns True. If no solution is found after
        iterating through all possible path counts, it returns False.

        Returns:
            bool: True if a solution is found, False otherwise.

        Note:
            This overloads the `solve()` method from `AbstractWalkModelDiGraph` class.
        """
        self.solve_time_start = time.perf_counter()

        for i in range(self.get_lowerbound_k(), self.G.number_of_edges()):
            utils.logger.info(f"{__name__}: solving with k = {i}")

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
                optimization_options=self.optimization_options,
                solver_options=fd_solver_options,
            )
            fd_model.solve()

            # If the previous run exceeded the time limit, 
            # we still stop the search, even if we might have managed to solve it
            if self.solve_time_elapsed > self.time_limit:
                return False

            if fd_model.is_solved():
                self._solution = fd_model.get_solution(remove_empty_paths=True)
                if self.flow_attr_origin == "node":
                    # If the flow_attr_origin is "node", we need to convert the solution walks from the expanded graph to walks in the original graph.
                    self._solution["_walks_internal"] = self._solution["walks"]
                    self._solution["walks"] = self.G_internal.get_condensed_paths(self._solution["walks"])
                self.set_solved()
                self.solve_statistics = fd_model.solve_statistics
                self.solve_statistics["mfd_solve_time"] = time.perf_counter() - self.solve_time_start
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

        if self._lowerbound_k != None:
            return self._lowerbound_k
        
        stDiGraph = stdigraph.stDiGraph(self.G)

        # Checking if we have been given some lowerbound to start with
        self._lowerbound_k = self.optimization_options.get("lowerbound_k", 1)

        self._lowerbound_k = max(self._lowerbound_k, stDiGraph.get_width(edges_to_ignore=self.edges_to_ignore))

        return self._lowerbound_k
