"""
Example demonstrating the Sankey diagram visualization feature.

This script includes two examples:

Example 1 - Simple Flow Network:
  - Creates a small flow network with 8 edges
  - Solves with Minimum Flow Decomposition
  - Generates Sankey diagrams and traditional graphviz visualization

Example 2 - Real Graph with k-Least Absolute Errors:
  - Loads a real graph from the test suite (89 nodes, 128 edges)
  - Solves with k-Least Absolute Errors (k=5)
  - Demonstrates visualization of complex graphs

Both examples show:
- How to visualize flow decompositions as interactive Sankey diagrams
- Automatic generation of both HTML (interactive) and static image (PDF) files
- Using graph IDs for automatic diagram titles
"""

import networkx as nx
import flowpaths as fp
from flowpaths.utils import graphutils

def create_example_graph():
    """Create a sample DAG with flow values."""
    G = nx.DiGraph()
    G.graph["id"] = "simple_flow_network"  # Set graph ID for diagram title
    
    # Add edges with flow values
    G.add_edge('s', 'a', flow=10)
    G.add_edge('s', 'b', flow=5)
    G.add_edge('a', 'c', flow=6)
    G.add_edge('a', 'd', flow=4)
    G.add_edge('b', 'c', flow=3)
    G.add_edge('b', 'd', flow=2)
    G.add_edge('c', 't', flow=9)
    G.add_edge('d', 't', flow=6)
    
    return G

def main():
    print("="*70)
    print("Example 1: Simple Flow Network with Minimum Flow Decomposition")
    print("="*70)
    print("\nCreating example graph...")
    G = create_example_graph()
    
    print("Computing minimum flow decomposition...")
    solver = fp.MinFlowDecomp(G, flow_attr='flow')
    solver.solve()
    solution = solver.get_solution()
    
    paths = solution['paths']
    weights = solution['weights']
    
    print(f"\nFound {len(paths)} paths:")
    for i, (path, weight) in enumerate(zip(paths, weights), 1):
        print(f"  Path {i}: {' → '.join(path)} (weight: {weight})")
    
    # Draw as Sankey diagram (automatically saves both HTML and PDF)
    print("\nGenerating Sankey diagram...")
    graphutils.draw(
        G,
        filename="sankey_example",  # Will create both .html and .pdf
        flow_attr='flow',
        paths=paths,
        weights=weights,
        draw_options={
            "style": "sankey",
            # "sankey_arrowlen": 15,
            "sankey_color_toggle": True,
            "sankey_arrow_toggle": True,
        }
    )
    print("✓ Both interactive (HTML) and static (PDF) versions have been created")
    print("  - sankey_example.html: Open in a web browser for interactive diagram")
    print("  - sankey_example.pdf: Static image for presentations/papers")
    
    # You can specify a different static format (PNG, SVG):
    # graphutils.draw(
    #     G,
    #     filename="sankey_example.png",  # Creates .html and .png
    #     flow_attr='flow',
    #     paths=paths,
    #     weights=weights,
    #     draw_options={"style": "sankey"}
    # )
    
    # For comparison, also generate traditional graphviz visualization
    print("\nGenerating traditional visualization for comparison...")
    graphutils.draw(
        G,
        filename="traditional_example.pdf",
        flow_attr='flow',
        paths=paths,
        weights=weights,
        draw_options={
            "style": "default",
            "show_edge_weights": True,
            "show_path_weight_on_first_edge": True
        }
    )
    print("✓ Traditional graphviz diagram saved as 'traditional_example.pdf'")

def example_real_graph():
    """Example using a real graph from the test suite with kLeastAbsErrors."""
    print("\n" + "="*70)
    print("Example 2: Real Graph with k-Least Absolute Errors")
    print("="*70)
    
    # Load a real graph from the test suite
    graph_file = "tests/acyclic_graphs/gt15.kmer21.(612000.618000).V89.E128.acyc.graph"
    print(f"\nLoading graph from {graph_file}...")
    G = graphutils.read_graphs(graph_file)[0]
    
    print(f"Graph loaded: {G.graph.get('id', 'unknown')}")
    print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    
    # Solve with k-Least Absolute Errors
    k = 5  # Find 5 paths that minimize absolute errors
    print(f"\nSolving with k-Least Absolute Errors (k={k})...")
    solver = fp.kLeastAbsErrors(
        G, 
        flow_attr='flow', 
        k=k,
        weight_type=float
    )
    solver.solve() 
    
    if solver.is_solved():
        solution = solver.get_solution()
        paths = solution['paths']
        weights = solution['weights']
        
        print(f"\nFound {len(paths)} paths:")
        for i, (path, weight) in enumerate(zip(paths, weights), 1):
            path_str = ' → '.join(str(n) for n in path[:5])  # Show first 5 nodes
            if len(path) > 5:
                path_str += f" → ... → {path[-1]} ({len(path)} nodes)"
            print(f"  Path {i}: {path_str} (weight: {weight:.2f})")
        
        # Generate Sankey diagram
        print(f"\nGenerating Sankey diagram for real graph...")
        graphutils.draw(
            G,
            filename="sankey_real_graph",
            flow_attr='flow',
            paths=paths,
            weights=weights,
            draw_options={
                "style": "sankey"
            }
        )
        print("✓ Both interactive (HTML) and static (PDF) versions created:")
        print("  - sankey_real_graph.html")
        print("  - sankey_real_graph.pdf")
    else:
        print("⚠ Solver did not find a solution")

if __name__ == "__main__":
    main()
    example_real_graph()
