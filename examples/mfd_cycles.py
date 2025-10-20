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
    mfd_model = fp.MinFlowDecompCycles(
        G=graph, 
        flow_attr="flow", 
        weight_type=int,
        )

    # We solve it
    mfd_model.solve()

    # We process its solution
    process_solution(graph, None, mfd_model)

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

    mfd_model = fp.MinFlowDecompCycles(
        G=graph, 
        flow_attr="flow", 
        weight_type=int,
        )
    mfd_model.solve()
    process_solution(graph, None, mfd_model)

def test3(filename: str):
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

    mfd_model = fp.kLeastAbsErrorsCycles(
        G=graph,
        flow_attr="flow",
        weight_type=float,
        optimization_options={
            "optimize_with_safe_sequences": True,
            "optimize_with_safety_as_subset_constraints": False,
        },
        solver_options={
            "external_solver": "gurobi",
            "time_limit": 300,
        },
    )
    mfd_model.solve()
    process_solution(graph, filename, mfd_model)

def process_solution(graph, filename = None, model: fp.MinFlowDecompCycles = None):
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
    # test1()
    # test2()
    test3(filename = "tests/cyclic_graphs/gt3.kmer15.(130000.132000).V23.E32.cyc100.graph")
    # test3(filename = "tests/cyclic_graphs/gt5.kmer15.(92000.94000).V76.E104.cyc64.graph")
    # test3(filename = "tests/cyclic_graphs/gt5.kmer27.(1300000.1400000).V809.E1091.mincyc1000.graph")

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.INFO,
        log_to_console=True,
    )
    main()