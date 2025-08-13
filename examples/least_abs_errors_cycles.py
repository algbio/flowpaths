import flowpaths as fp
import networkx as nx

def test1():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=1)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("b", "a", flow=2)
    graph.add_edge("a", "t", flow=1)

    # We create a Least Absolute Errors solver with default settings, 
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges,
    # and that the number of paths to consider is 1.
    lae_model = fp.kLeastAbsErrorsCycles(
        G=graph, 
        flow_attr="flow", 
        k=1, 
        weight_type=int,
        )

    # We solve it
    lae_model.solve()

    # We process its solution
    process_solution(graph, lae_model)

def test2():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=3)
    graph.add_edge("a", "t", flow=3)
    graph.add_edge("s", "b", flow=6)
    graph.add_edge("b", "a", flow=2)
    graph.add_edge("a", "h", flow=2)
    graph.add_edge("h", "t", flow=6)
    graph.add_edge("b", "c", flow=4)
    graph.add_edge("c", "d", flow=4)
    graph.add_edge("c", "h", flow=4)
    graph.add_edge("d", "h", flow=0)
    graph.add_edge("d", "e", flow=4)
    graph.add_edge("e", "c", flow=4)
    graph.add_edge("e", "f", flow=4)
    graph.add_edge("f", "g", flow=4)
    graph.add_edge("g", "e", flow=4)

    lae_model = fp.kLeastAbsErrorsCycles(
        G=graph, 
        flow_attr="flow", 
        k=3, 
        weight_type=int,
        )
    lae_model.solve()
    process_solution(graph, lae_model)

def process_solution(graph, model: fp.kLeastAbsErrors):
    if model.is_solved():
        print(model.get_solution())
        print("model.is_valid_solution()", model.is_valid_solution())
        fp.utils.draw(
            G=graph,
            filename=f"least-abs_errors_cycles_example.pdf",
            flow_attr="flow",
            paths=model.get_solution()["walks"],
            weights=model.get_solution()["weights"],
            draw_options={
            "show_graph_edges": True,
            "show_edge_weights": False,
            "show_path_weights": False,
            "show_path_weight_on_first_edge": True,
            "pathwidth": 2,
        })
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )

    # test1()
    test2()