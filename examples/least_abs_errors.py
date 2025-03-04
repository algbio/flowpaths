import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=3)
    graph.add_edge("s", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=7)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "t", flow=7)
    graph.add_edge("d", "t", flow=3)

    # We create a Least Absolute Errors solver with default settings, 
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges,
    # and that the number of paths to consider is 3.
    lae_model = fp.kLeastAbsErrors(
        graph, 
        flow_attr="flow", 
        k=3, 
        weight_type=float,
        solver_options={"external_solver": "highs"}
        )

    # We solve it
    lae_model.solve()

    # We process its solution
    process_solution(lae_model)

    # We solve again, by also telling the model to ignore the edges in `edges_to_ignore`
    # when computing the edge errors
    lae_model_2 = fp.kLeastAbsErrors(
        graph, 
        flow_attr="flow", 
        k=3, 
        weight_type=float, 
        edges_to_ignore=[("a", "c")],
        solver_options={"external_solver": "gurobi"}
        )
    lae_model_2.solve()
    process_solution(lae_model_2)

    # We solve again, by also telling the model to trust the edges in 
    # trusted_edges_for_safety, so that safety optimizations can apply to them
    lae_model_3 = fp.kLeastAbsErrors(
        graph, 
        flow_attr="flow", 
        k=3, 
        weight_type=float, 
        edges_to_ignore=[("a", "c")],
        trusted_edges_for_safety=[("a", "b")],
        solver_options={"external_solver": "gurobi"}
        )
    lae_model_3.solve()
    process_solution(lae_model_3)

    # We solve again, by also passing subpath_constraints. Since by default we have coverage 1, their edges 
    # will be added by the class to trusted_edges_for_safety, so that safety optimizations can apply to them
    lae_model_4 = fp.kLeastAbsErrors(
        graph, 
        flow_attr="flow", 
        k=3, 
        weight_type=float, 
        subpath_constraints=[[("a", "b")]],
        edges_to_ignore=[("a", "c")],
        solver_options={"external_solver": "gurobi"}
        )
    lae_model_4.solve()
    process_solution(lae_model_4)

def process_solution(model: fp.kLeastAbsErrors):
    if model.is_solved():
        print(model.get_solution())
        print("model.is_valid_solution()", model.is_valid_solution())
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()