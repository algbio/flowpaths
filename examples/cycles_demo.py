import flowpaths as fp
import networkx as nx

def test(filename: str):
    graph = fp.graphutils.read_graphs(filename)[0]
    print("graph id", graph.graph["id"])
    # print("subset_constraints", graph.graph["constraints"])
    fp.utils.draw(
            G=graph,
            filename=filename + ".pdf",
            flow_attr="flow",
            subpath_constraints=graph.graph["constraints"],
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
        subset_constraints=graph.graph["constraints"], # try with and without
        optimization_options={
            "optimize_with_safe_sequences": True, # set to false to deactivate the safe sequences optimization
        },
        solver_options={
            "external_solver": "gurobi", # we can try also "highs" at some point
            "time_limit": 300, # 300s = 5min, is it ok?
        },
    )
    mfd_model.solve()
    process_solution(mfd_model)

    # note that here below we are not passing k, as it will be chosen as the graph width
    klae_model = fp.kLeastAbsErrorsCycles(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        subset_constraints=graph.graph["constraints"], # try with and without
        optimization_options={
            "optimize_with_safe_sequences": True, # set to false to deactivate the safe sequences optimization
        },
        solver_options={
            "external_solver": "gurobi", # we can try also "highs" at some point
            "time_limit": 300, # 300s = 5min, is it ok?
        },
    )
    klae_model.solve()
    process_solution(klae_model)

    # note that here below we are not passing k, as it will be chosen as the graph width
    kmpe_model = fp.kMinPathErrorCycles(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        subset_constraints=graph.graph["constraints"], # try with and without
        optimization_options={
            "optimize_with_safe_sequences": True, # set to false to deactivate the safe sequences optimization
        },
        solver_options={
            "external_solver": "gurobi", # we can try also "highs" at some point
            "time_limit": 300, # 300s = 5min, is it ok?
        },
    )
    kmpe_model.solve()
    process_solution(kmpe_model)

def process_solution(model):
    if model.is_solved():
        solution = model.get_solution()
        solve_statistics = model.solve_statistics
        print(solve_statistics)
        print("solution walks:", solution['walks'])
        print("solution weights:", solution['weights'])
        print("model.is_valid_solution()", model.is_valid_solution()) # Keep this to verify the solution
        print("node_number:", solve_statistics['node_number'])
        print("edge_number:", solve_statistics['edge_number'])
        print("safe_sequences_time:", solve_statistics.get('safe_sequences_time', 0)) # the time to compute safe sequences. use get(), as this is not set if not using safe sequences
        print("edge_variables_total:", solve_statistics['edge_variables_total']) # number of edges * number of solution walks in the last iteration
        print("edge_variables=1:", solve_statistics['edge_variables=1'])
        print("edge_variables>=1:", solve_statistics['edge_variables>=1'])
        print("graph_width:", solve_statistics['graph_width']) # the the minimum number of s-t walks needed to cover all edges
        print("model_status:", solve_statistics['model_status'])
        print("solve_time:", solve_statistics['solve_time']) # time taken by the ILP for a given k, or by MFD to iterate through k and do small internal things
        print("number_of_nontrivial_SCCs:", solve_statistics['number_of_nontrivial_SCCs']) # trivial = at least one edge
        print("size_of_largest_SCC:", solve_statistics['size_of_largest_SCC']) # size = number of edges
    else:
        print("Model could not be solved.")

def main():
    test(filename = "tests/cyclic_graphs/gt5.kmer27.(630000.660000).V111.E154.mincyc100.graph")

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.INFO,
        log_to_console=True,
    )
    main()