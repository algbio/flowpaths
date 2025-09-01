import time
import copy
import networkx as nx
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils as utils
import flowpaths.utils.solverwrapper as sw
import flowpaths.stdag as stdag
import flowpaths.kpathcover as kpathcover
import flowpaths.nodeexpandeddigraph as nedg
from copy import deepcopy

class MinPathCover(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        cover_type: str = "edge",
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        length_attr: str = None,
        elements_to_ignore: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = {},
        solver_options: dict = {},
    ):
        """
        This class finds a minimum number of paths covering the edges of a directed acyclic graph (DAG) -- and generalizations of this problem, see the parameters below.

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed acyclic graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html).

        - `cover_type: str`, optional

            The elements of the graph to cover. Default is `"edge"`. Options:
            
            - `"edge"`: cover the edges of the graph. This is the default.
            - `"node"`: cover the nodes of the graph.

        - `subpath_constraints: list`, optional
            
            List of subpath constraints. Default is an empty list. 
            Each subpath constraint is a list of edges that must be covered by some solution path, according 
            to the `subpath_constraints_coverage` or `subpath_constraints_coverage_length` parameters (see below).

        - `subpath_constraints_coverage: float`, optional
            
            Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            
            Defaults to `1.0`, meaning that 100% of the edges (or nodes, if `flow_attr_origin` is `"node"`) of 
            the constraint need to be covered by some solution path). 
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `subpath_constraints_coverage_length: float`, optional
            
            Coverage length of the subpath constraints. Default is `None`. If set, this overrides `subpath_constraints_coverage`, 
            and the coverage constraint is expressed in terms of the subpath constraint length. 
            `subpath_constraints_coverage_length` is then the fraction of the total length of the constraint (specified via `length_attr`) needs to appear in some solution path.
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `length_attr: str`, optional
            
            The attribute name from where to get the edge lengths (or node length, if `flow_attr_origin` is `"node"`). Defaults to `None`.
            
            - If set, then the subpath lengths (above) are in terms of the edge/node lengths specified in the `length_attr` field of each edge/node.
            - If set, and an edge/node has a missing edge length, then it gets length 1.

        - `elements_to_ignore: list`, optional

            List of graph elements to ignore when adding constrains on flow explanation by the weighted paths.
            These elements are either edges or nodes, depending on the `cover_type` parameter.
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `optimization_options: dict`, optional
            
            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional
            
            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

        """

        # Handling node-weighted graphs
        self.cover_type = cover_type
        if self.cover_type == "node":
            if G.number_of_nodes() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no nodes. Please provide a graph with at least one node.")
                raise ValueError(f"The input graph G has no nodes. Please provide a graph with at least one node.")
            # NodeExpandedDiGraph needs to have flow_attr on edges, otherwise it will add the edges to edges_to_ignore
            G_with_flow_attr = deepcopy(G)
            node_flow_attr = str(id(G_with_flow_attr)) + "_flow_attr"
            for node in G_with_flow_attr.nodes():
                G_with_flow_attr.nodes[node][node_flow_attr] = 0 # any dummy value
            self.G_internal = nedg.NodeExpandedDiGraph(G_with_flow_attr, node_flow_attr=node_flow_attr)
            subpath_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subpath_constraints)
            
            edges_to_ignore_internal = self.G_internal.edges_to_ignore
            if not all(isinstance(node, str) for node in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of nodes, i.e. strings, not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of nodes, i.e. strings, not {elements_to_ignore}")
            edges_to_ignore_internal += [self.G_internal.get_expanded_edge(node) for node in elements_to_ignore]
            
            additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
            additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)
        elif self.cover_type == "edge":
            if G.number_of_edges() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
                raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
            self.G_internal = G
            subpath_constraints_internal = subpath_constraints
            
            if not all(isinstance(edge, tuple) and len(edge) == 2 for edge in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of edges, i.e. tuples of nodes, not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of edges, i.e. tuples of nodes, not {elements_to_ignore}")
            edges_to_ignore_internal = elements_to_ignore

            additional_starts_internal = additional_starts
            additional_ends_internal = additional_ends
        else:
            utils.logger.error(f"cover_type must be either 'node' or 'edge', not {self.cover_type}")
            raise ValueError(f"cover_type must be either 'node' or 'edge', not {self.cover_type}")

        self.G = stdag.stDAG(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subpath_constraints = subpath_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)

        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.length_attr = length_attr
        
        self.additional_starts = additional_starts
        self.additional_ends = additional_ends

        self._solution = None
        self._lowerbound_k = None
        self._is_solved = None
        self.model = None
        
        self.solve_statistics = {}
        self.optimization_options = optimization_options
        self.solver_options = solver_options
        self.time_limit = self.solver_options.get("time_limit", sw.SolverWrapper.time_limit)
        self.solve_time_start = None

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}")

    def solve(self) -> bool:

        self.solve_time_start = time.perf_counter()
        
        for i in range(self.get_lowerbound_k(), self.G.number_of_edges()):
            utils.logger.info(f"{__name__}: iteration with k = {i}")

            i_solver_options = copy.deepcopy(self.solver_options)
            if "time_limit" in i_solver_options:
                i_solver_options["time_limit"] = self.time_limit - self.solve_time_elapsed

            model = kpathcover.kPathCover(
                        G=self.G,
                        k=i,
                        subpath_constraints=self.subpath_constraints,
                        subpath_constraints_coverage=self.subpath_constraints_coverage,
                        subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                        length_attr=self.length_attr,
                        elements_to_ignore=self.edges_to_ignore,
                        additional_starts=self.additional_starts,
                        additional_ends=self.additional_ends,
                        optimization_options=self.optimization_options,
                        solver_options=i_solver_options,
                    )
            model.solve()

            if model.is_solved():
                self._solution = model.get_solution()
                self.set_solved()
                self.solve_statistics = model.solve_statistics
                self.solve_statistics["mpc_solve_time"] = time.perf_counter() - self.solve_time_start
                self.model = model
                return True
            elif model.solver.get_model_status() != sw.SolverWrapper.infeasible_status:
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
        Get the solution of the Min Path Cover model, as dict with unique key `"paths"`.
        """
        self.check_is_solved()
        return self._solution
    
    def get_objective_value(self):

        self.check_is_solved()

        # Number of paths
        return len(self._solution["paths"])

    def is_valid_solution(self) -> bool:
        return self.model.is_valid_solution()
    
    def get_lowerbound_k(self):

        if self._lowerbound_k is None:
            stG = stdag.stDAG(self.G)
            self._lowerbound_k = stG.get_width(edges_to_ignore=self.edges_to_ignore)

        return self._lowerbound_k