import networkx as nx
import flowpaths.utils as utils

class AbstractSourceSinkGraph(nx.DiGraph):
    """Base class for s-t augmented graphs (internal).

    This class (introduced when unifying :class:`stDAG` and :class:`stDiGraph`) factors out
    logic previously duplicated in both classes.

    Core responsibilities
    ---------------------
    * Store and expose the original ``base_graph`` plus user supplied ``additional_starts`` / ``additional_ends``.
    * Validate that all nodes are strings and that any additional start/end nodes belong to ``base_graph``.
    * Create unique global source / sink node identifiers (``self.source`` / ``self.sink``).
    * Attach the global source to every (in-degree 0) source or additional start; attach every (out-degree 0) sink
      or additional end to the global sink.
    * Expose convenience collections: ``source_edges``, ``sink_edges``, ``source_sink_edges``.
    * Provide shared flow helper utilities: :meth:`get_non_zero_flow_edges` and
      :meth:`get_max_flow_value_and_check_non_negative_flow`.

    Extension hooks
    ---------------
    Subclasses customise behaviour via two lightweight hooks:

    * ``_pre_build_validate`` - extra validation before augmentation (e.g. acyclicity for ``stDAG``).
    * ``_post_build`` - populate subclass specific derived structures (e.g. condensation for ``stDiGraph``).

    Backwards compatibility
    -----------------------
    External code should keep instantiating [`stDAG`](stdag.md) or [`stDiGraph`](stdigraph.md); their public APIs
    are unchanged. ``AbstractSourceSinkGraph`` is an internal implementation detail and may change without notice.
    """

    def __init__(
        self,
        base_graph: nx.DiGraph,
        additional_starts: list | None = None,
        additional_ends: list | None = None,
    ):
        if not all(isinstance(node, str) for node in base_graph.nodes()):
            utils.logger.error(f"{__name__}: Every node of the graph must be a string.")
            raise ValueError("Every node of the graph must be a string.")

        super().__init__()
        self.base_graph = base_graph
        if "id" in base_graph.graph:
            self.id = str(base_graph.graph["id"])
        else:
            self.id = str(id(self))

        self.additional_starts = set(additional_starts or [])
        self.additional_ends = set(additional_ends or [])

        # Ensure any declared additional start/end nodes are in the base graph
        if not self.additional_starts.issubset(base_graph.nodes()):
            utils.logger.error(f"{__name__}: Some nodes in additional_starts are not in the base graph.")
            raise ValueError("Some nodes in additional_starts are not in the base graph.")
        if not self.additional_ends.issubset(base_graph.nodes()):
            utils.logger.error(f"{__name__}: Some nodes in additional_ends are not in the base graph.")
            raise ValueError("Some nodes in additional_ends are not in the base graph.")

        self.source = f"source_{id(self)}"
        self.sink = f"sink_{id(self)}"

        # Hooks
        self._pre_build_validate()
        self._augment_with_source_sink()
        self._post_build()

        nx.freeze(self)

    # ----------------------------- Hooks ---------------------------------
    def _pre_build_validate(self):  # pragma: no cover - default is no-op
        pass

    def _post_build(self):  # pragma: no cover - default is no-op
        pass

    # --------------------------- Build logic -----------------------------
    def _augment_with_source_sink(self):
        # Add base nodes/edges
        self.add_nodes_from(self.base_graph.nodes(data=True))
        self.add_edges_from(self.base_graph.edges(data=True))

        # Connect global source & sink
        for u in self.base_graph.nodes:
            if self.base_graph.in_degree(u) == 0 or u in self.additional_starts:
                self.add_edge(self.source, u)
            if self.base_graph.out_degree(u) == 0 or u in self.additional_ends:
                self.add_edge(u, self.sink)

        self.source_edges = list(self.out_edges(self.source))
        self.sink_edges = list(self.in_edges(self.sink))
        self.source_sink_edges = set(self.source_edges + self.sink_edges)

    # ----------------------- Shared helper methods -----------------------
    def get_non_zero_flow_edges(
        self, flow_attr: str, edges_to_ignore: set = set()
    ) -> set:
        """Return set of edges whose attribute `flow_attr` is non-zero and not ignored."""
        non_zero_flow_edges = set()
        for u, v, data in self.edges(data=True):
            if (u, v) not in edges_to_ignore and data.get(flow_attr, 0) != 0:
                non_zero_flow_edges.add((u, v))
        return non_zero_flow_edges

    def get_max_flow_value_and_check_non_negative_flow(
        self, flow_attr: str, edges_to_ignore: set
    ) -> float:
        """Return maximum value of `flow_attr` over edges (ignoring some) verifying non-negativity.

        Raises ValueError if any required attribute missing or negative.
        """
        w_max = float("-inf")
        if edges_to_ignore is None:
            edges_to_ignore = set()
        for u, v, data in self.edges(data=True):
            if (u, v) in edges_to_ignore:
                continue
            if flow_attr not in data:
                utils.logger.error(
                    f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'."
                )
                raise ValueError(
                    f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'."
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

