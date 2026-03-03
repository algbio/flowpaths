"""
Example demonstrating kLeastAbsErrors with cover_every_edge option.

This example creates a "bubble graph" where each bubble consists of two parallel
2-edge paths with different flow values. The cover_every_edge option ensures 
that every edge is covered by at least one of the k paths in the solution.
"""

import networkx as nx
import flowpaths as fp


def create_bubble_graph(pairs):
    """
    Create a bubble graph from a list of value pairs.
    
    Each pair (val1, val2) creates a bubble with:
    - Two parallel length-2 paths from node i to node i+1
    - Upper path: both edges have flow = val1
    - Lower path: both edges have flow = val2
    
    Parameters
    ----------
    pairs : list of tuples
        List of (val1, val2) pairs to create bubbles
        
    Returns
    -------
    G : nx.DiGraph
        The bubble graph with 'flow' attribute on edges
    """
    G = nx.DiGraph()
    
    for bubble_idx, (val1, val2) in enumerate(pairs):
        # Start and end nodes for this bubble (must be strings)
        start_node = str(bubble_idx)
        end_node = str(bubble_idx + 1)
        
        # Create intermediate nodes for the two parallel paths
        upper_middle = f"u{bubble_idx}"
        lower_middle = f"l{bubble_idx}"
        
        # Upper path (high flow): start -> upper_middle -> end
        G.add_edge(start_node, upper_middle, flow=val1)
        G.add_edge(upper_middle, end_node, flow=val1)
        
        # Lower path (low flow): start -> lower_middle -> end
        G.add_edge(start_node, lower_middle, flow=val2)
        G.add_edge(lower_middle, end_node, flow=val2)
    
    return G


def main():
    print("kLeastAbsErrors with cover_every_edge Example")
    print("=" * 70)
    
    # Create bubble graph with different flow pairs
    pairs = [(10, 3), (12, 5), (8, 4)]
    G = create_bubble_graph(pairs)
    
    # Solve with k=2 paths and cover_every_edge=True
    print("\nSolving with k=2 paths and cover_every_edge=True...")
    model = fp.kLeastAbsErrors(G, 
                               flow_attr='flow', 
                               weight_type=int,
                               k=2, 
                               cover_every_edge=True)
    model.solve()
    solution = model.get_solution()
    
    print(f"\nSolution paths:")
    for i, (path, weight) in enumerate(zip(solution['paths'], solution['weights'])):
        print(f"  Path {i + 1} (weight={weight:.1f}): {path}")
    
    total_error = sum(solution['edge_errors'].values())
    print(f"\nTotal absolute error: {total_error:.2f}")
    
    # Draw the solution
    print("\nDrawing visualization...")
    fp.graphutils.draw(
        G=G,
        filename="least_abs_errors_cover_every_edge.pdf",
        flow_attr="flow",
        paths=solution['paths'],
        weights=solution['weights'],
        draw_options={
            "show_graph_edges": True,
            "show_edge_weights": True,
            "show_path_weights": True,
            "show_path_weight_on_first_edge": False,
            "pathwidth": 3.0,
            "style": "default",
        }
    )
    print("Saved to: least_abs_errors_cover_every_edge.pdf")


if __name__ == "__main__":
    main()