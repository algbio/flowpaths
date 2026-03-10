#!/usr/bin/env python
"""
Create a small dataset by selecting graphs per width from a larger dataset.

For each unique width value found in the input dataset, selects a specified
number of graphs (first ones encountered) and saves them to a new file.

Usage:
    python create_small_dataset.py
"""

import gzip
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from benchmark_utils import DatasetLoader


def derive_output_path(input_path: str, graphs_per_width: int) -> str:
    """Derive output dataset path from input path and sampling parameter."""
    input_file = Path(input_path)
    suffixes = input_file.suffixes

    # Preserve historical format for .grp.gz files.
    if suffixes[-2:] == ['.grp', '.gz']:
        base_name = input_file.name[:-len('.grp.gz')]
        output_name = f"{base_name}_{graphs_per_width}_perwidth.grp.gz"
    elif suffixes:
        # Keep existing extension for other file types.
        ext = ''.join(suffixes)
        base_name = input_file.name[:-len(ext)]
        output_name = f"{base_name}_{graphs_per_width}_perwidth{ext}"
    else:
        output_name = f"{input_file.name}_{graphs_per_width}_perwidth"

    return str(input_file.with_name(output_name))


def write_graph_to_lines(graph):
    """
    Convert a graph back to the .grp format lines.
    
    Parameters
    ----------
    graph : nx.DiGraph
        Graph to convert
        
    Returns
    -------
    list of str
        Lines representing the graph in .grp format
    """
    lines = []
    
    # Header line with graph id
    graph_id = graph.graph.get('id', 'unknown')
    lines.append(f"#{graph_id}\n")
    
    # Number of nodes
    lines.append(f"{graph.number_of_nodes()}\n")
    
    # Edges with weights
    for u, v, data in graph.edges(data=True):
        flow = data.get('flow', 0)
        lines.append(f"{u} {v} {flow}\n")
    
    return lines


def create_small_dataset(
    input_path: str,
    output_path: str,
    graphs_per_width: int = 5
):
    """
    Select graphs from a dataset by taking a fixed number per width value.
    
    Parameters
    ----------
    input_path : str
        Path to input dataset
    output_path : str
        Path to output dataset
    graphs_per_width : int
        Number of graphs to select for each unique width value (default: 5)
    """
    print(f"Loading graphs from {input_path}...")
    loader = DatasetLoader(input_path)
    graphs = loader.load_graphs()
    print(f"Loaded {len(graphs)} graphs")
    
    # Group graphs by width
    width_groups = {}
    for graph in graphs:
        width = graph.graph.get('w', 0)
        if width not in width_groups:
            width_groups[width] = []
        width_groups[width].append(graph)
    
    print(f"Found {len(width_groups)} unique width values")
    
    # Select first graphs_per_width graphs for each width
    sampled_graphs = []
    for width in sorted(width_groups.keys()):
        graphs_with_width = width_groups[width]
        selected = graphs_with_width[:graphs_per_width]
        sampled_graphs.extend(selected)
        print(f"  Width {width}: selected {len(selected)} of {len(graphs_with_width)} graphs")
    
    print(f"\nTotal selected: {len(sampled_graphs)} graphs")
    
    # Create output directory if needed
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to output file
    print(f"Writing to {output_path}...")
    
    all_lines = []
    for graph in sampled_graphs:
        all_lines.extend(write_graph_to_lines(graph))
    
    # Write as gzip if output path ends with .gz
    if output_path.endswith('.gz'):
        with gzip.open(output_path, 'wt', encoding='utf-8') as f:
            f.writelines(all_lines)
    else:
        with open(output_path, 'w') as f:
            f.writelines(all_lines)
    
    print(f"✓ Successfully created dataset with {len(sampled_graphs)} graphs")
    
    # Print some statistics
    widths = [g.graph.get('w', 0) for g in sampled_graphs]
    if widths:
        print(f"\nDataset statistics:")
        print(f"  Width range: {min(widths)} - {max(widths)}")
        print(f"  Average width: {sum(widths) / len(widths):.1f}")
        
        nodes = [g.number_of_nodes() for g in sampled_graphs]
        edges = [g.number_of_edges() for g in sampled_graphs]
        print(f"  Nodes range: {min(nodes)} - {max(nodes)}")
        print(f"  Edges range: {min(edges)} - {max(edges)}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Create a smaller dataset by sampling a fixed number of graphs per width"
    )
    parser.add_argument(
        "--input",
        default="datasets/esa2025/Mouse.PacBio_reads.grp.gz",
        help="Path to input dataset (default: %(default)s)",
    )
    parser.add_argument(
        "--graphs-per-width",
        type=int,
        default=5,
        help="Number of graphs to select per width value (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Path to output dataset. If omitted, it is derived from --input as "
            "<input>_<graphs-per-width>_perwidth with the same extension(s)."
        ),
    )
    args = parser.parse_args()

    if args.graphs_per_width <= 0:
        parser.error("--graphs-per-width must be a positive integer")

    input_path = args.input
    graphs_per_width = args.graphs_per_width
    output_path = args.output or derive_output_path(input_path, graphs_per_width)
    
    print("="*70)
    print("Creating small dataset")
    print("="*70)
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Graphs per width: {graphs_per_width}")
    
    try:
        create_small_dataset(input_path, output_path, graphs_per_width)
        
        # Verify the output
        print("\nVerifying output...")
        loader = DatasetLoader(output_path)
        verification_graphs = loader.load_graphs()
        print(f"✓ Verification: Successfully loaded {len(verification_graphs)} graphs from output file")
        
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print(f"\nMake sure the input file exists: {input_path}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "="*70)
    print("Done!")
    print("="*70)


if __name__ == '__main__':
    main()
