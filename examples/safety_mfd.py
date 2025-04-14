import flowpaths as fp
import networkx as nx

def main():
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
        log_file="log_mfd_example.log",
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

    # solving the model once to get the number of paths
    mfd_model = fp.MinFlowDecomp(
        graph,
        flow_attr="flow",
    )
    mfd_model.solve()
    mfd_solution = mfd_model.get_solution()
    k = len(mfd_solution["paths"])

    safety_model = fp.SafetyAbstractPathModelDAG(
        model_type=fp.kFlowDecomp,
        time_limit=10,
        G=graph,
        k=k,
        flow_attr="flow",
        )
    safety_model.solve()
    process_solution(safety_model)

def process_solution(model):
    if model.is_solved():
        print(f"The safe paths are {model.get_solution()}")
        print(model.solve_statistics)
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()