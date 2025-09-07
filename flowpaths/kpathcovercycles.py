import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.abstractwalkmodeldigraph as walkmodel
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
from copy import deepcopy
import time

class kPathCoverCycles(walkmodel.AbstractWalkModelDiGraph):
    def __init__(
        self,
        G: nx.DiGraph,
        k: int = None,
        cover_type: str = "edge",
        subset_constraints: list = [],
        subset_constraints_coverage: float = 1.0,
        elements_to_ignore: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = None,
        solver_options: dict = {},
    ):
        """
        This class finds, if possible, `k` walks covering the edges of a directed graph, possibly with cycles -- and generalizations of this problem, see the parameters below.

        Moreover, among all such walk covers, it finds minimizing the sum of the lengths of the walks (in terms of total number of edges).

        Parameters
        ----------
        - `G: nx.DiGraph`
            
            The input directed graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html), which can have cycles.

        - `k: int`
            
            The number of walks to decompose in.

        - `cover_type : str`, optional

            The elements of the graph to cover. Default is `"edge"`. Options:
            
            - `"edge"`: cover the edges of the graph. This is the default.
            - `"node"`: cover the nodes of the graph.

         - `subset_constraints: list`, optional
            
            List of subset constraints. Default is an empty list. 
            Each subset constraint is a list of edges that must be covered by some solution walk, in any order, according 
            to the `subset_constraints_coverage` parameter (see below).

        - `subset_constraints_coverage: float`, optional

            Coverage fraction of the subset constraints that must be covered by some solution walk.

            Defaults to `1.0`, meaning that 100% of the edges (or nodes, if `flow_attr_origin` is `"node"`) of
            the constraint need to be covered by some solution walk).
            See [subset constraints documentation](subset-constraints.md#3-relaxing-the-constraint-coverage)
        
        - `elements_to_ignore: list`, optional

            List of edges (or nodes, if `flow_attr_origin` is `"node"`) to ignore when adding constrains on flow explanation by the weighted paths. 
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)
        
        - `additional_starts: list`, optional
            
            List of additional start nodes of the walks. Default is an empty list.

        - `additional_ends: list`, optional

            List of additional end nodes of the walks. Default is an empty list.

        - `optimization_options: dict`, optional

            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options: dict`, optional

            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).

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
            subset_constraints_internal = self.G_internal.get_expanded_subpath_constraints(subset_constraints)
            additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
            additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)

            if not all(isinstance(element_to_ignore, str) for element_to_ignore in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of nodes (i.e strings), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of nodes (i.e strings), not {elements_to_ignore}")
            edges_to_ignore_internal = self.G_internal.edges_to_ignore
            edges_to_ignore_internal += [self.G_internal.get_expanded_edge(node) for node in elements_to_ignore]
            edges_to_ignore_internal = list(set(edges_to_ignore_internal))

        elif self.cover_type == "edge":
            if G.number_of_edges() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
                raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
            self.G_internal = G
            subset_constraints_internal = subset_constraints
            if not all(isinstance(edge, tuple) and len(edge) == 2 for edge in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
            edges_to_ignore_internal = elements_to_ignore
            additional_starts_internal = additional_starts
            additional_ends_internal = additional_ends
        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.cover_type}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.cover_type}")

        self.G = stdigraph.stDiGraph(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
        self.subset_constraints = subset_constraints_internal
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)

        self.k = k
        self.subset_constraints_coverage = subset_constraints_coverage
        
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}
        self.solve_time_start = time.perf_counter()
        self.optimization_options = optimization_options.copy() if optimization_options else {}
        self.optimization_options["trusted_edges_for_safety"] = set(e for e in self.G.edges() if e not in self.edges_to_ignore)
        
        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            G=self.G,
            k=self.k,
            max_edge_repetition=self.G.number_of_edges() * self.G.number_of_nodes(),
            subset_constraints=self.subset_constraints,
            subset_constraints_coverage=self.subset_constraints_coverage,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics
        )

        # This method is called from the super class AbstractPathModelDiGraph
        self.create_solver_and_walks()

        # This method is called from the current class to encode the path cover
        self._encode_walk_cover()

        # This method is called from the current class to encode the objective function
        self._encode_objective()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_walk_cover(self):
        
        subset_constraint_edges = set()
        for subset_constraint in self.subset_constraints:
            for edge in zip(subset_constraint[:-1], subset_constraint[1:]):
                subset_constraint_edges.add(edge)

        for u, v in self.G.edges():
            if (u, v) in self.edges_to_ignore:
                continue
            if self.subset_constraints_coverage == 1 and (u, v) in subset_constraint_edges:
                continue
            
            # We require that self.edge_vars[(u, v, i)] is 1 for at least one i
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.edge_vars[(u, v, i)]
                    for i in range(self.k)
                ) >= 1,
                name=f"cover_u={u}_v={v}",
            )

    def _encode_objective(self):

        # Minimize the total number of edges in the walks, otherwise, e.g. 
        # also walk going around a cycle multiple times and covering it multiple times are valid solutions,
        # but they are not desirable.
        
        self.solver.set_objective(
            self.solver.quicksum(
                self.edge_vars[(u, v, i)]
                for (u, v) in self.G.edges()
                for i in range(self.k)
            ),
            sense="minimize"
        )

    def get_solution(self):
        """
        Retrieves the solution for problem.

        If the solution has already been computed and cached as `self._solution`, it returns the cached solution.
        Otherwise, it checks if the problem has been solved, computes the solution walks
        and caches the solution.

        !!! warning "Warning"
            Make sure you called `.solve()` before calling this method.

        Returns
        -------
        - `solution: dict`

            A dictionary containing the solution walks (key `"walks"`).

        Raises
        -------
        - `exception` If model is not solved.
        """

        if self._solution is None:
            self.check_is_solved()

            if self.cover_type == "edge":
                self._solution = {
                    "walks": self.get_solution_walks(),
                    }
            elif self.cover_type == "node":
                self._solution = {
                    "_walks_internal": self.get_solution_walks(),
                    "walks": self.G_internal.get_condensed_paths(self.get_solution_walks()),
                    }

        return self._solution

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

        if self._solution is None:
            utils.logger.error(f"{__name__}: Solution is not available. Call get_solution() first.")
            raise ValueError("Solution is not available. Call get_solution() first.")

        solution_walks = self._solution.get("_walks_internal", self._solution["walks"])
        solution_walks_of_edges = [
            [(walk[i], walk[i + 1]) for i in range(len(walk) - 1)]
            for walk in solution_walks
        ]

        covered_by_walks = {(u, v): 0 for (u, v) in self.G.edges()}
        for walk in solution_walks_of_edges:
            for e in walk:
                if e in covered_by_walks:
                    covered_by_walks[e] += 1

        for u, v in self.G.edges():
            if (u,v) not in self.edges_to_ignore:
                if covered_by_walks[(u, v)] == 0: 
                    return False

        return True

    def get_objective_value(self):

        self.check_is_solved()

        return self.k
    
    def get_lowerbound_k(self):

        if self._lowerbound_k is None:
            self._lowerbound_k = self.G.get_width(edges_to_ignore=self.edges_to_ignore)

        return self._lowerbound_k