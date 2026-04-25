import flowpaths as fp
import networkx as nx


SOLVER_OPTIONS = {"external_solver": "highs"}


def test_k_min_discordant_nodes_cycles_solves_and_returns_discordant_nodes():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=5)
    graph.add_node("b", flow=5)
    graph.add_node("t", flow=5)

    graph.add_edge("s", "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")
    graph.add_edge("b", "t")

    model = fp.kMinDiscordantNodesCycles(
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
    assert "walks" in solution
    assert "weights" in solution
    assert "discordant_nodes" in solution
    assert set(solution["discordant_nodes"].keys()) == {"s", "a", "b", "t"}
    assert model.get_objective_value() == sum(solution["discordant_nodes"].values())


def test_k_min_discordant_nodes_cycles_respects_subset_constraints_nodes_parameter():
    graph = nx.DiGraph()
    graph.add_node("s", flow=5)
    graph.add_node("a", flow=5)
    graph.add_node("b", flow=5)
    graph.add_node("t", flow=5)

    graph.add_edge("s", "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")
    graph.add_edge("b", "t")

    model = fp.kMinDiscordantNodesCycles(
        G=graph,
        flow_attr="flow",
        k=1,
        discordance_tolerance=0.0,
        weight_type=int,
        subset_constraints=[["a", "b"]],
        solver_options=SOLVER_OPTIONS,
    )

    # Node-based constraints are converted to expanded node-edges.
    assert ("a.0", "a.1") in model.subset_constraints[0]
    assert ("b.0", "b.1") in model.subset_constraints[0]

    model.solve()

    assert model.is_solved()
    assert model.is_valid_solution()

    solution = model.get_solution(remove_empty_walks=True)
    assert len(solution["walks"]) >= 1
