import flowpaths as fp
import networkx as nx

# Create a simple graph
graph = nx.DiGraph()
graph.graph["id"] = "simple_graph"
graph.add_edge("s", "a", flow=6, length=2)
graph.add_edge("s", "b", flow=7, length=4)
graph.add_edge("a", "b", flow=2, length=6)
graph.add_edge("a", "c", flow=5, length=3)
graph.add_edge("b", "c", flow=9, length=1)
graph.add_edge("c", "d", flow=6, length=8)
graph.add_edge("c", "t", flow=7, length=9)
graph.add_edge("d", "t", flow=6, length=4)

width = fp.stDiGraph(graph).get_width(edges_to_ignore=[])

# Solve the minimum path error model
mpe_model = fp.kMinPathError(graph, flow_attr="flow", k=width, weight_type=float)
mpe_model.solve()

# Draw the solution
if mpe_model.is_solved():
    solution = mpe_model.get_solution()
    fp.utils.draw(
        G=graph,
        filename="test_graph_simple_graph.pdf",
        flow_attr="flow",
        paths=solution["paths"],
        weights=solution["weights"],
        draw_options={
        "show_graph_edges": True,
        "show_edge_weights": False,
        "show_path_weights": False,
        "show_path_weight_on_first_edge": True,
        "pathwidth": 2,
    })