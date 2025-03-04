import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_node("s", flow=13)
graph.add_node("a", flow=6)
graph.add_node("b", flow=9)
graph.add_node("c", flow=13)
graph.add_node("d", flow=6)
graph.add_node("t", flow=13)

# Adding edges
graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

# Expand the graph
ne_graph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")

# Solve the problem on the expanded graph
mfd_model = fp.kLeastAbsErrors(
    ne_graph, 
    k=3,
    flow_attr="flow",
    edges_to_ignore=ne_graph.edges_to_ignore,
    )
mfd_model.solve()

if mfd_model.is_solved():
    # Getting the solution in the expanded graph
    solution = mfd_model.get_solution()
    # Condensing the paths in the expanded graph to paths in the the original graph
    original_paths = ne_graph.condense_paths(solution["paths"])
    print("Original paths:", original_paths)
    print("Weights:", solution["weights"])
