import pytest
import flowpaths as fp
import networkx as nx


SOLVER_OPTIONS = {"external_solver": "gurobi"}


def test_k_min_discordant_nodes_exact_fit_with_subpath_constraints():
    graph = nx.DiGraph()
    graph.add_node("s", flow=10)
    graph.add_node("a", flow=6)
    graph.add_node("b", flow=4)
    graph.add_node("c", flow=10)
    graph.add_node("t", flow=10)

    graph.add_edge("s", "a")
    graph.add_edge("s", "b")
    graph.add_edge("a", "c")
    graph.add_edge("b", "c")
    graph.add_edge("c", "t")

    model = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=2,
        discordance_tolerance=0.0,
        weight_type=int,
        subpath_constraints=[[("a", "c")]],
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.get_objective_value() == 0

    solution = model.get_solution(remove_empty_paths=False)
    assert len(solution["paths"]) == 2
    assert sorted(solution["weights"]) == [4, 6]
    assert sum(solution["discordant_nodes"].values()) == 0
    assert any("a" in path and "c" in path for path in solution["paths"])


def test_k_min_discordant_nodes_counts_discordant_nodes():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=10)
    graph.add_node("t", flow=5)

    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=0.0,
        weight_type=int,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()

    solution = model.get_solution()
    assert solution["weights"] == [5]
    assert solution["discordant_nodes"]["a"] == 1
    assert model.get_objective_value() == 1


def test_k_min_discordant_nodes_supports_multi_vertex_constraints():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=5)
    graph.add_node("b", flow=2)
    graph.add_node("c", flow=2)
    graph.add_node("t", flow=5)

    graph.add_edge("s", "a")
    graph.add_edge("a", "t")
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", "t")

    model = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=2,
        discordance_tolerance=0.0,
        weight_type=int,
        subpath_constraints=[[("a", "b"), ("b", "c")]],
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.get_objective_value() == 0

    solution = model.get_solution(remove_empty_paths=True)
    assert any(
        ("a", "b") in list(zip(path[:-1], path[1:]))
        and ("b", "c") in list(zip(path[:-1], path[1:]))
        for path in solution["paths"]
    )


def test_k_min_discordant_nodes_remove_empty_paths_filters_singleton_paths():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=5)
    graph.add_node("t", flow=5)

    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=0.0,
        weight_type=int,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    solution = model.get_solution(remove_empty_paths=False)
    with_singleton = {
        "paths": solution["paths"] + [["s"]],
        "weights": solution["weights"] + [0],
    }
    filtered = model._remove_empty_paths(with_singleton)

    assert filtered["paths"] == solution["paths"]
    assert filtered["weights"] == solution["weights"]


def test_k_min_discordant_nodes_rejects_invalid_weight_type():
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "t")

    with pytest.raises(ValueError, match="weight_type must be either int or float"):
        fp.kMinDiscordantNodes(
            G=graph,
            flow_attr="flow",
            k=1,
            weight_type=str,
            solver_options=SOLVER_OPTIONS,
        )


def test_k_min_discordant_nodes_small_error_needs_positive_tolerance():
    graph = nx.DiGraph()
    graph.add_node("s", flow=10)
    graph.add_node("a", flow=10.4)
    graph.add_node("t", flow=10)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    strict_model = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=0.0,
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )
    strict_model.solve()
    strict_solution = strict_model.get_solution()

    assert strict_model.is_solved()
    assert strict_model.is_valid_solution()
    assert strict_solution["discordant_nodes"]["a"] == 1
    assert strict_model.get_objective_value() == 1

    tolerant_model = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=0.05,
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )
    tolerant_model.solve()
    tolerant_solution = tolerant_model.get_solution()

    assert tolerant_model.is_solved()
    assert tolerant_model.is_valid_solution()
    assert tolerant_solution["discordant_nodes"]["a"] == 0
    assert tolerant_model.get_objective_value() == 0


def test_k_min_discordant_nodes_tolerance_boundary_behavior():
    graph = nx.DiGraph()
    graph.add_node("s", flow=20)
    graph.add_node("a", flow=21)
    graph.add_node("t", flow=20)

    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model_zero_tol = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=1.0,
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )
    model_zero_tol.solve()

    assert model_zero_tol.is_solved()
    assert model_zero_tol.is_valid_solution()
    assert model_zero_tol.get_solution()["discordant_nodes"]["a"] == 0
    assert model_zero_tol.get_objective_value() == 0

    model_positive_tol = fp.kMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=0.05,
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )
    model_positive_tol.solve()

    assert model_positive_tol.is_solved()
    assert model_positive_tol.is_valid_solution()
    assert model_positive_tol.get_solution()["discordant_nodes"]["a"] == 0
    assert model_positive_tol.get_objective_value() == 0