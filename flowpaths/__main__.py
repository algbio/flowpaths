import flowpaths.minflowdecomp as mfd
import flowpaths.kminpatherror as kmpe
import networkx as nx

# Run as `python -m flowpaths` in the `flowpaths` root directory


def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge(0, "a", flow=6)
    graph.add_edge(0, "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", 1, flow=7)
    graph.add_edge("d", 1, flow=6)

    # We create a Minimum Flow Decomposition solver with default settings,
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges.
    mfd_model = mfd.MinFlowDecomp(graph, flow_attr="flow")

    # We solve it
    mfd_model.solve()

    # We process its solution
    process_solution(mfd_model)

    # We now set the weights of the solution paths to int
    mfd_model_int = mfd.MinFlowDecomp(graph, flow_attr="flow", weight_type=int)
    mfd_model_int.solve()
    process_solution(mfd_model_int)

    # We solve again, but using the `gurobi` solver, instead of the default `highs`.
    # This requires the `gurobipy` package and a Gurobi license.
    # For this, we deactivate the greedy optimization, to make sure the gurobi solver is used.
    mfd_model_int_gurobi = mfd.MinFlowDecomp(
        graph,
        flow_attr="flow",
        weight_type=int,
        optimize_with_greedy=False,
        external_solver="gurobi",
    )
    mfd_model_int_gurobi.solve()
    process_solution(mfd_model_int_gurobi)

    # We solve again, by deactivating all optimizations
    mfd_model_slow = mfd.MinFlowDecomp(
        graph,
        flow_attr="flow",
        weight_type=int,
        optimize_with_safe_paths=False,
        optimize_with_safe_sequences=False,
        optimize_with_safe_zero_edges=False,
        optimize_with_greedy=False,
    )
    mfd_model_slow.solve()
    process_solution(mfd_model_slow)

    # We now create a kMinPathError model
    # We perturbe the graph
    graph.remove_edge("a", "c")
    graph.add_edge("a", "c", flow=5)

    kminpatherror_model = kmpe.kMinPathError(
        graph,
        flow_attr="flow",
        weight_type=float,
        num_paths=3,
        optimize_with_safe_paths=True,
        optimize_with_safe_sequences=False,
        optimize_with_safe_zero_edges=False,
        optimize_with_greedy=False,
    )
    kminpatherror_model.solve()
    process_solution_kmpe(kminpatherror_model)

    # We now ignore the edge ('a', 'c') in the optimization, but allow the paths to go through it
    kminpatherror_model = kmpe.kMinPathError(
        graph,
        flow_attr="flow",
        weight_type=int,
        num_paths=3,
        edges_to_ignore=[("a", "c")],
        optimize_with_safe_paths=False,
        optimize_with_safe_sequences=True,
        optimize_with_safe_zero_edges=True,
        optimize_with_greedy=False,
    )
    kminpatherror_model.solve()
    process_solution_kmpe(kminpatherror_model)


def process_solution(model: mfd.MinFlowDecomp):
    if model.is_solved:
        solution = model.get_solution()
        print(
            "Solution weights, paths, solve statistics: ",
            solution[1],
            solution[0],
            model.solve_statistics,
        )
    else:
        print("Model could not be solved.")


def process_solution_kmpe(model: kmpe.kMinPathError):
    if model.is_solved:
        solution = model.get_solution()
        print(
            "Solution weights, slacks, paths, weights, solve statistics: ",
            solution[1],
            solution[2],
            solution[0],
            model.solve_statistics,
        )
    else:
        print("Model could not be solved.")


if __name__ == "__main__":
    main()
