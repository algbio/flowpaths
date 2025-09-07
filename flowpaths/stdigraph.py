import networkx as nx
import copy
from flowpaths.utils import graphutils
from flowpaths.stdag import stDAG
import flowpaths.utils as utils
from flowpaths.abstractsourcesinkgraph import AbstractSourceSinkGraph
from typing import Dict, Tuple


class stDiGraph(AbstractSourceSinkGraph):
    """General directed graph with global source/sink and SCC condensation helpers.

    This class now subclasses [`AbstractSourceSinkGraph`](abstractsourcesinkgraph.md), which performs the common augmentation
    (adding global source/sink and validating additional boundary nodes). The remaining
    logic here focuses on strongly connected component (SCC) handling and the condensation
    expansion used for width and incompatible sequence computations.

    """
    def __init__(
        self,
        base_graph: nx.DiGraph,
        additional_starts: list | None = None,
        additional_ends: list | None = None,
    ):
        """
        This class inherits from networkx.DiGraph. The graph equals `base_graph` plus:

        - a global source connected to all sources of `base_graph` and to all nodes in `additional_starts`;
        - a global sink connected from all sinks of `base_graph` and from all nodes in `additional_ends`.

        !!! warning Warning

            The graph `base_graph` must satisfy the following properties:
            
            - the nodes must be strings; 
            - `base_graph` must have at least one source (i.e. node without incoming edges), or at least one node in `additional_starts`;
            - `base_graph` must have at least one sink (i.e. node without outgoing edges), or at least one node in `additional_ends`.

        Raises:
        -------
        - `ValueError`: If any of the above three conditions are not satisfied.
        - `ValueError`: If any node in `additional_starts` is not in the base graph.
        - `ValueError`: If any node in `additional_ends` is not in the base graph.

        """
        self._condensation_expanded = None
        super().__init__(
            base_graph=base_graph,
            additional_starts=additional_starts,
            additional_ends=additional_ends,
        )

    def _post_build(self):
        if len(self.source_edges) == 0:
            utils.logger.error(f"{__name__}: The graph passed to stDiGraph must have at least one source, or at least one node in `additional_starts`.")
            raise ValueError("The graph passed to stDiGraph must have at least one source, or at least one node in `additional_starts`.")
        if len(self.sink_edges) == 0:
            utils.logger.error(f"{__name__}: The graph passed to stDiGraph must have at least one sink, or at least one node in `additional_ends`.")
            raise ValueError("The graph passed to stDiGraph must have at least one sink, or at least one node in `additional_ends`.")
        self.condensation_width = None
        self._build_condensation_expanded()

    def _expanded(self, v: int) -> str:

        return str(v) + "_expanded"

    def _build_condensation_expanded(self):

        self._condensation: nx.DiGraph = nx.condensation(self)
        # We add the dict `member_edges` storing for each node in the condensation, the edges in that SCC
        self._condensation.graph["member_edges"] = {str(node): set() for node in self._condensation.nodes()}
        # We add the dict `edge_multiplicity` for each edge in the condensation to store the number of 
        # original graph edges that are between the corresponding SCCs (and these SCCs are different, i.e. we don't store this for self-loops)
        self._condensation.graph["edge_multiplicity"] = {e: 0 for e in self._condensation.edges() if e[0] != e[1]}

        for u, v in self.edges():
            # If u and v are in the same SCC, we add it to the member edges
            if self._condensation.graph['mapping'][u] == self._condensation.graph['mapping'][v]:
                self._condensation.graph["member_edges"][str(self._condensation.graph['mapping'][u])].add((u, v))
            else:
                # Otherwise, we increase the multiplicity of the condensation edge between the different SCCs
                self._condensation.graph["edge_multiplicity"][self._edge_to_condensation_edge(u, v)] += 1
        utils.logger.debug(f"{__name__}: Condensation graph: {self._condensation.edges()}")
        utils.logger.debug(f"{__name__}: Condensation member edges: {self._condensation.graph['member_edges']}")
        utils.logger.debug(f"{__name__}: Condensation mapping: {self._condensation.graph['mapping']}")

        # Conventions
        # self._condensation has int nodes 
        # self._condensation.graph['mapping'][u] : str (i.e. original nodes) -> int (i.e. condensation nodes)
        # self._condensation.graph["member_edges"] : str (i.e. str(condensation nodes)) -> set(str,str) (i.e. set of original edges, which are (str,str))
        # self._condensation.graph["edge_multiplicity"] : tuple(int, int) (i.e. condensation edge between SCCs) -> int (i.e. multiplicity of edges between SCCs)

        # self._condensation_expanded has str nodes
        # self._condensation_expanded has nodes of the form 
        # - str(int), if the SCC node is trivial (having no edges)
        # - str(int) and str(int) + "_expanded", if the SCC node is non-trivial

        # cond_expanded is a copy of self._condensation, with the difference
        # that all nodes v corresponding to non-trivial SCCs (i.e. with at least one edge)
        # are expanded into an edge (v, self._expanded(v))
        condensation_expanded = nx.DiGraph()
        for v in self._condensation.nodes:
            # If v belongs to a trivial SCC (having no edges),
            # then we don't expand the node
            if len(self._condensation.graph["member_edges"][str(v)]) == 0:
                condensation_expanded.add_node(str(v))
            else:
                # Otherwise, if the SCC of the node is non-trivial, then we expand the node into the edge (v, self._expanded(v))
                condensation_expanded.add_node(str(v))
                condensation_expanded.add_node(self._expanded(v))
                condensation_expanded.add_edge(str(v), self._expanded(v))

        for u, v in self._condensation.edges():
            edge_source = str(u) if len(self._condensation.graph["member_edges"][str(u)]) == 0 else self._expanded(str(u))
            edge_target = str(v)
            condensation_expanded.add_edge(edge_source,edge_target)

        self._condensation_expanded = stDAG(condensation_expanded)

        utils.logger.debug(f"{__name__}: Condensation expanded graph: {self._condensation_expanded.edges()}")

    def _edge_to_condensation_expanded_edge(self, u, v) -> tuple:
        """
        Maps an edge (u,v) in the original graph to an edge in the condensation_expanded graph.
        """

        if (u,v) not in self.edges():
            utils.logger.error(f"{__name__}: Edge ({u}, {v}) not found in original graph.")
            raise ValueError(f"Edge ({u}, {v}) not found in original graph.")

        mapping_u = self._condensation.graph['mapping'][u]
        mapping_v = self._condensation.graph['mapping'][v]
        
        if mapping_u != mapping_v:
            # If an edge between SCCs, then check if the source of the edge is a trivial SCC or not
            edge_source = str(mapping_u) if len(self._condensation.graph["member_edges"][str(mapping_u)]) == 0 else self._expanded(str(mapping_u))
            edge_target = str(mapping_v)
        else:
            # If an edge inside an SCC, then that SCC is non-trivial, and we return the expanded edge corresponding to that SCC
            edge_source = str(mapping_u)
            edge_target = self._expanded(str(mapping_u))

        if (edge_source, edge_target) not in self._condensation_expanded.edges():
            utils.logger.error(f"{__name__}: Edge ({edge_source}, {edge_target}) not found in condensation expanded graph.")
            raise ValueError(f"Edge ({edge_source}, {edge_target}) not found in condensation expanded graph.")

        return (edge_source, edge_target)

    def _condensation_edge_to_condensation_expanded_edge(self, u, v) -> tuple:
        """
        Maps an edge (u,v) in the condensation graph to an edge in the condensation_expanded graph.
        """

        if (u,v) not in self._condensation.edges() and u != v:
            utils.logger.error(f"{__name__}: Edge ({u}, {v}) not found in condensation graph.")
            raise ValueError(f"Edge ({u}, {v}) not found in condensation graph.")

        if u != v:
            # If an edge between SCCs, then check if the source of the edge is a trivial SCC or not
            edge_source = str(u) if len(self._condensation.graph["member_edges"][str(u)]) == 0 else self._expanded(str(u))
            edge_target = str(v)
        else:
            # If an edge inside an SCC, then that SCC is non-trivial, and we return the expanded edge corresponding to that SCC
            edge_source = str(u)
            edge_target = self._expanded(str(u))

        if (edge_source, edge_target) not in self._condensation_expanded.edges():
            utils.logger.error(f"{__name__}: Edge ({edge_source}, {edge_target}) not found in condensation expanded graph.")
            raise ValueError(f"Edge ({edge_source}, {edge_target}) not found in condensation expanded graph.")

        return (edge_source, edge_target)
    
    def _edge_to_condensation_node(self, u, v) -> str:
        """
        Maps an edge `(u,v)` inside an SCC of the original graph 
        to the node corresponding to the SCC (as `str`) in the condensation graph

        Raises:
        -------
        - `ValueError` if the edge (u,v) is not an edge of the graph.
        - `ValueError` if the edge (u,v) is not inside an SCC.
        """

        if not self.is_scc_edge(u, v):
            utils.logger.error(f"{__name__}: Edge ({u},{v}) is not an edge inside an SCC.")
            raise ValueError(f"Edge ({u},{v}) is not an edge inside an SCC.")
        
        return str(self._condensation.graph['mapping'][u])

    def _edge_to_condensation_edge(self, u, v) -> tuple:
        """
        Maps an edge `(u,v)` of the original graph 
        to the edge of the condensation graph.

        Raises:
        -------
        - `ValueError` if the edge (u,v) is not an edge of the graph.
        """

        return (self._condensation.graph['mapping'][u], self._condensation.graph['mapping'][v])

    def get_width(self, edges_to_ignore: list = None) -> int:
        """
        Returns the width of the graph, which we define as the minimum number of $s$-$t$ walks needed to cover all edges.

        This is computed as the width of the condensation DAGs (minimum number of $s$-$t$ paths to cover all edges), with the following modification.
        Nodes `v` in the condensation corresponding to non-trivial SCCs (i.e. SCCs with more than one node, equivalent to having at least one edge) 
        are subdivided into a edge `(v, v_expanded)`, all condensation in-neighbors of `v` are connected to `v`,
        and all condensation out-neighbors of `v` are connected from `v_expanded`.

        Parameters:
        -----------
        - `edges_to_ignore`: A list of edges in the original graph to ignore when computing the width.

            The width is then computed as as above, with the exception that:

            - If an edge `(u,v)` in `edges_to_ignore` is between different SCCs, 
                then the corresponding edge to ignore is between the two SCCs in the condensation graph, 
                and we can ignore it when computing the normal width of the condensation.

            - If an edge `(u,v)` in `edges_to_ignore` is inside the same SCC, 
                then we remove the edge `(u,v)` from (a copy of) the member edges of the SCC in the condensation. 
                If an SCC `v` has no more member edges left, we can also add the condensation edge `(v, v_expanded)` to
                the list of edges to ignore when computing the width of the condensation.
        """

        if self.condensation_width is not None and (edges_to_ignore is None or len(edges_to_ignore) == 0):
            return self.condensation_width

        # We transform each edge in edges_to_ignore (which are edges of self)
        # into an edge in the expanded graph
        edges_to_ignore_expanded = []
        member_edges = copy.deepcopy(self._condensation.graph['member_edges'])
        edge_multiplicity = copy.deepcopy(self._condensation.graph["edge_multiplicity"])
        utils.logger.debug(f"{__name__}: edge_multiplicity for edges in the condensation: {edge_multiplicity}")

        for u, v in (edges_to_ignore or []):
            # If (u,v) is an edge between different SCCs
            # Then the corresponding edge to ignore is between the two SCCs
            if not self.is_scc_edge(u, v):
                edge_multiplicity[self._edge_to_condensation_edge(u, v)] -= 1
            else:
                # (u,v) is an edge within the same SCC
                # and thus we remove the edge (u,v) from the member edges
                member_edges[self._edge_to_condensation_node(u, v)].discard((u, v))

        weight_function_condensation_expanded = {e: 0 for e in self._condensation_expanded.edges()}

        for u,v in self._condensation.edges:
            weight_function_condensation_expanded[self._condensation_edge_to_condensation_expanded_edge(u,v)] = edge_multiplicity[(u,v)]

        # We also add to edges_to_ignore_expanded the expanded edges arising from non-trivial SCCs
        # (i.e. SCCs with more than one node, which are expanded into an edge, 
        # i.e. len(self._condensation['member_edges'][node]) > 0)
        # and for which there are no longer member edges (because all were in edges_to_ignore)
        for node in self._condensation.nodes():
            if len(member_edges[str(node)]) == 0 and len(self._condensation.graph['member_edges'][str(node)]) > 0:
                weight_function_condensation_expanded[(str(node), self._expanded(node))] = 0
            else:
                weight_function_condensation_expanded[(str(node), self._expanded(node))] = 1

        utils.logger.debug(f"{__name__}: Edges to ignore in the expanded graph: {edges_to_ignore_expanded}")

        utils.logger.debug(f"{__name__}: Condensation expanded graph: {self._condensation_expanded.edges()}")
        # width = self._condensation_expanded.get_width(edges_to_ignore=edges_to_ignore_expanded)

        width = self._condensation_expanded.compute_max_edge_antichain(get_antichain=False, weight_function=weight_function_condensation_expanded)

        utils.logger.debug(f"{__name__}: Width of the condensation expanded graph: {width}")

        if (edges_to_ignore is None or len(edges_to_ignore) == 0):
            self.condensation_width = width

        # DEBUG code
        # utils.draw(
        #         G=self._condensation_expanded,
        #         filename="condensation_expanded.pdf",
        #         flow_attr="flow",
        #         draw_options={
        #         "show_graph_edges": True,
        #         "show_edge_weights": False,
        #         "show_path_weights": False,
        #         "show_path_weight_on_first_edge": True,
        #         "pathwidth": 2,
        #     })

        return width
    
    def is_scc_edge(self, u, v) -> bool:
        """
        Returns True if (u,v) is an edge inside an SCC of self, False otherwise.
        """

        # Check if (u,v) is an edge of the graph
        if (u,v) not in self.edges():
            utils.logger.error(f"{__name__}: Edge ({u},{v}) is not in the graph.")
            raise ValueError(f"Edge ({u},{v}) is not in the graph.")

        return self._condensation.graph['mapping'][u] == self._condensation.graph['mapping'][v]

    def get_number_of_nontrivial_SCCs(self) -> int:
        """
        Returns the number of non-trivial SCCs (i.e. SCCs with at least one edge).
        """

        return sum(1 for v in self._condensation.nodes() if len(self._condensation.graph['member_edges'][str(v)]) > 0)

    def get_size_of_largest_SCC(self) -> int:
        """
        Returns the size of the largest SCC (in terms of number of edges).
        """
        return max((len(self._condensation.graph['member_edges'][str(v)]) for v in self._condensation.nodes()), default=0)
    
    def get_avg_size_of_non_trivial_SCC(self) -> int:
        """
        Returns the average size (in terms of number of edges) of non-trivial SCCs (i.e. SCCs with at least one edge).
        """
        sizes = [len(self._condensation.graph['member_edges'][str(v)]) for v in self._condensation.nodes() if len(self._condensation.graph['member_edges'][str(v)]) > 0]
        return sum(sizes) // len(sizes) if sizes else 0

    def get_longest_incompatible_sequences(self, sequences: list) -> list:

        # We map the edges in sequences to edges in self._condensation_expanded

        large_constant = 0 #self.number_of_edges() + 1

        sequence_function = {e: [] for e in self._condensation_expanded.edges} # edge in self._condensation_expanded -> list of ids of all sequences using that edge

        for seq_index, sequence in enumerate(sequences):
            for u, v in sequence:
                condensation_expanded_edge = self._edge_to_condensation_expanded_edge(u, v)
                sequence_function[condensation_expanded_edge].append(seq_index)

        # for each edge, sort sequence function by the length of the sequences
        for edge in sequence_function:
            sequence_function[edge] = sorted(sequence_function[edge], key=lambda x: len(sequences[x]), reverse=True)

        # get the edge_multiplicity of each edge
        for e in self._condensation.edges():
            condensation_expanded_edge = self._condensation_edge_to_condensation_expanded_edge(e[0], e[1])
            # If the edge is between SCCs, we have a multiplicity associated to it
            # if we also have sequences associated to it, then we keep only the largest multiplicity-many
            if len(sequence_function[condensation_expanded_edge]) > 0:
                edge_multiplicity = self._condensation.graph["edge_multiplicity"][e]
                sequence_function[condensation_expanded_edge] = sequence_function[condensation_expanded_edge][:edge_multiplicity]

        for v in self._condensation.nodes():
            # If the SCC v has at least one edge,
            # then we keep only the largest sequence associated with it, because this edge 
            # cannot be used multiple times in the antichain
            if len(self._condensation.graph["member_edges"][str(v)]) > 0:
                condensation_expanded_edge = self._condensation_edge_to_condensation_expanded_edge(v, v)
                sequence_function[condensation_expanded_edge] = sequence_function[condensation_expanded_edge][:1]

        weight_function = {edge: large_constant + sum(len(sequences[seq_idx]) for seq_idx in sequence_function[edge]) for edge in self._condensation_expanded.edges()}

        utils.logger.debug(f"{__name__}: Weight function for incompatible sequences: {weight_function}")

        _, antichain = self._condensation_expanded.compute_max_edge_antichain(
            get_antichain=True,
            weight_function=weight_function,
        )

        incompatible_sequences = []

        seq_idx_set = set()
        for u, v in antichain:
            # extend incompatible_sequences with
            for seq_idx in sequence_function[(u, v)]:
                incompatible_sequences.append(sequences[seq_idx])
                # Checking that we don't report duplicates, which should never happen
                if seq_idx in seq_idx_set:
                    utils.logger.error(f"{__name__}: Sequence {seq_idx} is already in the incompatible sequences, skipping it.")
                    raise ValueError(f"{__name__}: CRITICAL BUG: Sequence {seq_idx} is already in the incompatible sequences")
                seq_idx_set.add(seq_idx)

        return incompatible_sequences

    def compute_edge_max_reachable_value(self, flow_attr: str) -> Dict[Tuple[str, str], float]:
        """For each base edge (u,v), compute the maximum ``flow_attr`` over:
        - the edge (u,v) itself,
        - any edge reachable forward from v,
        - any edge whose head can reach u (i.e., backward reachability to u).

        Efficiently uses the precomputed SCC condensation and runs dynamic programming on
        the condensation DAG.

        Returns a dict mapping each original edge (u,v) to the computed float. 

        If an edge has a missing ``flow_attr'' (the source and sink edges) we treat its flow value as 0.

        Examples
        --------
        >>> import networkx as nx
        >>> from flowpaths.stdigraph import stDiGraph
        >>> G = nx.DiGraph()
        >>> G.add_edge("a", "b", flow=1)
        >>> G.add_edge("b", "c", flow=5)
        >>> G.add_edge("c", "a", flow=3)  # cycle among a,b,c
        >>> G.add_edge("c", "d", flow=2)
        >>> H = stDiGraph(G)
        >>> res = H.compute_edge_max_reachable_value("flow")
        >>> # Every edge can reach an edge of weight 5 within the SCC or forward
        >>> res[("a", "b")] == 5 and res[("b", "c")] == 5 and res[("c", "a")] == 5 and res[("c", "d")] == 5
        True
        """
        C: nx.DiGraph = self._condensation
        mapping = C.graph["mapping"]  # original node -> condensation node (int)

        # 2) Precompute per-SCC local maxima and per-edge weights.
        #
        #    - local_out[c]: the max weight of any edge whose TAIL is inside SCC `c`.
        #      This represents the best edge you can reach by going forward from any
        #      node in this SCC (including edges that stay inside the SCC or that exit it).
        #
        #    - local_in[c]: the max weight of any edge whose HEAD is inside SCC `c`.
        #      This captures the best edge that can reach this SCC (used for backward reachability).
        #
        #    We also record each edge's own weight so the final answer includes (u,v) itself.
        local_out = {c: 0.0 for c in C.nodes()}
        local_in = {c: 0.0 for c in C.nodes()}

        edge_weight: Dict[Tuple[str, str], float] = {}
        for u, v, data in self.edges(data=True):
            w = float(data.get(flow_attr, 0.0))
            edge_weight[(u, v)] = w
            cu = mapping[u]
            cv = mapping[v]
            if w > local_out[cu]:
                local_out[cu] = w
            if w > local_in[cv]:
                local_in[cv] = w

        topological_sort = list(nx.topological_sort(C))

        # 3) Forward DP over the condensation DAG to compute, for each SCC `c`, the
        #    maximum edge weight reachable from `c` by moving forward along DAG edges.
        #    Because SCCs are contracted, this also correctly accounts for reachability
        #    within cycles (inside a single SCC).
        max_desc = {c: local_out[c] for c in C.nodes()}
        for c in reversed(topological_sort):
            for s in C.successors(c):
                if max_desc[s] > max_desc[c]:
                    max_desc[c] = max_desc[s]

        # 4) Backward DP (propagated forward along edges) to compute, for each SCC `c`, the
        #    maximum edge weight among edges whose HEAD can reach `c` (i.e. along the
        #    reversed condensation DAG). We propagate `local_in` from ancestors to successors
        #    in topological order.
        max_anc = {c: local_in[c] for c in C.nodes()}
        for c in topological_sort:
            for s in C.successors(c):
                if max_anc[c] > max_anc[s]:
                    max_anc[s] = max_anc[c]

        # 5) For each original edge (u,v), combine:
        #    - the edge's own weight,
        #    - the best reachable-from-SCC(v) weight (forward), and
        #    - the best reaching-SCC(u) weight (backward).
        #
        #    If no reachable candidate exists, the value is 0.0 by construction of locals.
        result: Dict[Tuple[str, str], float] = {}
        for u, v in self.edges():
            cu = mapping[u]
            cv = mapping[v]
            result[(u, v)] = max(edge_weight[(u, v)], max_desc[cv], max_anc[cu])

        return result
    