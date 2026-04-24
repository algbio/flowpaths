import flowpaths as fp
import networkx as nx


SOLVER_OPTIONS = {"external_solver": "highs"}


def test_min_paths_min_discordant_nodes_initialization_sets_expected_defaults():
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "t")

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        min_num_paths=2,
        max_num_paths=5,
    )

    assert model.model_type is fp.kMinDiscordantNodes
    assert model.stop_on_delta_abs == 0
    assert model.stop_on_first_feasible is None
    assert model.stop_on_delta_rel is None
    assert model.min_num_paths == 2
    assert model.max_num_paths == 5
    assert model.kwargs["G"] is graph
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
        min_num_paths=1,
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
        min_num_paths=1,
        max_num_paths=4,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()
    # Here objective is stable between k=1 and k=2, and we keep the previous k.
    assert model.get_objective_value() == 1
    assert model.model.k == 1
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
        min_num_paths=1,
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
