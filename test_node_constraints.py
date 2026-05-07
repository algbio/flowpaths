#!/usr/bin/env python3
"""
Test script demonstrating node-based sequence constraints in draw() function.
"""

import networkx as nx
import sys
sys.path.insert(0, '/Users/tomescu/Documents/GitHub/flowpaths')

from flowpaths.utils import graphutils

# Create a simple DAG
G = nx.DiGraph()
G.add_edges_from([
    ('s', 'a', {'flow': 5}),
    ('s', 'b', {'flow': 3}),
    ('a', 'c', {'flow': 5}),
    ('b', 'c', {'flow': 3}),
    ('c', 'd', {'flow': 8}),
    ('d', 't', {'flow': 8}),
])

G.graph['id'] = 'test_graph'

# Example 1: Node-based constraints (NEW)
print("Test 1: Node-based constraints (list of nodes)")
print("=" * 50)

# Define constraints as sequences of nodes
constraints_by_nodes = [
    ['s', 'a', 'c', 'd'],  # Path through a
    ['s', 'b', 'c', 'd'],  # Path through b
]

# Draw with node-based constraints
graphutils.draw(
    G,
    filename='/tmp/test_node_constraints.pdf',
    flow_attr='flow',
    subpath_constraints=constraints_by_nodes,
    draw_options={'show_edge_weights': True, 'show_graph_title': True}
)
print("✓ Generated: /tmp/test_node_constraints.pdf")
print("  - Nodes in each constraint are highlighted with distinct colors")
print("  - Edges between consecutive nodes in each constraint are dashed")

# Example 2: Edge-based constraints (EXISTING, still supported)
print("\nTest 2: Edge-based constraints (list of edges) - backwards compatible")
print("=" * 50)

constraints_by_edges = [
    [('s', 'a'), ('a', 'c'), ('c', 'd')],
    [('s', 'b'), ('b', 'c'), ('c', 'd')],
]

graphutils.draw(
    G,
    filename='/tmp/test_edge_constraints.pdf',
    flow_attr='flow',
    subpath_constraints=constraints_by_edges,
    draw_options={'show_edge_weights': True, 'show_graph_title': True}
)
print("✓ Generated: /tmp/test_edge_constraints.pdf")
print("  - Only edges (not nodes) are highlighted")
print("  - Backward compatible with existing code")

# Example 3: Mixed constraints
print("\nTest 3: Node-based with paths overlay")
print("=" * 50)

paths = [
    ['s', 'a', 'c', 'd', 't'],
    ['s', 'b', 'c', 'd', 't'],
]
weights = [5, 3]

constraints_by_nodes = [
    ['a', 'c'],  # Intermediate segment
    ['b', 'c'],  # Another intermediate segment
]

graphutils.draw(
    G,
    filename='/tmp/test_mixed_constraints.pdf',
    flow_attr='flow',
    paths=paths,
    weights=weights,
    subpath_constraints=constraints_by_nodes,
    draw_options={'show_edge_weights': True, 'show_graph_title': True}
)
print("✓ Generated: /tmp/test_mixed_constraints.pdf")
print("  - Paths are shown as thick colored edges")
print("  - Constraint nodes are highlighted with distinct colors")

print("\n" + "=" * 50)
print("All tests completed successfully!")
print("=" * 50)
