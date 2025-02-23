import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("0", "a", flow=3)
    graph.add_edge("0", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=7)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "1", flow=7)
    graph.add_edge("d", "1", flow=3)

    # We create a Least Absolute Errors solver with default settings, 
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges,
    # and that the number of paths to consider is 3.
    lae_model = fp.kLeastAbsErrors(graph, flow_attr="flow", num_paths=3, weight_type=float)

    # We solve it
    lae_model.solve()

    # We process its solution
    process_solution(lae_model)

    edges_to_ignore = [("a", "c")]
    # We solve again, by telling the model to ignore the edges in `edges_to_ignore`
    # when computing the path slacks (i.e. edge errors)
    lae_model_2 = fp.kLeastAbsErrors(graph, flow_attr="flow", num_paths=3, weight_type=float, edges_to_ignore=edges_to_ignore)
    lae_model_2.solve()
    process_solution(lae_model_2)

def process_solution(model: fp.kLeastAbsErrors):
    if model.is_solved:
        solution = model.get_solution()
        print(
            "Solution paths, weights, edge errors, solve statistics: ",
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