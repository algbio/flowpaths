import networkx as nx
import copy
from flowpaths.utils import graphutils
from flowpaths.stdag import stDAG
import flowpaths.utils as utils

class stDiGraph(nx.DiGraph):
    def __init__(
        self,
        base_graph: nx.DiGraph,
        additional_starts: list = [],
        additional_ends: list = [],
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
        if not all(isinstance(node, str) for node in base_graph.nodes()):
            utils.logger.error(f"{__name__}: Every node of the graph must be a string.")
            raise ValueError("Every node of the graph must be a string.")

        super().__init__()
        self.base_graph = base_graph
        if "id" in base_graph.graph:
            self.id = base_graph.graph["id"]
        else:
            self.id = id(self)
        self.additional_starts = set(additional_starts)
        self.additional_ends = set(additional_ends)

        # check if some node in additional_starts is not in base_graph
        if not self.additional_starts.issubset(base_graph.nodes()):
            utils.logger.error(f"{__name__}: Some nodes in additional_starts are not in the base graph.")
            raise ValueError(f"Some nodes in additional_starts are not in the base graph.")
        # check if some node in additional_ends is not in base_graph
        if not self.additional_ends.issubset(base_graph.nodes()):
            utils.logger.error(f"{__name__}: Some nodes in additional_ends are not in the base graph.")
            raise ValueError(f"Some nodes in additional_ends are not in the base graph.")
        
        self.source = f"source_{id(self)}"
        self.sink = f"sink_{id(self)}"

        self._condensation_expanded = None

        self._build_graph()

        nx.freeze(self)

    def _build_graph(self):

        self.add_nodes_from(self.base_graph.nodes(data=True))
        self.add_edges_from(self.base_graph.edges(data=True))

        for u in self.base_graph.nodes:
            if self.base_graph.in_degree(u) == 0 or u in self.additional_starts:
                self.add_edge(self.source, u)
            if self.base_graph.out_degree(u) == 0 or u in self.additional_ends:
                self.add_edge(u, self.sink)

        self.source_edges = list(self.out_edges(self.source))
        self.sink_edges = list(self.in_edges(self.sink))

        self.source_sink_edges = set(self.source_edges + self.sink_edges)

        if len(self.source_edges) == 0:
            utils.logger.error(f"{__name__}: The graph passed to stDiGraph must have at least one source, or at least one node in `additional_starts`.")
            raise ValueError(f"The graph passed to stDiGraph must have at least one source, or at least one node in `additional_starts`.")
        if len(self.sink_edges) == 0:
            utils.logger.error(f"{__name__}: The graph passed to stDiGraph must have at least one sink, or at least one node in `additional_ends`.")
            raise ValueError(f"The graph passed to stDiGraph must have at least one sink, or at least one node in `additional_ends`.")

        self.condensation_width = None
        self._build_condensation_expanded()

    def get_non_zero_flow_edges(
        self, flow_attr: str, edges_to_ignore: set = set()
    ) -> set:
        """
        Get all edges with non-zero flow values.

        Returns
        -------
        set
            A set of edges (tuples) that have non-zero flow values.
        """

        non_zero_flow_edges = set()
        for u, v, data in self.edges(data=True):
            if (u, v) not in edges_to_ignore and data.get(flow_attr, 0) != 0:
                non_zero_flow_edges.add((u, v))

        return non_zero_flow_edges

    def get_max_flow_value_and_check_non_negative_flow(
        self, flow_attr: str, edges_to_ignore: set
    ) -> float:
        """
        Determines the maximum flow value in the graph and checks for positive flow values.

        This method iterates over all edges in the graph, ignoring edges specified in
        `self.edges_to_ignore`. It checks if each edge has the required flow attribute
        specified by `self.flow_attr`. If an edge does not have this attribute, a
        ValueError is raised. If an edge has a negative flow value, a ValueError is
        raised. The method returns the maximum flow value found among all edges.

        Returns
        -------
        - float: The maximum flow value among all edges in the graph.

        Raises
        -------
        - ValueError: If an edge does not have the required flow attribute.
        - ValueError: If an edge has a negative flow value.
        """

        w_max = float("-inf")
        if edges_to_ignore is None:
            edges_to_ignore = set()

        for u, v, data in self.edges(data=True):
            if (u, v) in edges_to_ignore:
                continue
            if not flow_attr in data:
                utils.logger.error(
                    f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data."
                )
                raise ValueError(
                    f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data."
                )
            if data[flow_attr] < 0:
                utils.logger.error(
                    f"Edge ({u},{v}) has negative flow value {data[flow_attr]}. All flow values must be >=0."
                )
                raise ValueError(
                    f"Edge ({u},{v}) has negative flow value {data[flow_attr]}. All flow values must be >=0."
                )
            w_max = max(w_max, data[flow_attr])

        return w_max

    def _expanded(self, v: int) -> str:

        return str(v) + "_expanded"

    def _build_condensation_expanded(self):

        self._condensation: nx.DiGraph = nx.condensation(self)
        # We add the dict `member_edges` storing for each node in the condensation, the edges in that SCC
        self._condensation.graph["member_edges"] = {str(node): set() for node in self._condensation.nodes()}

        for u, v in self.edges():
            if self._condensation.graph['mapping'][u] == self._condensation.graph['mapping'][v]:
                self._condensation.graph["member_edges"][str(self._condensation.graph['mapping'][u])].add((u, v))
        utils.logger.debug(f"{__name__}: Condensation graph: {self._condensation.edges()}")
        utils.logger.debug(f"{__name__}: Condensation member edges: {self._condensation.graph['member_edges']}")
        utils.logger.debug(f"{__name__}: Condensation mapping: {self._condensation.graph['mapping']}")

        # Conventions
        # self._condensation has int nodes 
        # self._condensation.graph['mapping'][u] : str (i.e. original nodes) -> int (i.e. condensation nodes)
        # self._condensation.graph["member_edges"] : str (i.e. str(condensation nodes)) -> set(str,str) (i.e. set of original edges, which are (str,str))

        # self._condensation_expanded has str nodes
        # self._condensation_expanded has nodes of the form 
        # - str(int), if the SCC node is trivial
        # - str(int) and str(int) + "_expanded", if the SCC node is non-trivial

        # cond_expanded is a copy of self._condensation, with the difference
        # that all nodes v corresponding to non-trivial SCCs (i.e. with more than 2 nodes, equiv with at least one edge)
        # are expanded into an edge (v, self._expanded(v))
        condensation_expanded = nx.DiGraph()
        for v, data in self._condensation.nodes(data=True):
            # If v belongs to an SCC made up of a single node,
            # then we don't expand the node
            if len(data['members']) == 1:
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

        for u, v in (edges_to_ignore or []):
            # If (u,v) is an edge between different SCCs
            # Then the corresponding edge to ignore is between the two SCCs
            if not self.is_scc_edge(u, v):
                edges_to_ignore_expanded.append(self._edge_to_condensation_expanded_edge(u, v))
            else:
                # (u,v) is an edge within the same SCC
                # and thus we remove the edge (u,v) from the member edges
                member_edges[self._edge_to_condensation_node(u, v)].discard((u, v))

        # We also add to edges_to_ignore_expanded the expanded edges arising from non-trivial SCCs
        # (i.e. SCCs with more than one node, which are expanded into an edge, 
        # i.e. len(self._condensation['member_edges'][node]) > 0)
        # and for which there are no longer member edges (because all were in edges_to_ignore)
        for node in self._condensation.nodes():
            if len(member_edges[str(node)]) == 0 and len(self._condensation.graph['member_edges'][str(node)]) > 0:
                edges_to_ignore_expanded.append((str(node), self._expanded(node)))

        utils.logger.debug(f"{__name__}: Edges to ignore in the expanded graph: {edges_to_ignore_expanded}")

        utils.logger.debug(f"{__name__}: Condensation expanded graph: {self._condensation_expanded.edges()}")
        width = self._condensation_expanded.get_width(edges_to_ignore=edges_to_ignore_expanded)

        if (edges_to_ignore is None or len(edges_to_ignore) == 0):
            self.condensation_width = width

        return width
    
    def is_scc_edge(self, u, v) -> bool:
        """
        Returns True if (u,v) is an edge inside an SCCs, False otherwise.
        """

        # Check if (u,v) is an edge of the graph
        if (u,v) not in self.edges():
            utils.logger.error(f"{__name__}: Edge ({u},{v}) is not in the graph.")
            raise ValueError(f"Edge ({u},{v}) is not in the graph.")

        return self._condensation.graph['mapping'][u] == self._condensation.graph['mapping'][v]

    def get_longest_incompatible_sequences(self, sequences: list) -> list:

        # We map the edges in sequences to edges in self._condensation_expanded

        large_constant = 0 #self.number_of_edges() + 1

        weight_function = {edge: 0 for edge in self._condensation_expanded.edges} # edge in self._condensation_expanded -> length of a longest sequence using that edge (whn interpreting the sequence as a set)
        sequence_function = dict() # edge in self._condensation_expanded -> id of a longest sequence using that edge

        for seq_index, sequence in enumerate(sequences):
            seq_length_as_set = large_constant + len(set(sequence))
            for u, v in sequence:
                condensation_expanded_edge = self._edge_to_condensation_expanded_edge(u, v)
                if seq_length_as_set > weight_function[condensation_expanded_edge]:
                    weight_function[condensation_expanded_edge] = seq_length_as_set
                    sequence_function[condensation_expanded_edge] = seq_index

        utils.logger.debug(f"{__name__}: Weight function for incompatible sequences: {weight_function}")

        _, antichain = self._condensation_expanded.compute_max_edge_antichain(
            get_antichain=True,
            weight_function=weight_function,
        )

        incompatible_sequences = []

        for u, v in antichain:
            incompatible_sequences.append(sequences[sequence_function[(u, v)]])

        return incompatible_sequences