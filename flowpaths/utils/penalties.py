import numbers
import networkx as nx
from .logging import logger


def _linear_quantile(values: list[float], q: float) -> float:
    """Compute quantile by linear interpolation (q in [0, 1])."""
    if len(values) == 0:
        return 0.0
    if len(values) == 1:
        return values[0]

    sorted_values = sorted(values)
    idx = (len(sorted_values) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def auto_additional_edges_lambda(
    G: nx.DiGraph,
    flow_attr: str,
    flow_attr_origin: str = "edge",
    graph_width: float | None = None,
    quantile: float = 0.9,
    scale: float = 0.1,
    min_lambda: float = 1.0,
) -> float:
    """
    Graph-dependent default for additional_edges_lambda.

    Formula:
        max(min_lambda, scale * (Q_quantile(flow_values) / max(1, graph_width)))

    - flow_values are edge flows when flow_attr_origin="edge"
    - flow_values are node flows when flow_attr_origin="node"
    """
    if not isinstance(G, nx.DiGraph):
        raise ValueError("G must be a networkx.DiGraph")
    if flow_attr_origin not in ["edge", "node"]:
        raise ValueError(f"flow_attr_origin must be 'edge' or 'node', not {flow_attr_origin}")
    if quantile < 0 or quantile > 1:
        raise ValueError(f"quantile must be in [0,1], not {quantile}")
    if scale < 0:
        raise ValueError(f"scale must be non-negative, not {scale}")
    if min_lambda < 0:
        raise ValueError(f"min_lambda must be non-negative, not {min_lambda}")

    if flow_attr_origin == "node":
        flow_values = [
            float(data[flow_attr])
            for _, data in G.nodes(data=True)
            if flow_attr in data and isinstance(data[flow_attr], numbers.Real)
        ]
    else:
        flow_values = [
            float(data[flow_attr])
            for _, _, data in G.edges(data=True)
            if flow_attr in data and isinstance(data[flow_attr], numbers.Real)
        ]

    q_value = _linear_quantile(flow_values, quantile)

    resolved_width = graph_width
    if resolved_width is None:
        w_from_graph = G.graph.get("w")
        if isinstance(w_from_graph, numbers.Real):
            resolved_width = float(w_from_graph)
        else:
            try:
                from flowpaths import stdigraph as _stdigraph  # type: ignore

                resolved_width = float(_stdigraph.stDiGraph(G).get_width())
            except Exception:
                resolved_width = 1.0

    if not isinstance(resolved_width, numbers.Real) or resolved_width <= 0:
        resolved_width = 1.0

    lambda_auto = max(min_lambda, scale * (q_value / float(resolved_width)))
    logger.debug(
        "auto_additional_edges_lambda: flow_attr=%s, origin=%s, q=%.4f, width=%.4f, value=%.4f",
        flow_attr,
        flow_attr_origin,
        q_value,
        float(resolved_width),
        lambda_auto,
    )
    return float(lambda_auto)
