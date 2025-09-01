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
    graph.add_edge("0", "a", flow=6, length=2)
    graph.add_edge("0", "b", flow=7, length=4)
    graph.add_edge("a", "b", flow=2, length=6)
    graph.add_edge("a", "c", flow=5, length=3)
    graph.add_edge("b", "c", flow=9, length=1)
    graph.add_edge("c", "d", flow=6, length=8)
    graph.add_edge("c", "1", flow=7, length=9)
    graph.add_edge("d", "1", flow=6, length=4)

    # We create a Minimum Path Error solver with default settings, 
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges,
    # and that the number of paths to consider is 3.
    min_mpe_model = fp.NumPathsOptimization(
        model_type = fp.kMinPathError,
        stop_on_delta_rel=0.2,
        max_num_paths=10,
        G=graph, 
        flow_attr="flow",
        )
    
    min_mpe_model.solve()
    process_solution(min_mpe_model)

def process_solution(model: fp.kMinPathError):
    if model.is_solved():
        print(model.get_solution())
        print(model.solve_statistics)
        print("model.is_valid_solution()", model.is_valid_solution())
    else:
        print("Model could not be solved.")
        print(model.solve_statistics)

if __name__ == "__main__":
    main()