import networkx as nx
from flowpaths.utils import graphutils
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
