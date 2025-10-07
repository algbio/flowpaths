import flowpaths as fp
import networkx as nx

def test_min_flow_decomp(filename: str):
    graph = fp.graphutils.read_graphs(filename)[0]
    print("graph id", graph.graph["id"])
    print("subset_constraints", graph.graph["constraints"])
    # fp.utils.draw(
    #         G=graph,
    #         filename=filename + ".pdf",
    #         flow_attr="flow",
    #         subpath_constraints=graph.graph["constraints"],
    #         draw_options={
    #         "show_graph_edges": True,
    #         "show_edge_weights": True,
    #         "show_path_weights": False,
    #         "show_path_weight_on_first_edge": True,
    #         "pathwidth": 2,
    #         "style": "points",
    #     })

    print(graph.graph["n"], graph.graph["m"], graph.graph["w"])

    mfd_model = fp.kFlowDecomp(
        G=graph,
        flow_attr="flow",
        k = 15,
        weight_type=int,
        optimization_options={
            "optimize_with_safe_sequences": True, # set to false to deactivate the safe sequences optimization
            "optimize_with_safe_paths": False, # set to false to deactivate the safe paths optimization
            "optimize_with_flow_safe_paths": False,
            "optimize_with_safe_zero_edges": True,
            "optimize_with_greedy": False,
        },
        solver_options={
            "external_solver": "highs", # we can try also "highs" at some point
            "time_limit": 300, # 300s = 5min, is it ok?
            "threads": 1
        },
    )
    mfd_model.solve()
    process_solution(mfd_model)

def process_solution(model):
    if model.is_solved():
        solution = model.get_solution()
        print("solution paths:", solution['paths'])
        print("solution weights:", solution['weights'])
        print("model.is_valid_solution()", model.is_valid_solution()) # Keep this to verify the solution
    else:
        print("Model could not be solved.")

    # fp.utils.draw(
    #         G=model.G,
    #         filename= "solution.pdf",
    #         flow_attr="flow",
    #         paths=model.get_solution().get('walks', None),
    #         weights=model.get_solution().get('weights', None),
    #         draw_options={
    #             "show_graph_edges": False,
    #             "show_edge_weights": False,
    #             "show_path_weights": False,
    #             "show_path_weight_on_first_edge": True,
    #             "pathwidth": 2,
    #             # "style": "points",
    #         })

    solve_statistics = model.solve_statistics
    print(solve_statistics)
    # print("node_number:", solve_statistics['node_number'])
    # print("edge_number:", solve_statistics['edge_number'])
    # print("safe_sequences_time:", solve_statistics.get('safe_sequences_time', 0)) # the time to compute safe sequences. use get(), as this is not set if not using safe sequences
    # print("edge_variables_total:", solve_statistics['edge_variables_total']) # number of edges * number of solution walks in the last iteration
    # print("edge_variables=1:", solve_statistics['edge_variables=1'])
    # print("edge_variables>=1:", solve_statistics['edge_variables>=1'])
    # print("edge_variables=0:", solve_statistics['edge_variables=0'])
    # print("graph_width:", solve_statistics['graph_width']) # the the minimum number of s-t walks needed to cover all edges
    # print("model_status:", solve_statistics['model_status'])
    # print("solve_time:", solve_statistics['solve_time']) # time taken by the ILP for a given k, or by MFD to iterate through k and do small internal things
    # print("solve_time_ilp:", solve_statistics['solve_time_ilp']) # time taken by the ILP for a given k, or by MFD to iterate through k and do small internal things

def main():
    # test_min_flow_decomp(filename = "tests/acyclic_graphs/gt15.kmer21.(288000.294000).V390.E560.acyc.graph")
    test_min_flow_decomp(filename = "tests/acyclic_graphs/gt15.kmer21.(612000.618000).V89.E128.acyc.graph")

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.INFO,
        log_to_console=True,
    )
    main()