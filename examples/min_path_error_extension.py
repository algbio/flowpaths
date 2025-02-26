import flowpaths as fp
import networkx as nx

def main():
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
    mpe_model = fp.kMinPathError(graph, flow_attr="flow", num_paths=3, weight_type=float, edge_length_attr="length")

    # We solve it
    mpe_model.solve()

    # We process its solution
    process_solution(mpe_model)

    edges_to_ignore = [("a", "c")]
    # We solve again, by telling the model to ignore the edges in `edges_to_ignore`
    # when computing the path slacks (i.e. edge errors)
    mpe_model_2 = fp.kMinPathError(graph, flow_attr="flow", num_paths=3, weight_type=int, edges_to_ignore=edges_to_ignore, edge_length_attr="length")
    mpe_model_2.solve()
    process_solution(mpe_model_2)

    edges_to_ignore = [("a", "c")]
    # We solve again, by telling the model to ignore the edges in `edges_to_ignore`
    # when computing the path slacks (i.e. edge errors)
    mpe_model_3 = fp.kMinPathError(graph, flow_attr="flow", num_paths=3, weight_type=int, edges_to_ignore=edges_to_ignore)
    mpe_model_3.solve()
    process_solution(mpe_model_3)

    path_length_ranges    = [[0, 15], [16, 18], [19, 20], [21, 30], [31, 100]]
    error_scale_factors   = [ 1.6   ,  1.0    ,  1.3    ,  1.7    ,  1.0     ]    
    # We solve again, by telling the model to ignore the edges in `edges_to_ignore`
    # when computing the path slacks (i.e. edge errors)
    mpe_model_4 = fp.kMinPathError(
        graph, 
        flow_attr="flow", 
        num_paths=3, 
        weight_type=int, 
        edge_length_attr="length", 
        path_length_ranges=path_length_ranges, 
        path_error_scale_factors=error_scale_factors,
        external_solver="gurobi"
        )  
    mpe_model_4.solve()
    process_solution(mpe_model_4)


def process_solution(model: fp.kMinPathError):
    if model.is_solved():
        solution = model.get_solution()
        print(
            "Solution paths, weights, slacks, solve statistics: ",
            solution[0],
            solution[1],
            solution[2],
            model.solve_statistics,
        )
        print("model.is_valid_solution()", model.is_valid_solution())
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()