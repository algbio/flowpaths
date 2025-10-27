import flowpaths as fp
import networkx as nx

def test():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=1)
    graph.add_edge("a", "t", flow=1)
    graph.add_edge("s", "b", flow=2)
    graph.add_edge("b", "a", flow=2)
    graph.add_edge("a", "h", flow=3)
    graph.add_edge("h", "t", flow=3)
    graph.add_edge("b", "c", flow=4)
    graph.add_edge("c", "d", flow=4)
    graph.add_edge("c", "h", flow=5)
    graph.add_edge("d", "h", flow=5)
    graph.add_edge("d", "e", flow=6)
    graph.add_edge("e", "c", flow=6)
    graph.add_edge("e", "f", flow=7)
    graph.add_edge("f", "g", flow=7)
    graph.add_edge("g", "e", flow=8)

    # lae_model = fp.kLeastAbsErrorsCycles(
    #     G=graph, 
    #     flow_attr="flow", 
    #     k=3, 
    #     weight_type=int,
    #     trusted_edges_for_safety_percentile=25,
    #     )
    # lae_model.solve()
    # process_solution(graph, None, lae_model)

    mpe_model = fp.kMinPathErrorCycles(
        G=graph, 
        flow_attr="flow",
        weight_type=int,
        elements_to_ignore_percentile=50,
        )
    mpe_model.solve()
    process_solution(graph, "test_mpe_percentile", mpe_model)

def process_solution(graph, filename, model: fp.kLeastAbsErrors):
    if model.is_solved():
        # print(model.get_solution())
        print("model.is_valid_solution()", model.is_valid_solution())
        if filename is not None:
            fp.utils.draw(
                G=graph,
                filename=filename + ".solved.pdf",
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
        print("Statistics", model.solve_statistics)
    else:
        print("Model could not be solved.")
        fp.utils.draw(
            G=graph,
            filename=filename + ".pdf",
            flow_attr="flow",
            draw_options={
            "show_graph_edges": True,
            "show_edge_weights": True,
            "show_path_weights": False,
            "show_path_weight_on_first_edge": True,
            "pathwidth": 2,
        })

def main():
    test()    

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    main()