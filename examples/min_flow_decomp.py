import flowpaths as fp
import networkx as nx

def main():
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=6)
    graph.add_edge("s", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "t", flow=7)
    graph.add_edge("d", "t", flow=6)

    # We create a Minimum Flow Decomposition solver with default settings,
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges.
    mfd_model = fp.MinFlowDecomp(graph, flow_attr="flow")
    fp.utils.logger.info("Created the Minimum Flow Decomposition solver")

    # We solve it
    mfd_model.solve()

    # We process its solution
    process_solution(mfd_model)

    # We solve again, by deactivating all optimizations, and 
    # setting the weights of the solution paths to int
    optimization_options = {
        "optimize_with_safe_paths": False,
        "optimize_with_safe_sequences": False,
        "optimize_with_safe_zero_edges": False,
        "optimize_with_greedy": False,
    }
    mfd_model_slow = fp.MinFlowDecomp(
        graph,
        flow_attr="flow",
        weight_type=int,
        optimization_options=optimization_options,
    )
    mfd_model_slow.solve()
    process_solution(mfd_model_slow)

    kfd_model_3 = fp.kFlowDecomp(graph, flow_attr="flow", k=3)
    kfd_model_3.solve()
    process_solution(kfd_model_3)

    kfd_model_4 = fp.kFlowDecomp(graph, flow_attr="flow", k=4)
    kfd_model_4.solve()
    process_solution(kfd_model_4)

def process_solution(model: fp.MinFlowDecomp):
    if model.is_solved():
        print(model.get_solution())
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()