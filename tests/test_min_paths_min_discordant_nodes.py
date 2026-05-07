import flowpaths as fp
import networkx as nx
import pytest


SOLVER_OPTIONS = {"external_solver": "highs"}


def test_min_paths_min_discordant_nodes_initialization_sets_expected_defaults():
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        max_num_paths=5,
    )

    assert model.model_type is fp.kMinDiscordantNodes
    assert model.stop_on_delta_abs == 0
    assert model.stop_on_first_feasible is None
    assert model.stop_on_delta_rel is None
    assert model.min_num_paths >= 1  # Computed from MinPathCover
    assert model.max_num_paths == 5
    assert set(model.kwargs["G"].nodes()) == set(graph.nodes())
    assert set(model.kwargs["G"].edges()) == set(graph.edges())
    assert model.kwargs["flow_attr"] == "flow"


def test_min_paths_min_discordant_nodes_solve_stops_with_zero_discordance():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=5)
    graph.add_node("t", flow=5)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        max_num_paths=4,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.get_objective_value() == 0
    # With stop_on_delta_abs == 0, we stop when objective repeats and keep the previous k.
    assert model.model.k == 1
    solution = model.get_solution()
    assert "paths" in solution
    assert "weights" in solution


def test_min_paths_min_discordant_nodes_solve_stops_when_objective_plateaus():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=10)
    graph.add_node("t", flow=5)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        max_num_paths=4,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    # Here objective is stable between k=1 and k=2, and we keep the previous k.
    assert model.get_objective_value() == 1
    assert model.model.k >= 1
    solution = model.get_solution()
    assert "discordant_nodes" in solution


def test_num_paths_optimization_delta_rel_keeps_previous_k():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=10)
    graph.add_node("t", flow=5)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model = fp.NumPathsOptimization(
        model_type=fp.kMinDiscordantNodes,
        stop_on_delta_rel=0.01,
        min_num_paths=1,
        max_num_paths=4,
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.model.k == 1


def test_min_paths_min_discordant_nodes_branching_graph_requires_two_paths():
    graph = nx.DiGraph()
    graph.add_node("s", flow=10)
    graph.add_node("a", flow=5)
    graph.add_node("b", flow=5)
    graph.add_node("t", flow=10)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")
    graph.add_edge("s", "b")
    graph.add_edge("b", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        max_num_paths=5,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.get_objective_value() == 0
    # k=1 is infeasible because all branch edges must be covered; with repeated objective 0, keep previous k.
    assert model.model.k == 2
    solution = model.get_solution()
    assert len(solution["paths"]) >= 2


def test_num_paths_optimization_delta_rel_branching_graph_keeps_previous_k():
    graph = nx.DiGraph()
    graph.add_node("s", flow=10)
    graph.add_node("a", flow=6)
    graph.add_node("b", flow=5)
    graph.add_node("t", flow=10)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")
    graph.add_edge("s", "b")
    graph.add_edge("b", "t")

    model = fp.NumPathsOptimization(
        model_type=fp.kMinDiscordantNodes,
        stop_on_delta_rel=0.01,
        min_num_paths=1,
        max_num_paths=5,
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    # k=1 infeasible due branching edge coverage, k=2 feasible, and first small relative delta is between k=2 and k=3.
    assert model.model.k == 2
    assert model.get_objective_value() == 1


def test_num_paths_optimization_get_solution_accepts_remove_empty_paths_flag():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=10)
    graph.add_node("t", flow=5)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    model = fp.NumPathsOptimization(
        model_type=fp.kMinDiscordantNodes,
        stop_on_delta_rel=0.01,
        min_num_paths=1,
        max_num_paths=4,
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    solution = model.get_solution(remove_empty_paths=True)
    assert "paths" in solution
    assert "weights" in solution


def test_num_paths_optimization_remove_empty_paths_filters_aligned_lists():
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "t")

    model = fp.NumPathsOptimization(
        model_type=fp.kMinDiscordantNodes,
        stop_on_delta_abs=0,
        min_num_paths=1,
        max_num_paths=2,
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        solver_options=SOLVER_OPTIONS,
    )

    model._solution = {
        "paths": [["s"], ["s", "t"]],
        "weights": [3, 7],
        "slacks": [1, 2],
        "discordant_nodes": ["x", "y"],
    }
    model.set_solved()

    filtered = model.get_solution(remove_empty_paths=True)
    unfiltered = model.get_solution(remove_empty_paths=False)

    assert filtered["paths"] == [["s", "t"]]
    assert filtered["weights"] == [7]
    assert filtered["slacks"] == [2]
    assert filtered["discordant_nodes"] == ["y"]
    assert unfiltered["paths"] == [["s"], ["s", "t"]]


def test_min_paths_min_discordant_nodes_single_node_dag():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        max_num_paths=3,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.model.k == 1
    assert model.get_objective_value() == 0

    solution = model.get_solution(remove_empty_paths=False)
    assert solution["paths"] == [["s"]]
    assert solution["weights"] == [5]
    assert solution["discordant_nodes"] == {"s": 0}
    assert model.solve_statistics["solve_mode"] == "trivial_single_node"


def test_min_paths_min_discordant_nodes_two_weakly_connected_components_mixed_sizes():
    graph = nx.DiGraph()
    # Component 1: isolated single node.
    graph.add_node("iso", flow=3)
    # Component 2: simple connected DAG with one edge.
    graph.add_node("s", flow=5)
    graph.add_node("t", flow=5)
    graph.add_edge("s", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        max_num_paths=3,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model._is_componentized
    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.get_objective_value() == 0

    solution = model.get_solution(remove_empty_paths=False)
    solution_paths_as_sets = {tuple(path) for path in solution["paths"]}

    assert ("iso",) in solution_paths_as_sets
    assert ("s", "t") in solution_paths_as_sets
    assert solution["discordant_nodes"] == {"iso": 0, "s": 0, "t": 0}


def test_min_paths_min_discordant_nodes_initialization_attaches_path_cover_seed():
    graph = nx.DiGraph()
    graph.add_node("s", flow=10)
    graph.add_node("a", flow=5)
    graph.add_node("b", flow=5)
    graph.add_node("t", flow=10)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")
    graph.add_edge("s", "b")
    graph.add_edge("b", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        max_num_paths=5,
        solver_options=SOLVER_OPTIONS,
    )

    seed_paths = model.kwargs["optimization_options"].get("path_cover_mip_start_paths")
    assert seed_paths is not None
    assert len(seed_paths) == 2
    assert {tuple(path) for path in seed_paths} == {("s", "a", "t"), ("s", "b", "t")}


def test_min_paths_min_discordant_nodes_zero_flow_isolated_component_is_trivially_solved():
    graph = nx.DiGraph()
    # Component 1: isolated node with zero flow (trivial feasible component).
    graph.add_node("zero", flow=0.0)
    # Component 2: simple connected DAG.
    graph.add_node("s", flow=5.0)
    graph.add_node("t", flow=5.0)
    graph.add_edge("s", "t", flow=5.0)

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=float,
        max_num_paths=3,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model._is_componentized
    assert model.is_solved()
    assert model.is_valid_solution()
    assert model.get_objective_value() == 0

    solution = model.get_solution(remove_empty_paths=False)
    solution_paths_as_sets = {tuple(path) for path in solution["paths"]}

    assert ("zero",) in solution_paths_as_sets
    assert ("s", "t") in solution_paths_as_sets
    assert solution["discordant_nodes"] == {"zero": 0, "s": 0, "t": 0}


def test_min_paths_min_discordant_nodes_multitrans_72_ngraph_must_solve():
    graphs = fp.graphutils.read_ngraphs("./tests/acyclic_graphs/multitrans.72.ngraph")
    assert len(graphs) == 1
    graph = graphs[0]

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=float,
        subsequence_constraints=graph.graph.get("constraints", []),
        max_num_paths=max(1, graph.number_of_nodes()),
        solver_options=SOLVER_OPTIONS,
    )

    try:
        solved = model.solve()
    except ValueError as exc:
        pytest.fail(
            "MinPathsMinDiscordantNodes failed before solving multitrans.72.ngraph. "
            "Potential weak-component/constraint issue. "
            f"error={exc}; weak_components={nx.number_weakly_connected_components(graph)}; "
            f"constraints={len(graph.graph.get('constraints', []))}"
        )

    solve_status = None
    if isinstance(model.solve_statistics, dict):
        solve_status = model.solve_statistics.get("solve_status")

    assert solved, (
        "MinPathsMinDiscordantNodes did not solve multitrans.72.ngraph. "
        "Investigate feasibility/constraint handling and weak-component splitting. "
        f"solve_status={solve_status}; weak_components={nx.number_weakly_connected_components(graph)}; "
        f"constraints={len(graph.graph.get('constraints', []))}"
    )
    assert model.is_solved()
    assert model.is_valid_solution()
    solution = model.get_solution(remove_empty_paths=False)
    assert "paths" in solution
    assert "weights" in solution


def test_min_paths_min_discordant_nodes_infeasible_when_constraint_pair_is_unreachable(caplog):
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("a", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    with caplog.at_level("CRITICAL"):
        model = fp.MinPathsMinDiscordantNodes(
            G=graph,
            flow_attr="flow",
            weight_type=int,
            subsequence_constraints=[["a", "s"]],
            max_num_paths=3,
            solver_options=SOLVER_OPTIONS,
        )
        solved = model.solve()

    assert solved is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.infeasible_status_name
    assert any("no path from 'a' to 's'" in record.message for record in caplog.records)
    assert any("Aborting solve because subsequence constraints are infeasible" in record.message for record in caplog.records)
    assert not hasattr(model, "model")


def test_min_paths_min_discordant_nodes_infeasible_when_constraint_node_missing(caplog):
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "t")

    with caplog.at_level("CRITICAL"):
        model = fp.MinPathsMinDiscordantNodes(
            G=graph,
            flow_attr="flow",
            weight_type=int,
            subsequence_constraints=[["s", "x"]],
            max_num_paths=3,
            solver_options=SOLVER_OPTIONS,
        )
        solved = model.solve()

    assert solved is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.infeasible_status_name
    assert any("node 'x'" in record.message and "is not in graph" in record.message for record in caplog.records)
    assert any("Aborting solve because subsequence constraints are infeasible" in record.message for record in caplog.records)
    assert not hasattr(model, "model")


def test_min_paths_min_discordant_nodes_scales_and_restores_weights_with_rounding():
    graph = nx.DiGraph()
    graph.add_node("s", flow=6)
    graph.add_node("t", flow=6)
    graph.add_edge("s", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        discordance_tolerance=0.0,
        flow_values_divisor=2,
        round_flow_values_to_int=True,
        max_num_paths=3,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    solution = model.get_solution(remove_empty_paths=False)
    assert solution["weights"] == [6.0]
    assert solution["discordant_nodes"] == {"s": 0, "t": 0}
    assert model.get_objective_value() == 0


def test_min_paths_min_discordant_nodes_scales_without_rounding_and_keeps_validity():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5.0)
    graph.add_node("t", flow=5.0)
    graph.add_edge("s", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=float,
        discordance_tolerance=0.0,
        flow_values_divisor=2,
        round_flow_values_to_int=False,
        max_num_paths=3,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    solution = model.get_solution(remove_empty_paths=False)
    assert solution["weights"] == [5.0]
    assert solution["discordant_nodes"] == {"s": 0, "t": 0}
