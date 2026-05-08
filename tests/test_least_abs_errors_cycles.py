import pytest
import itertools
import flowpaths as fp
import networkx as nx
from pathlib import Path

weight_type = [float]
solvers = ["highs"]
settings_flags = {
    "optimize_with_safety_as_subset_constraints": [True, False],
}

params = list(itertools.product(
    weight_type,
    solvers,
    *settings_flags.values()
    ))

def run_test(graph: nx.DiGraph, test_index, params):
    print("*******************************************")
    print(f"Testing graph {test_index}: {fp.utils.fpid(graph)}") 
    print("*******************************************")

    first_objective_value = None

    for settings in params:
        print("Testing settings:", settings)
        optimization_options = {key: setting for key, setting in zip(settings_flags.keys(), settings[2:])}

        print("-------------------------------------------")
        print("Solving with optimization options:", {key for key in optimization_options if optimization_options[key]})

        lae_model = fp.kLeastAbsErrorsCycles(
            G=graph,
            flow_attr="flow",
            k=5,
            weight_type=settings[0],
            optimization_options=optimization_options,
            solver_options={"external_solver": settings[1]},
            trusted_edges_for_safety=graph.edges
        )
        lae_model.solve()
        print(lae_model.solve_statistics)

        # Checks
        assert lae_model.is_solved(), "Model should be solved"
        assert lae_model.is_valid_solution(), "The solution is not a valid flow decomposition, under the default tolerance."

        current_objective_value = lae_model.get_objective_value()
        if first_objective_value is None:
            first_objective_value = current_objective_value
        else:
            assert first_objective_value == current_objective_value, "The objective value should be the same for all settings."


graphs_dir = Path(__file__).parent / "cyclic_graphs"
graphs = []
for graph_file in sorted(graphs_dir.glob("*.graph")):
    print(graph_file)
    graphs.extend(fp.graphutils.read_graphs(str(graph_file)))

@pytest.mark.parametrize("graph, idx", [(g, i) for i, g in enumerate(graphs)])
def test(graph, idx):
    run_test(graph, idx, params)


def test_additional_edges_lambda_validation_cycles():
    G = nx.DiGraph()
    G.add_edge("s", "a", flow=2)
    G.add_edge("a", "t", flow=2)

    with pytest.raises(ValueError, match="additional_edges_lambda must be non-negative"):
        fp.kLeastAbsErrorsCycles(
            G=G,
            flow_attr="flow",
            k=1,
            additional_edges_lambda=-1,
        )

    with pytest.raises(ValueError, match=r"endpoint\(s\) not in the input graph"):
        fp.kLeastAbsErrorsCycles(
            G=G,
            flow_attr="flow",
            k=1,
            additional_edges=[("s", "x")],
        )


def test_additional_edges_objective_cycles():
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    
    G = nx.DiGraph()
    G.add_edge("s", "a", flow=40)
    G.add_edge("a", "b", flow=4)
    G.add_edge("b", "a", flow=3)
    G.add_edge("b", "t", flow=4)

    model = fp.kLeastAbsErrorsCycles(
        G=G,
        flow_attr="flow",
        k=1,
        additional_edges=[("a", "t")],
        additional_edges_lambda=1.0,
        # solver_options={"external_solver": "highs"},
    )
    model.solve()
    assert model.get_solution()["walks"] == [['s', 'a', 't']], "Expected walk not found"
    assert model.get_solution()["weights"] == [40.0], "Expected weight not found"
    assert model.get_objective_value() == 12, "Objective value should be 12 with the additional edge a->t used to resolve the cycle and the error on edge a->b."

    assert model.is_solved()
    assert model.is_valid_solution()
    assert abs(model.get_objective_value() - model.solver.get_objective_value()) < 1e-6


def test_k_none_uses_constrained_width_with_subset_constraints_lae_cycles():
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=1)
    g.add_edge("a", "t", flow=1)
    g.add_edge("s", "b", flow=1)
    g.add_edge("b", "t", flow=1)

    edges_to_ignore = [("s", "b"), ("b", "t")]
    subset_constraints = [[("s", "b"), ("b", "t")]]

    model = fp.kLeastAbsErrorsCycles(
        G=g,
        flow_attr="flow",
        k=None,
        elements_to_ignore=edges_to_ignore,
        subset_constraints=subset_constraints,
        solver_options={"external_solver": "highs"},
    )

    assert model.k == 2
    model.solve()
    assert model.is_solved()
