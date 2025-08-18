import flowpaths as fp
import networkx as nx


def test():
    graph = nx.DiGraph()
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")
    graph.add_edge("s", "b")
    graph.add_edge("b", "a")
    graph.add_edge("a", "h")
    graph.add_edge("h", "t")
    graph.add_edge("b", "c")
    graph.add_edge("c", "d")
    graph.add_edge("c", "h")
    graph.add_edge("d", "h")
    graph.add_edge("d", "e")
    graph.add_edge("e", "c")
    graph.add_edge("e", "f")
    graph.add_edge("f", "g")
    graph.add_edge("g", "e")

    mpc_model = fp.MinPathCoverCycles(G=graph)
    mpc_model.solve()

    if mpc_model.is_solved():
        print(mpc_model.get_solution())

    process_solution(graph, 4, "test", mpc_model)

    subset_constraints=[[("b", "a"),("a", "t")]]
    mpc_model_sc = fp.MinPathCoverCycles(
        graph,
        subset_constraints=subset_constraints,
    )
    mpc_model_sc.solve()

    process_solution(graph, 4, "test_sc", mpc_model_sc)

def test3(k: int, filename: str):
    # read the graph from file
    graph = fp.graphutils.read_graphs(filename)[0]
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

    mpc_model = fp.MinPathCoverCycles(
        G=graph,
        optimization_options={
            "optimize_with_safe_sequences": True,
            "optimize_with_safety_as_subset_constraints": False,
        },
        solver_options={"external_solver": "highs"},
    )
    mpc_model.solve()
    process_solution(graph, k, filename, mpc_model)

def process_solution(graph, k: int, filename = None, model = None):
    if model.is_solved():
        print(model.get_solution())
        assert len(model.get_solution()["walks"]) == k
        print("model.is_valid_solution()", model.is_valid_solution())
        if filename is not None:
            fp.utils.draw(
                G=graph,
                filename=filename + ".solved.pdf",
                flow_attr="flow",
                paths=model.get_solution()["walks"],
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

def main():
    test()
    # test3(k = 2, filename = "tests/cyclic_graphs/gt3.kmer15.(130000.132000).V23.E32.cyc100.graph")
    # test3(k = 4, filename = "tests/cyclic_graphs/gt5.kmer15.(92000.94000).V76.E104.cyc64.graph")

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.INFO,
        log_to_console=True,
    )
    main()