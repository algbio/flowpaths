import flowpaths as fp
import networkx as nx


SOLVER_OPTIONS = {"external_solver": "highs"}


def test_num_paths_optimization_supports_cyclic_walk_models():
    graph = nx.DiGraph()
    graph.add_edge("s", "a", flow=5)
    graph.add_edge("a", "b", flow=5)
    graph.add_edge("b", "a", flow=1)
    graph.add_edge("b", "t", flow=4)

    model = fp.NumPathsOptimization(
        model_type=fp.kLeastAbsErrorsCycles,
        stop_on_first_feasible=True,
        min_num_paths=1,
        max_num_paths=2,
        G=graph,
        flow_attr="flow",
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    solution = model.get_solution(remove_empty_paths=True)
    assert "walks" in solution
    assert "weights" in solution


def test_num_paths_optimization_remove_empty_paths_filters_walk_solutions():
    graph = nx.DiGraph()
    graph.add_edge("s", "t", flow=1)

    model = fp.NumPathsOptimization(
        model_type=fp.kLeastAbsErrorsCycles,
        stop_on_first_feasible=True,
        min_num_paths=1,
        max_num_paths=1,
        G=graph,
        flow_attr="flow",
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )

    model._solution = {
        "walks": [["s"], ["s", "t"]],
        "weights": [3.0, 7.0],
        "edge_errors": [1.0, 2.0],
    }
    model.set_solved()

    filtered = model.get_solution(remove_empty_paths=True)
    unfiltered = model.get_solution(remove_empty_paths=False)

    assert filtered["walks"] == [["s", "t"]]
    assert filtered["weights"] == [7.0]
    assert filtered["edge_errors"] == [2.0]
    assert unfiltered["walks"] == [["s"], ["s", "t"]]
