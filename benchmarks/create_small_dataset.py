#!/usr/bin/env python
"""
Create a small dataset by sampling random graphs from a larger dataset.

Usage:
    python create_small_dataset.py
"""

import random
import gzip
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from benchmark_utils import DatasetLoader


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
    num_graphs: int = 50,
    seed: int = 42
):
    """
    Sample random graphs from a dataset and save to a new file.
    
    Parameters
    ----------
    input_path : str
        Path to input dataset
    output_path : str
        Path to output dataset
    num_graphs : int
        Number of graphs to sample
    seed : int
        Random seed for reproducibility
    """
    print(f"Loading graphs from {input_path}...")
    loader = DatasetLoader(input_path)
    graphs = loader.load_graphs()
    print(f"Loaded {len(graphs)} graphs")
    
    # Set random seed for reproducibility
    random.seed(seed)
    
    # Sample graphs
    if num_graphs >= len(graphs):
        print(f"Warning: Requested {num_graphs} graphs but dataset only has {len(graphs)}")
        sampled_graphs = graphs
    else:
        sampled_graphs = random.sample(graphs, num_graphs)
        print(f"Sampled {len(sampled_graphs)} random graphs")
    
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
    # Configuration
    input_path = "datasets/esa2025/Mouse.PacBio_reads.grp.gz"
    output_path = "datasets/small/Mouse.PacBio_reads_500.grp.gz"
    num_graphs = 500
    seed = 42
    
    print("="*70)
    print("Creating small dataset")
    print("="*70)
    
    try:
        create_small_dataset(input_path, output_path, num_graphs, seed)
        
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
