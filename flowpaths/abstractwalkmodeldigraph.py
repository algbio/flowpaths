import flowpaths.stdigraph as stdigraph
from flowpaths.utils import safetypathcoverscycles
from flowpaths.utils import solverwrapper as sw
import flowpaths.utils as utils
import networkx as nx
import time
import copy
from abc import ABC, abstractmethod

class AbstractWalkModelDiGraph(ABC):
    # storing some defaults
    optimize_with_safe_sequences = True
    optimize_with_safe_sequences_allow_geq_constraints = True
    optimize_with_safe_sequences_fix_via_bounds = False
    optimize_with_safe_sequences_fix_zero_edges = False
    # TODO: optimize_with_subset_constraints_as_safe_sequences = True
    optimize_with_safety_as_subset_constraints = False
    optimize_with_max_safe_antichain_as_subset_constraints = False
    allow_empty_walks = False
    allow_empty_walks = False

    def __init__(
        self,
        G: stdigraph.stDiGraph,
        k: int,
        max_edge_repetition: int = 1,
        max_edge_repetition_dict: dict = None,
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

            The directed graph to be used, possibly with cycles. Create it using the [`stDiGraph` class](stdigraph.md).

        - `k: int`
            
            The number of s-t walks to be modeled.

        - `max_edge_repetition: int`, optional

            The maximum number of times an edge can be used in a walk. Defaults to 1.

        - `max_edge_repetition_dict: dict`, optional

                A per-edge upper bound mapping that overrides `max_edge_repetition` on a per-edge basis.
                Keys are edges `(u, v)` from `G.edges()` and values are non-negative integers specifying
                the maximum number of times that edge can be used within a single walk (layer).

                Requirements and behavior:
                - If provided, it must contain an entry for every edge in `G` (missing entries raise `ValueError`).
                - Values should be integers ≥ 0; a value of 0 forbids the edge in any walk.
                - When both `max_edge_repetition` and this dict are provided, the dict takes precedence per edge.
                - These bounds are applied per layer i and are used to set the variable upper bounds and related
                    big-M constants in the model.

        - `subset_constraints: list`, optional
            
            A list of lists, where each list is a *set* of edges (not necessarily contiguous). Defaults to an empty list.

            Each set of edges must appear in at least one solution path; if you also pass `subset_constraints_coverage`, 
            then each set of edges must appear in at least `subset_constraints_coverage` fraction of some solution walk, see below.

        - `subset_constraints_coverage: float`, optional
            
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
                    2. Every edge in `trusted_edges_for_safety` appears in some solution walk, for all solutions. This naturally holds for several problems, for example [Minimum Flow Decomposition](minimum-flow-decomposition-cycles.md) or [k-Minimum Path Error](k-min-path-error-cycles.md) where in fact, under default settings, **all** edges appear in all solutions.

        - `solver_options: dict`, optional
            
            Dictionary of solver options. Defaults to `{}`, in which case the default values are used. 
            See the [available solver options](solver-options-optimizations.md).

        - `solve_statistics: dict`, optional
            
            Dictionary to store solve statistics. Defaults to `{}`.


        Raises
        ----------

        - ValueError: If `trusted_edges_for_safety` is not provided when optimizing with `optimize_with_safe_sequences`.
        - ValueError: If `max_edge_repetition_dict` is provided but is missing any edge in `G`.
        """

        self.G = G
        if G.number_of_edges() == 0:
            utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
            raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
        self.id = self.G.id
        self.k = k
        if k <= 0:
            utils.logger.error(f"{__name__}: k must be positive, got {k}.")
            raise ValueError(f"k must be positive, got {k}.")
        if max_edge_repetition_dict is None:
            self.edge_upper_bounds = {edge: max_edge_repetition for edge in self.G.edges()}
        else:
            self.edge_upper_bounds = max_edge_repetition_dict
            for edge in self.G.edges():
                if edge not in self.edge_upper_bounds:
                    utils.logger.critical(f"{__name__}: Missing max_edge_repetition in max_edge_repetition_dict for edge {edge}")
                    raise ValueError(f"Missing max_edge_repetition for edge {edge}")
        # We set to 1 in edge_upper_bounds if the edge is not inside an SCC of self.G,
        # because these edges cannot be traversed more than 1 times by any walk
        for edge in self.G.edges():
            if not self.G.is_scc_edge(edge[0], edge[1]):
                self.edge_upper_bounds[edge] = 1

        self.subset_constraints = copy.deepcopy(subset_constraints)
        if self.subset_constraints is not None:
            self._check_valid_subset_constraints()

        self.subset_constraints_coverage = subset_constraints_coverage
        if len(subset_constraints) > 0:
            if self.subset_constraints_coverage <= 0 or self.subset_constraints_coverage > 1:
                utils.logger.error(f"{__name__}: subset_constraints_coverage must be in the range (0, 1]")
                raise ValueError("subset_constraints_coverage must be in the range (0, 1]")

        self.solve_statistics = solve_statistics
        self.edge_vars = {}
        self.edge_vars_sol = {}
        self.subset_vars = {}

        self.solver_options = solver_options
        if self.solver_options is None:
            self.solver_options = {}
        self.threads = self.solver_options.get("threads", sw.SolverWrapper.threads)

        # optimizations
        if optimization_options is None:
            optimization_options = {}
        self.optimize_with_safe_sequences = optimization_options.get("optimize_with_safe_sequences", AbstractWalkModelDiGraph.optimize_with_safe_sequences)
        self.trusted_edges_for_safety = optimization_options.get("trusted_edges_for_safety", None)
        self.allow_empty_walks = optimization_options.get("allow_empty_walks", AbstractWalkModelDiGraph.allow_empty_walks)
        self.optimize_with_safety_as_subset_constraints = optimization_options.get("optimize_with_safety_as_subset_constraints", AbstractWalkModelDiGraph.optimize_with_safety_as_subset_constraints)
        self.optimize_with_max_safe_antichain_as_subset_constraints = optimization_options.get("optimize_with_max_safe_antichain_as_subset_constraints", AbstractWalkModelDiGraph.optimize_with_max_safe_antichain_as_subset_constraints)
        self.optimize_with_safe_sequences_allow_geq_constraints = optimization_options.get("optimize_with_safe_sequences_allow_geq_constraints", AbstractWalkModelDiGraph.optimize_with_safe_sequences_allow_geq_constraints)
        self.optimize_with_safe_sequences_fix_via_bounds = optimization_options.get("optimize_with_safe_sequences_fix_via_bounds", AbstractWalkModelDiGraph.optimize_with_safe_sequences_fix_via_bounds)
        self.optimize_with_safe_sequences_fix_zero_edges = optimization_options.get(
            "optimize_with_safe_sequences_fix_zero_edges",
            AbstractWalkModelDiGraph.optimize_with_safe_sequences_fix_zero_edges,
        )

        self._is_solved = False

        if not hasattr(self, "solve_time_start") or self.solve_time_start is None:
            self.solve_time_start = time.perf_counter()

    def create_solver_and_walks(self):
        """
        Creates a solver instance and encodes the walks in the graph.

        This method initializes the solver with the specified parameters and encodes the walks
        by creating variables for edges and subsets to cover.

        !!! warning "Call this method before encoding other variables and constraints."
        
            Always call this method before encoding other variables and constraints on the walks.

        """
        self.solver = sw.SolverWrapper(**self.solver_options)

        self._encode_walks()
        
        self._apply_safety_optimizations()

        self._encode_subset_constraints()

        self.solve_statistics["graph_width"] = self.G.get_width()
        self.solve_statistics["edge_number"] = self.G.number_of_edges()
        self.solve_statistics["node_number"] = self.G.number_of_nodes()

    def _encode_walks(self):

        # Encodes the paths in the graph by creating variables for edges and subsets to cover.

        # This method initializes the edge and subset variables for the solver and adds constraints
        # to ensure the paths are valid according to the given subset constraints and safe lists.

        self.edge_indexes = [
            (u, v, i) for i in range(self.k) for (u, v) in self.G.edges()
        ]
        self.solve_statistics["edge_variables_total"] = len(self.edge_indexes)

        self.path_indexes = [(i) for i in range(self.k)]
        self.vertex_indexes = [
            (v, i) for i in range(self.k) for v in self.G.nodes()
        ]

        ################################
        #                              #
        #       Encoding walks         #
        #                              #
        ################################

        # We follow https://arxiv.org/abs/2209.00042

        # Basic

        utils.logger.debug(f"{__name__}: Encoding walks for graph id = {utils.fpid(self.G)} with k = {self.k}")

        # Build per-index UBs for edge variables using self.edge_upper_bounds[(u,v)] repeated across layers
        edge_ubs = [float(self.edge_upper_bounds[(u, v)]) for (u, v, i) in self.edge_indexes]
        self.edge_vars = self.solver.add_variables(self.edge_indexes, name_prefix="edge", lb=0, ub=edge_ubs, var_type="integer")

        # Note that x[(u,v,i)] can take values bigger than 1 if using the edge (u,v) more times, but by our construction the self.G.source is
        # also a source of the graph, so the walk cannot come back to self.G.source.
        for i in range(self.k):
            if not self.allow_empty_walks:
                self.solver.add_constraint(
                    self.solver.quicksum(
                        self.edge_vars[(self.G.source, v, i)]
                        for v in self.G.successors(self.G.source)
                    )
                    == 1,
                    name=f"17a_i={i}",
                )
            else:
                self.solver.add_constraint(
                    self.solver.quicksum(
                        self.edge_vars[(self.G.source, v, i)]
                        for v in self.G.successors(self.G.source)
                    )
                    <= 1,
                    name=f"17a_i={i}",
                )

        for i in range(self.k):
            for v in self.G.nodes:  # find all edges u->v->w for v in V\{s,t}
                if v == self.G.source or v == self.G.sink:
                    continue
                self.solver.add_constraint(
                    self.solver.quicksum(self.edge_vars[(u, v, i)] for u in self.G.predecessors(v))
                    - self.solver.quicksum(self.edge_vars[(v, w, i)] for w in self.G.successors(v))
                    == 0,
                    f"17b_v={v}_i={i}",
                )

        # Constraints to make sure the entire walk is strongly connected
        # Every vertex gets a distance d[v,i]
        self.distance_vars = self.solver.add_variables(self.vertex_indexes, name_prefix="distance", lb=0, ub=self.G.number_of_nodes(), var_type="integer")
        self.edge_selected_vars = self.solver.add_variables(self.edge_indexes, name_prefix="selected_edge", lb=0, ub=1, var_type="integer")

        # Edge selected constraints

        # 19a: If y[(u,v,i)] = 1, then x[(u,v,i)] >= 1
        # Equivalently, y[(u,v,i)] cannot be 1 without x[(u,v,i)] being at least 1
        for i in range(self.k):
            for (u,v) in self.G.edges:
                self.solver.add_constraint(
                    self.edge_vars[(u, v, i)] >= self.edge_selected_vars[(u, v, i)],
                    name=f"21_edge_selected_u={u}_v={v}_i={i}",
                )

        # 19b: If a vertex is selected, then exactly one in-coming edge is selected
        for i in range(self.k):
            for v in self.G.nodes:
                if v == self.G.source:
                    continue
                incoming_flow_v     = self.solver.quicksum( self.edge_vars[(u, v, i)]          for u in self.G.predecessors(v) )
                incoming_selected_v = self.solver.quicksum( self.edge_selected_vars[(u, v, i)] for u in self.G.predecessors(v) )

                # If at least one x[(u,v,i)] is 1, then at least one y[(u,v,i)] is 1
                # Big-M uses per-edge upper bounds for incoming edges to v
                M_v = sum(self.edge_upper_bounds[(u, v)] for u in self.G.predecessors(v))
                self.solver.add_constraint(
                    incoming_flow_v <= M_v * incoming_selected_v,
                    name=f"22a_vertex_selected_v={v}_i={i}",
                )
                # At most one y[(u,v,i)] = 1
                self.solver.add_constraint(
                    incoming_selected_v <= 1,
                    name=f"22b_vertex_selected_v={v}_i={i}",
                )

        # 18a: d[s,1] = 1
        for i in range(self.k):
            self.solver.add_constraint(
                self.distance_vars[(self.G.source, i)] == 1,
                name=f"18a_i={i}",
            )
        # 19c: The distance strictly increases along selected edges
        M = self.G.number_of_nodes() + 1
        for i in range(self.k):
            for (u,v) in self.G.edges:
                # If edge is selected, distance must increase by at least 1 (or exactly 1, but exact equality not needed)
                # Otherwise, we don't impose anything, which is why we use big M
                self.solver.add_constraint(
                    self.distance_vars[(v, i)] >= self.distance_vars[(u, i)] + 1 - M * (1 - self.edge_selected_vars[(u, v, i)]),
                    name=f"19c_distance_order_u={u}_v={v}_i={i}",
                )

    def _encode_subset_constraints(self):

        #################################
        #                               #
        # Encoding subset constraints   #
        #                               #
        #################################

        # Example of a subset constraint: R=[ [(1,3),(3,5)], [(0,1)] ], means that we have 2 subsets to cover, the first one is {(1,3),(3,5)}, the second set is just a single edge {(0,1)}

        if len(self.subset_constraints) == 0:
            return
        else:
            utils.logger.debug(f"{__name__}: Encoding subset constraints for graph id = {utils.fpid(self.G)} with k = {self.k}")

        self.subset_indexes = [ (i, j) for i in range(self.k) for j in range(len(self.subset_constraints)) ]

        self.subset_vars = self.solver.add_variables(
            self.subset_indexes, name_prefix="r", lb=0, ub=1, var_type="integer")

        # Model z[(u,v,i)] = min(1, x[(u,v,i)]) with a binary aux var and per-edge UB:
        #   z <= x
        #   x <= U_e * z, where U_e is the per-edge upper bound
        self.edge_used_vars = self.solver.add_variables(
            self.edge_indexes, name_prefix="used_edge", lb=0, ub=1, var_type="integer"
        )
        for i in range(self.k):
            for (u, v) in self.G.edges:
                # z_ei <= x_ei
                self.solver.add_constraint(
                    self.edge_used_vars[(u, v, i)] <= self.edge_vars[(u, v, i)],
                    name=f"min1_le_x_u={u}_v={v}_i={i}",
                )
                # x_ei <= U * z_ei
                self.solver.add_constraint(
                    self.edge_vars[(u, v, i)] <= self.edge_upper_bounds[(u, v)] * self.edge_used_vars[(u, v, i)],
                    name=f"x_le_Ue_min1_u={u}_v={v}_i={i}",
                )

        for i in range(self.k):
            for j in range(len(self.subset_constraints)):
                # By default, the length of the constraints is its number of edges 
                constraint_as_set = set(self.subset_constraints[j])
                constraint_length = len(constraint_as_set)
                # And the fraction of edges that we need to cover is self.subset_constraints_coverage
                coverage_fraction = self.subset_constraints_coverage
                self.solver.add_constraint(
                    self.solver.quicksum(self.edge_used_vars[(e[0], e[1], i)] for e in constraint_as_set)
                    >= constraint_length * coverage_fraction
                    * self.subset_vars[(i, j)],
                    name=f"7a_i={i}_j={j}",
                )
        for j in range(len(self.subset_constraints)):
            self.solver.add_constraint(
                self.solver.quicksum(self.subset_vars[(i, j)] for i in range(self.k)) >= 1,
                name=f"7b_j={j}",
            )

    def _apply_safety_optimizations(self):

        self.safe_lists = []

        if self.optimize_with_safe_sequences or self.optimize_with_safety_as_subset_constraints or self.optimize_with_max_safe_antichain_as_subset_constraints:
            start_time = time.perf_counter()
            self.safe_lists += safetypathcoverscycles.maximal_safe_sequences_via_dominators(
                G=self.G,
                X=self.trusted_edges_for_safety,
            )
            utils.logger.debug(f"{__name__}: Found {len(self.safe_lists)} safe sequences in {time.perf_counter() - start_time} seconds.")
            self.solve_statistics["safe_sequences_time"] = time.perf_counter() - start_time

        if self.safe_lists is None:
            return

        # In this case, we use all maximal safe sequences as subset constraints
        if self.optimize_with_safety_as_subset_constraints:
            self.subset_constraints += self.safe_lists
            return
        
        self.walks_to_fix = self._get_walks_to_fix_from_safe_lists()
        self.solve_statistics["edge_variables=1"] = 0
        self.solve_statistics["edge_variables>=1"] = 0
        self.solve_statistics["edge_variables=0"] = 0

        # Optionally fix clearly incompatible edges to zero using reachability w.r.t. each safe walk
        if self.optimize_with_safe_sequences_fix_zero_edges:
            self._apply_safety_optimizations_fix_zero_edges()

        # In this case, we use only the maximum antichain of maximal safe sequences as subset constraints
        if self.optimize_with_max_safe_antichain_as_subset_constraints:
            self.subset_constraints += self.walks_to_fix
            return

        # Otherwise, we fix variables using the walks to fix
        if self.optimize_with_safe_sequences:
            # iterating over safe lists
            for i in range(min(len(self.walks_to_fix), self.k)):
                # print("Fixing variables for safe list #", i)
                # iterate over the edges in the safe list to fix variables to 1
                for u, v in self.walks_to_fix[i]:
                    if self.G.is_scc_edge(u, v):
                        if self.optimize_with_safe_sequences_allow_geq_constraints:
                            # Raise LB via bounds only when enabled; else add constraint
                            if self.optimize_with_safe_sequences_fix_via_bounds:
                                self.solver.queue_set_var_lower_bound(self.edge_vars[(u, v, i)], 1)
                            else:
                                self.solver.add_constraint(
                                    self.edge_vars[(u, v, i)] >= 1,
                                    name=f"safe_list_u={u}_v={v}_i={i}",
                                )
                            self.solve_statistics["edge_variables>=1"] += 1
                    else:
                        # Instead of adding an equality constraint x==1 we tighten bounds directly.
                        if self.optimize_with_safe_sequences_fix_via_bounds:
                            # Queue a fix to value 1
                            self.solver.queue_fix_variable(self.edge_vars[(u, v, i)], int(1))
                        else:
                            # Keep old behaviour via equality constraint
                            self.solver.add_constraint(
                                self.edge_vars[(u, v, i)] == 1,
                                name=f"safe_list_u={u}_v={v}_i={i}",
                            )
                        self.solve_statistics["edge_variables=1"] += 1

    def _apply_safety_optimizations_fix_zero_edges(self):
        """
        Prune layer-edge variables to zero using safe-walk reachability while
        preserving edges that can be part of the walk or its connectors.

        For each walk i in `walks_to_fix` we build a protection set of edges that
        must not be fixed to 0 for layer i:
            1) Protect all edges that appear in the walk itself.
            2) Whole-walk reachability: let first_node be the first node of the walk
                    and last_node the last node. Protect any edge (u,v) such that
                        - u is reachable (forward) from last_node, OR
                        - v can reach (backward) first_node.
            3) Gap-bridging between consecutive edges: for every pair of consecutive
                    edges whose endpoints do not match (a gap), let
                        - current_last  = end node of the first edge, and
                        - current_start = start node of the next edge.
                    Protect any edge (u,v) such that
                        - u is reachable (forward) from current_last, AND
                        - v can reach (backward) current_start.

        All remaining edges (u,v) not in the protection set are fixed to 0 in
        layer i.

        Notes:
        - Requires `self.walks_to_fix` already computed and `self.edge_vars` created.
        - Reachability is computed with networkx `descendants` (forward) and
            `ancestors` (backward), including the seed node itself in each set.
        - If a walk has no gaps, only the whole-walk reachability protection (2)
            applies. If the graph structure makes many edges reachable, little or no
            pruning may occur for that walk.
        """
        if not hasattr(self, "walks_to_fix") or self.walks_to_fix is None:
            return

        fixed_zero_count = 0
        # Ensure we don't go beyond k layers
        for i in range(min(len(self.walks_to_fix), self.k)):
            walk = self.walks_to_fix[i]
            if not walk:
                continue

            # Build the set of edges that should NOT be fixed to 0 for this layer i
            # Start by protecting all edges in the walk itself
            protected_edges = set((u, v) for (u, v) in walk if self.G.has_edge(u, v))

            # Also protect edges that are reachable from the last node of the walk
            # or that can reach the first node of the walk
            first_node = walk[0][0]
            last_node = walk[-1][1]
            reachable_from_last_walk = nx.descendants(self.G, last_node) | {last_node}
            can_reach_first_walk = nx.ancestors(self.G, first_node) | {first_node}
            for (u, v) in self.G.edges:
                if (u in reachable_from_last_walk) or (v in can_reach_first_walk):
                    protected_edges.add((u, v))

            # Collect pairs of non-contiguous consecutive edges (gaps)
            gap_pairs = []
            for idx in range(len(walk) - 1):
                end_prev = walk[idx][1]
                start_next = walk[idx + 1][0]
                if end_prev != start_next:
                    gap_pairs.append((end_prev, start_next))

            # If there are no gaps, do not prune anything for this walk/layer
            if not gap_pairs:
                continue

            # For each gap, add edges that can lie on some path bridging the gap
            for (current_last, current_start) in gap_pairs:
                reachable_from_last = nx.descendants(self.G, current_last) | {current_last}
                can_reach_start = nx.ancestors(self.G, current_start) | {current_start}

                for (u, v) in self.G.edges:
                    if (u in reachable_from_last) and (v in can_reach_start):
                        protected_edges.add((u, v))

            # Now fix every other edge to 0 for this layer i
            for (u, v) in self.G.edges:
                if (u, v) in protected_edges:
                    continue
                # Queue zero-fix for batch bounds update
                self.solver.queue_fix_variable(self.edge_vars[(u, v, i)], int(0))
                fixed_zero_count += 1

        if fixed_zero_count:
            # Accumulate into solve statistics
            self.solve_statistics["edge_variables=0"] = self.solve_statistics.get("edge_variables=0", 0) + fixed_zero_count
            utils.logger.debug(f"{__name__}: Fixed {fixed_zero_count} edge variables to 0 via reachability pruning.")



    def _get_walks_to_fix_from_safe_lists(self) -> list:
     
        # Returns the walks to fix based on the safe lists.
        # The method finds the longest safe list for each edge and returns the walks to fix based on the longest safe list.

        # If already computed before, return the cached version
        if hasattr(self, "walks_to_fix") and self.walks_to_fix is not None:
            utils.logger.debug(f"{__name__}: Returning cached walks_to_fix with {len(self.walks_to_fix)} walks.")
            return self.walks_to_fix

        # If we have no safe lists, we return an empty list
        if self.safe_lists is None or len(self.safe_lists) == 0:
            self.walks_to_fix = []
            utils.logger.debug(f"{__name__}: No safe lists available; caching empty walks_to_fix.")
            return self.walks_to_fix

        walks_to_fix = self.G.get_longest_incompatible_sequences(self.safe_lists)
        # Cache the result
        self.walks_to_fix = walks_to_fix

        utils.logger.debug(f"{__name__}: Found {len(walks_to_fix)} walks to fix based on safe lists.")
        for i, walk in enumerate(walks_to_fix):
            utils.logger.debug(f"{__name__}: Safe walk {i}: {walk}")

        return self.walks_to_fix

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
            # Check that each subset has at least one edge
            if len(subset) == 0:
                utils.logger.error(f"{__name__}: subset {subset} must have at least 1 edge.")
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
        self.solve_statistics[f"solve_time_ilp"] = time.perf_counter() - start_time
        self.solve_statistics[f"solve_time"] = time.perf_counter() - self.solve_time_start
        self.solve_statistics[f"model_status"] = self.solver.get_model_status()
        self.solve_statistics[f"number_of_nontrivial_SCCs"] = self.G.get_number_of_nontrivial_SCCs()
        self.solve_statistics[f"avg_size_of_non_trivial_SCC"] = self.G.get_avg_size_of_non_trivial_SCC()
        self.solve_statistics[f"size_of_largest_SCC"] = self.G.get_size_of_largest_SCC()

        if self.solver.get_model_status() == "kOptimal" or self.solver.get_model_status() == 2:
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

    def compute_edge_max_reachable_value(self, u, v) -> int:
        """
        Returns an upper bound on how many times edge (u,v) can be used in a single walk layer.

        Subclasses should override this to provide a tighter, problem-specific bound.
        The default falls back to `self.max_edge_repetition`.
        Must return a non-negative integer.
        """
        return int(self.max_edge_repetition)

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
        Retrieves the solution walks from the graph, handling cycles with multiplicities.
        
        For each layer i, this reconstructs a single Eulerian walk that uses all edges
        with positive flow, ensuring complete flow decomposition.
        """
        
        if self.edge_vars_sol == {}:
            self.edge_vars_sol = self.solver.get_values(self.edge_vars)
        # utils.logger.debug(f"{__name__}: Getting solution walks with self.edge_vars_sol = {self.edge_vars_sol}")

        walks = []
        for i in range(self.k):
            # Build residual graph for this layer with edge multiplicities
            residual_graph = self._build_residual_graph_for_layer(i)
            # utils.logger.debug(f"{__name__}: residual_graph = {residual_graph}")
            
            # Check if there's any flow in this layer
            if not residual_graph:
                walks.append([])
                continue
                
            # Reconstruct complete Eulerian walk
            walk = self._reconstruct_eulerian_walk(residual_graph, i)
            walks.append(walk)
        
        return walks

    def _build_residual_graph_for_layer(self, layer_i: int) -> dict:
        """
        Builds a residual graph for a specific layer with edge multiplicities.
        
        Returns a dictionary where keys are vertices and values are lists of 
        outgoing neighbors (with repetition for multiple uses).
        """
        residual_graph = {}
        
        # Initialize all vertices
        for vertex in self.G.nodes():
            residual_graph[vertex] = []
        
        # Add edges based on solution values
        for (u, v) in self.G.edges():
            edge_key = (str(u), str(v), layer_i)
            if edge_key in self.edge_vars_sol:
                multiplicity = round(self.edge_vars_sol[edge_key])
                # Add this edge 'multiplicity' times to the residual graph
                for _ in range(multiplicity):
                    residual_graph[u].append(v)
        
        return residual_graph

    def _reconstruct_eulerian_walk(self, residual_graph: dict, layer_i: int) -> list:
        """
        Reconstructs a complete Eulerian walk using Hierholzer's algorithm.
        """
        # Make a copy since we'll be modifying it
        graph = {v: neighbors[:] for v, neighbors in residual_graph.items()}
        
        # Start from source
        current_vertex = self.G.source
        walk = [current_vertex]
        stack = []

        # Find one s-t walk
        while graph[current_vertex]:
            # Follow an unused edge
            next_vertex = graph[current_vertex].pop()
            stack.append(current_vertex)
            current_vertex = next_vertex
            walk.append(current_vertex)
            # utils.logger.debug(f"{__name__}: Current walk: {walk}, stack: {stack}")
        
        # Find vertices from which we can find dangling closed walks
        while stack:
            # utils.logger.debug(f"{__name__}: Current stack: {stack}")
            potential_vertex = stack.pop()            
            if graph[potential_vertex]:
                # Build and insert closed walk from this vertex
                closed_walk_start_idx = walk.index(potential_vertex)
                closed_walk = self._build_closed_walk_from_vertex(graph, potential_vertex, stack)

                # Insert closed walk into walk (excluding duplicate start vertex)
                walk[closed_walk_start_idx + 1:closed_walk_start_idx + 1] = closed_walk[1:]

        # Verify all edges were used
        total_edges_remaining = sum(len(neighbors) for neighbors in graph.values())
        if total_edges_remaining > 0:
            utils.logger.error(f"{__name__}: Layer {layer_i}: {total_edges_remaining} edges not used")

        # Remove source and sink from the walk
        if len(walk) >= 2 and walk[0] == self.G.source and walk[-1] == self.G.sink:
            return walk[1:-1]
        elif walk == [self.G.source]:
            return []
        else:
            utils.logger.error(f"{__name__}: Layer {layer_i}: Walk {walk} does not start with source or end with sink")
            return walk

    def _build_closed_walk_from_vertex(self, graph: dict, start_vertex, stack: list) -> list:
        """
        Builds a closed walk starting from the given vertex, modifying graph and stack.
        """
        closed_walk = [start_vertex]
        current_vertex = start_vertex
        
        while graph[current_vertex]:
            next_vertex = graph[current_vertex].pop()
            stack.append(current_vertex)
            closed_walk.append(next_vertex)
            current_vertex = next_vertex
            
            # Stop if we've completed the cycle
            if current_vertex == start_vertex:
                break
        
        return closed_walk

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