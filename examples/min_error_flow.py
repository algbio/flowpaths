import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=7)
    graph.add_edge("s", "b", flow=7)
    graph.add_edge("a", "b", flow=3)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=7)
    graph.add_edge("c", "t", flow=7)
    graph.add_edge("d", "t", flow=6)

    # We create a Minimum Flow Decomposition solver with default settings,
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges.
    correction_model = fp.MinErrorFlow(
        graph, 
        flow_attr="flow",
        weight_type=float,
        sparsity_lambda=0,
        # edges_to_ignore=[('c','d')],
        # additional_starts=['c'],
        # additional_ends=['b','d'],
    )

    # We solve it
    correction_model.solve()

    # We process its solution
    process_solution(graph, correction_model)


def process_solution(graph: nx.DiGraph, model: fp.MinErrorFlow):
    if model.is_solved():
        solution = model.get_solution()
        print(solution["graph"].edges(data=True))
        print(solution["error"])
        fp.utils.draw_solution(graph, filename="uncorrected_graph.pdf", flow_attr="flow", draw_options={"show_edge_weights": True})
        fp.utils.draw_solution(solution["graph"], filename="corrected_graph.pdf", flow_attr="flow", draw_options={"show_edge_weights": True})
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()