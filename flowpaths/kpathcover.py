import time
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.utils.graphutils as gu
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils.safetyflowdecomp as sfd
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
from copy import deepcopy

class kPathCover(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        k: int,
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
        This class finds, if possible, `k` paths covering the edges of a directed acyclic graph (DAG) -- and generalizations of this problem, see the parameters below.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed acyclic graph, as networkx DiGraph.

        - `k: int`
            
            The number of paths to decompose in.

        - `cover_type : str`, optional

            The elements of the graph to cover. Default is `"edge"`. Options:
            
            - `"edge"`: cover the edges of the graph. This is the default.
            - `"node"`: cover the nodes of the graph.

        - `subpath_constraints : list`, optional
            
            List of subpath constraints. Default is an empty list. 
            Each subpath constraint is a list of edges that must be covered by some solution path, according 
            to the `subpath_constraints_coverage` or `subpath_constraints_coverage_length` parameters (see below).

        - `subpath_constraints_coverage : float`, optional
            
            Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            
            Defaults to `1.0` (meaning that 100% of the edges of the constraint need to be covered by some solution path). See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `subpath_constraints_coverage_length : float`, optional
            
            Coverage length of the subpath constraints. Default is `None`. If set, this overrides `subpath_constraints_coverage`, 
            and the coverage constraint is expressed in terms of the subpath constraint length. 
            `subpath_constraints_coverage_length` is then the fraction of the total length of the constraint (specified via `length_attr`) needs to appear in some solution path.
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `length_attr : str`, optional
            
            Attribute name for edge lengths. Default is `None`.

        - `elements_to_ignore : list`, optional

            List of graph elements to ignore when adding constrains on flow explanation by the weighted paths.
            These elements are either edges or nodes, depending on the `cover_type` parameter.
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `additional_starts: list`, optional
            
            List of additional start nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `additional_ends: list`, optional
            
            List of additional end nodes of the paths. Default is an empty list. See [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `optimization_options : dict`, optional
            
            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

        """

        # Handling node-weighted graphs
        self.cover_type = cover_type
        if self.cover_type == "node":
            # NodeExpandedDiGraph needs to have flow_attr on edges, otherwise it will add the edges to edges_to_ignore
            graph_attr = deepcopy(G)
            node_flow_attr = id(graph_attr) + "_flow_attr"
            for node in graph_attr.nodes():
                graph_attr.nodes[node][node_flow_attr] = 0 # any dummy value
            self.G_internal = nedg.NodeExpandedDiGraph(G, node_flow_attr=node_flow_attr)
            subpath_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subpath_constraints)
            edges_to_ignore_internal = self.G_internal.edges_to_ignore
            # If we have some nodes to ignore (via elements_to_ignore), we need to add them to the edges_to_ignore_internal
            
            if not all(isinstance(node, str) for node in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of nodes, i.e. strings, not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of nodes, i.e. strings, not {elements_to_ignore}")
            edges_to_ignore_internal += [self.G_internal.get_expanded_edge(node) for node in elements_to_ignore]
            
            additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
            additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)
        elif self.cover_type == "edge":
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

        self.G = stdigraph.stDiGraph(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subpath_constraints = subpath_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)

        self.k = k
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.length_attr = length_attr

        self.__solution = None
        self.__lowerbound_k = None
        
        self.solve_statistics = {}
        self.optimization_options = optimization_options.copy() if optimization_options else {}
        self.optimization_options["trusted_edges_for_safety"] = set(e for e in self.G.edges() if e not in self.edges_to_ignore)

        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            G=self.G, 
            k=self.k,
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            length_attr=self.length_attr, 
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics,
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class to encode the path cover
        self.__encode_path_cover()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def __encode_path_cover(self):
        
        subpath_constraint_edges = set()
        for subpath_constraint in self.subpath_constraints:
            for edge in zip(subpath_constraint[:-1], subpath_constraint[1:]):
                subpath_constraint_edges.add(edge)

        # We encode that for each edge (u,v), the sum of the weights of the paths going through the edge is equal to the flow value of the edge.
        for u, v in self.G.edges():
            if (u, v) in self.edges_to_ignore:
                continue
            if self.subpath_constraints_coverage == 1 and (u, v) in subpath_constraint_edges:
                continue
            
            # We require that  self.edge_vars[(u, v, i)] is 1 for at least one i
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.edge_vars[(u, v, i)]
                    for i in range(self.k)
                ) >= 1,
                name=f"cover_u={u}_v={v}",
            )

    def get_solution(self):
        """
        Retrieves the solution for the k-path cover problem.

        Returns
        -------
        - `solution: dict`
        
            A dictionary containing the solution paths, under key `"paths"`.

        Raises
        ------
        - `exception` If model is not solved.
        """

        if self.__solution is None:
            self.check_is_solved()
            
            if self.cover_type == "edge":
                self.__solution = {
                    "paths": self.get_solution_paths(),
                }
            elif self.cover_type == "node":
                self.__solution = {
                    "_paths_internal": self.get_solution_paths(),
                    "paths": self.G_internal.get_condensed_paths(self.get_solution_paths()),
                }
            
        return self.__solution

    def is_valid_solution(self):
        """
        Checks if the solution is valid, meaning it covers all required edges.

        Raises
        ------
        - ValueError: If the solution is not available (i.e., self.solution is None).

        Returns
        -------
        - bool: True if the solution is valid, False otherwise.

        Notes
        -------
        - get_solution() must be called before this method.
        """

        if self.__solution is None:
            utils.logger.error(f"{__name__}: Solution is not available. Call get_solution() first.")
            raise ValueError("Solution is not available. Call get_solution() first.")

        solution_paths = self.__solution.get("_paths_internal", self.__solution["paths"])
        solution_paths_of_edges = [
            [(path[i], path[i + 1]) for i in range(len(path) - 1)]
            for path in solution_paths
        ]

        covered_by_paths = {(u, v): 0 for (u, v) in self.G.edges()}
        for path in solution_paths_of_edges:
            for e in path:
                if e in covered_by_paths:
                    covered_by_paths[e] += 1

        for u, v in self.G.edges():
            if (u,v) not in self.edges_to_ignore:
                if covered_by_paths[(u, v)] == 0: 
                    return False

        return True
    
    def get_objective_value(self):
        
        self.check_is_solved()

        return self.k
    
    def get_lowerbound_k(self):

        if self.__lowerbound_k is None:
            self.__lowerbound_k = self.G.get_width(edges_to_ignore=self.edges_to_ignore)
        
        return self.__lowerbound_k