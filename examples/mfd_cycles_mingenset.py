import flowpaths as fp
import networkx as nx

def test(filename: str):
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

    mfd_model = fp.MinFlowDecompCycles(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        optimization_options={
            "optimize_with_safe_sequences": True,
            "optimize_with_safety_as_subset_constraints": False,
            "use_min_gen_set_lowerbound": False,
            "optimize_with_guessed_weights": False,
        },
        solver_options={"external_solver": "highs"},
    )
    mfd_model.solve()
    process_solution(graph, filename, mfd_model)

def process_solution(graph, filename = None, model: fp.kFlowDecompCycles = None):
    if model.is_solved():
        print(model.get_solution())
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

def main():
    # test(filename = "tests/cyclic_graphs/gt3.kmer15.(130000.132000).V23.E32.cyc100.graph")
    # test(filename = "tests/cyclic_graphs/gt4.kmer15.(2898000.2900000).V29.E40.cyc448.graph")
    test(filename = "tests/cyclic_graphs/gt5.kmer15.(92000.94000).V76.E104.cyc64.graph")
    # test(filename = "tests/cyclic_graphs/gt6.kmer15.(4208000.4210000).V33.E50.cyc157.graph")

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    main()