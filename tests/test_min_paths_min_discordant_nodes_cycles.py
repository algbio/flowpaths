import flowpaths as fp
import networkx as nx


SOLVER_OPTIONS = {"external_solver": "highs"}


def test_min_paths_min_discordant_nodes_cycles_initialization_sets_expected_defaults():
    graph = nx.DiGraph()
    graph.add_node("s", flow=1)
    graph.add_node("a", flow=1)
    graph.add_node("t", flow=1)
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")
    graph.add_edge("t", "s")

    model = fp.MinPathsMinDiscordantNodesCycles(
        G=graph,
        flow_attr="flow",
        min_num_paths=2,
        max_num_paths=5,
    )

    assert model.model_type is fp.kMinDiscordantNodesCycles
    assert model.stop_on_delta_abs == 0
    assert model.stop_on_first_feasible is None
    assert model.stop_on_delta_rel is None
    assert model.min_num_paths == 2
    assert model.max_num_paths == 5
    assert model.kwargs["G"] is graph
    assert model.kwargs["flow_attr"] == "flow"


def test_min_paths_min_discordant_nodes_cycles_solve_stops_when_objective_plateaus():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=5)
    graph.add_node("b", flow=5)
    graph.add_node("t", flow=5)

    graph.add_edge("s", "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")
    graph.add_edge("b", "t")

    model = fp.MinPathsMinDiscordantNodesCycles(
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
    # On this graph, k=1 is not selected; once objective plateaus, the previous
    # feasible model is retained.
    assert model.model.k == 2
    solution = model.get_solution()
    assert "walks" in solution
    assert "weights" in solution
    assert "discordant_nodes" in solution
