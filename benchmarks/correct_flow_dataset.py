"""
Create a flow-conserving copy of a dataset.

Given an input dataset (.grp, .graph, .grp.gz, .graph.gz, or .zip), this script
loads all graphs, applies MinErrorFlow to graphs that violate flow conservation,
and writes a corrected dataset in the same container format as the input.

Examples
--------
python correct_flow_dataset.py \
    --input datasets/esa2025/Mouse.PacBio_reads.grp.gz

python correct_flow_dataset.py \
    --input datasets/esa2025/Mouse.PacBio_reads.grp.gz \
    --output datasets/esa2025/Mouse.PacBio_reads.flow_corrected.grp.gz
"""

import argparse
import gzip
from pathlib import Path
import sys
import zipfile

# Add parent directory to path to import benchmark_utils
sys.path.insert(0, str(Path(__file__).parent))

import flowpaths as fp
from benchmark_utils import DatasetLoader


FLOW_ATTR = "flow"
WEIGHT_TYPE = float


def get_flow_conserving_graph(graph, flow_attr: str, solver_options: dict):
    """
    Return a graph that satisfies flow conservation.

    If flow conservation is violated, run MinErrorFlow once to correct the graph.
    """
    if fp.utils.check_flow_conservation(graph, flow_attr):
        return graph, False

    correction_model = fp.MinErrorFlow(
        G=graph,
        flow_attr=flow_attr,
        weight_type=WEIGHT_TYPE,
        solver_options=solver_options,
    )
    correction_model.solve()
    if not correction_model.is_solved():
        raise RuntimeError(
            f"MinErrorFlow failed on graph id={graph.graph.get('id', 'unknown')} "
            f"with status {correction_model.solver.get_model_status()}"
        )

    corrected_graph = correction_model.get_corrected_graph()
    return corrected_graph, True


def detect_container_format(path: Path) -> str:
    """Return one of: 'plain', 'gz', 'zip'."""
    suffix = path.suffix.lower()
    if suffix == ".gz":
        return "gz"
    if suffix == ".zip":
        return "zip"
    return "plain"


def build_default_output_path(input_path: Path) -> Path:
    """Create default output path while preserving the input container format."""
    if input_path.suffix.lower() == ".gz" and len(input_path.suffixes) >= 2:
        # e.g. foo.grp.gz -> foo.flow_corrected.grp.gz
        base = input_path.name[: -len(".gz")]
        if "." in base:
            root, ext = base.rsplit(".", 1)
            return input_path.with_name(f"{root}.flow_corrected.{ext}.gz")
        return input_path.with_name(f"{base}.flow_corrected.gz")

    if input_path.suffix.lower() == ".zip":
        # e.g. foo.zip -> foo.flow_corrected.zip
        return input_path.with_name(f"{input_path.stem}.flow_corrected.zip")

    # plain text: foo.grp -> foo.flow_corrected.grp
    if "." in input_path.name:
        root, ext = input_path.name.rsplit(".", 1)
        return input_path.with_name(f"{root}.flow_corrected.{ext}")
    return input_path.with_name(f"{input_path.name}.flow_corrected")


def _subpath_to_nodes(subpath_edges):
    """Convert a subpath edge list [(u,v), ...] back to a node sequence [u,v,...]."""
    if not subpath_edges:
        return []

    first_u, first_v = subpath_edges[0]
    nodes = [str(first_u), str(first_v)]
    for u, v in subpath_edges[1:]:
        if str(u) != nodes[-1]:
            # Non-chain subpath; cannot reconstruct a clean node path.
            return []
        nodes.append(str(v))
    return nodes


def serialize_graph(graph, flow_attr: str) -> str:
    """Serialize one graph block in a format compatible with graphutils.read_graph."""
    lines = []

    graph_id = str(graph.graph.get("id", "unknown"))
    lines.append(f"# {graph_id}\n")

    constraints = graph.graph.get("constraints", [])
    for subpath_edges in constraints:
        nodes = _subpath_to_nodes(subpath_edges)
        if len(nodes) >= 2:
            lines.append("#S " + " ".join(nodes) + "\n")

    lines.append(f"{graph.number_of_nodes()}\n")

    for u, v in sorted(graph.edges(), key=lambda e: (str(e[0]), str(e[1]))):
        flow_val = graph[u][v].get(flow_attr, 0.0)
        lines.append(f"{u} {v} {float(flow_val)}\n")

    return "".join(lines)


def serialize_dataset(graphs, flow_attr: str) -> str:
    """Serialize all graphs into one dataset text blob."""
    blocks = [serialize_graph(graph, flow_attr).rstrip("\n") for graph in graphs]
    return "\n".join(blocks) + "\n"


def write_dataset_text(output_path: Path, text: str, input_format: str):
    """Write serialized dataset using the same container format as input."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if input_format == "gz":
        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            f.write(text)
        return

    if input_format == "zip":
        inner_name = output_path.stem + ".grp"
        with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(inner_name, text)
        return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    parser = argparse.ArgumentParser(
        description="Create a flow-conserving copy of a dataset via MinErrorFlow."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input dataset path (.grp, .graph, .grp.gz, .graph.gz, or .zip)",
    )
    parser.add_argument(
        "--output",
        help="Output dataset path. If omitted, uses '<input>.flow_corrected' with same format.",
    )
    parser.add_argument(
        "--flow-attr",
        default=FLOW_ATTR,
        help="Flow attribute name on edges (default: flow)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Solver threads for MinErrorFlow (default: 1)",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=300,
        help="Time limit per correction solve in seconds (default: 300)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail immediately if any graph cannot be corrected.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else build_default_output_path(input_path)

    input_format = detect_container_format(input_path)
    output_format = detect_container_format(output_path)
    if output_format != input_format:
        print(
            "Error: output format must match input format "
            f"(input={input_format}, output={output_format})."
        )
        sys.exit(1)

    solver_options = {
        "threads": args.threads,
        "log_to_console": "false",
        "time_limit": args.time_limit,
    }

    loader = DatasetLoader(str(input_path))
    print(f"Loading dataset: {input_path}")
    graphs = loader.load_graphs()
    print(f"Loaded {len(graphs)} graphs")

    corrected_graphs = []
    already_conserving = 0
    corrected = 0
    failed = 0

    for idx, graph in enumerate(graphs, start=1):
        graph_id = graph.graph.get("id", f"graph_{idx}")
        try:
            graph_out, was_corrected = get_flow_conserving_graph(
                graph=graph,
                flow_attr=args.flow_attr,
                solver_options=solver_options,
            )
            corrected_graphs.append(graph_out)
            if was_corrected:
                corrected += 1
                print(f"[{idx}/{len(graphs)}] corrected: {graph_id}")
            else:
                already_conserving += 1
        except Exception as exc:
            failed += 1
            msg = f"[{idx}/{len(graphs)}] failed correction: {graph_id} ({exc})"
            if args.strict:
                print("Error:", msg)
                sys.exit(1)
            print("Warning:", msg)
            corrected_graphs.append(graph)

    dataset_text = serialize_dataset(corrected_graphs, flow_attr=args.flow_attr)
    write_dataset_text(output_path, dataset_text, input_format=input_format)

    print("\nDone.")
    print(f"Output: {output_path}")
    print(
        "Summary: "
        f"{already_conserving} already conserving, "
        f"{corrected} corrected, {failed} failed"
    )


if __name__ == "__main__":
    main()
