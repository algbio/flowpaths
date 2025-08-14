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

        self.condensation_with = None

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
    
    def _expanded(v: str):
        
        return v + "_expanded"

    def get_condensation_expanded(self) -> stDAG:

        if self._condensation_expanded is not None:
            return self._condensation_expanded

        self._condensation: nx.DiGraph = nx.condensation(self)
        # We add the dict `member_edges` storing for each node in the condensation, the edges in that SCC
        self._condensation["member_edges"] = {node: set() for node in self._condensation.nodes()}

        for u, v in self.edges():
            if self._condensation['mapping'][u] == self._condensation['mapping'][v]:
                self._condensation["member_edges"][self._condensation['mapping'][u]].add((u, v))

        # cond_expanded is a copy of self._condensation, with the difference
        # that all nodes v corresponding to non-trivial SCCs (i.e. with more than 2 nodes, equiv with at least one edge)
        # are expanded into an edge (v, self._expanded(v))
        condensation_expanded = nx.DiGraph()
        # For a non-expanded node v, condensation_expanded["expanded_node_in"] = condensation_expanded["expanded_node_out"] = v
        # For an expanded node v, condensation_expanded["expanded_node_in"] = v, condensation_expanded["expanded_node_out"] = self._expanded(v)
        condensation_expanded["expanded_node_in"] = {}
        condensation_expanded["expanded_node_out"] = {}
        for v, data in self._condensation.nodes(data=True):
            # If v belongs to an SCC made up of a single node
            if len(data['members']) == 1:
                condensation_expanded.add_node(v)
            else:
                condensation_expanded.add_node(v)
                condensation_expanded.add_node(self._expanded(v))
                condensation_expanded.add_edge(v, self._expanded(v))
            
        for u, v in self._condensation.edges():
            condensation_expanded.add_edge(self._expanded(u), v)

        self._condensation_expanded = stDAG(condensation_expanded)

    def get_condensation_width(self, edges_to_ignore: list = None) -> int:

        if self.condensation_width is not None and (edges_to_ignore is None or len(edges_to_ignore) == 0):
            return self.condensation_width

        # We transform each edge in edges_to_ignore (which are edges of self)
        # into an edge in the expanded graph
        edges_to_ignore_expanded = []
        member_edges = copy.deepcopy(self._condensation['member_edges'])

        for u, v in (edges_to_ignore or []):
            # If (u,v) is an edge between different SCCs
            # Then the corresponding edge to ignore is between the two SCCs
            mapping_u = self._condensation['mapping'][u]
            mapping_v = self._condensation['mapping'][v]
            if mapping_u != mapping_v:
                edges_to_ignore_expanded.append((self._expanded(mapping_u), mapping_v))
            else:
                # (u,v) is an edge within the same SCC indexed by mapping_u = mapping v
                # member_edges[mapping_u] stores the original graph edges in this SCC, 
                # and thus we remove the edge (u,v) from the member edges
                member_edges[mapping_u].discard((u, v))

        # We also add to edges_to_ignore_expanded the expanded edges arising from non-trivial SCCs
        # (i.e. SCCs with more than one node, which are expanded into an edge, 
        # i.e. len(self._condensation['member_edges'][node]) > 0)
        # and for which there are no longer member edges (because all were in edges_to_ignore)
        for node in self._condensation.nodes():
            if len(member_edges[node]) == 0 and len(self._condensation['member_edges'][node]) > 0:
                edges_to_ignore_expanded.append((self._expanded(node), node))

        width = self.get_condensation_expanded().get_width(edges_to_ignore_expanded)

        if (edges_to_ignore is None or len(edges_to_ignore) == 0):
            self.condensation_width = width

        return width