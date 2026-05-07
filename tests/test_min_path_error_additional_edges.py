import networkx as nx
import pytest

import flowpaths as fp


def test_additional_edges_lambda_validation_kminpatherror():
    g = nx.DiGraph()
    g.add_edge("s", "t", flow=1)

    with pytest.raises(ValueError, match="additional_edges_lambda must be non-negative"):
        fp.kMinPathError(
            g,
            flow_attr="flow",
            k=1,
            additional_edges_lambda=-1,
            solver_options={"external_solver": "highs"},
        )

    with pytest.raises(ValueError, match="additional_edges_lambda must be numeric"):
        fp.kMinPathError(
            g,
            flow_attr="flow",
            k=1,
            additional_edges_lambda="invalid",
            solver_options={"external_solver": "highs"},
        )


def test_additional_edges_penalty_in_objective_kminpatherror():
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=1)
    g.add_edge("a", "t", flow=1)

    base_model = fp.kMinPathError(
        g,
        flow_attr="flow",
        k=2,
        additional_edges=[("s", "t")],
        additional_edges_lambda=0.0,
        subpath_constraints=[[('s', 't')]],
        solver_options={"external_solver": "highs"},
    )
    base_model.solve()
    assert base_model.is_solved()
    assert base_model.is_valid_solution()

    penalized_model = fp.kMinPathError(
        g,
        flow_attr="flow",
        k=2,
        additional_edges=[("s", "t")],
        additional_edges_lambda=2.0,
        subpath_constraints=[[('s', 't')]],
        solver_options={"external_solver": "highs"},
    )
    penalized_model.solve()
    assert penalized_model.is_solved()
    assert penalized_model.is_valid_solution()

    base_obj = base_model.get_objective_value()
    penalized_obj = penalized_model.get_objective_value()

    assert abs(base_obj - 0.0) < 1e-6
    assert abs(penalized_obj - (base_obj + 2.0)) < 1e-6


def test_additional_edge_used_binary_counted_once_kminpatherror():
    """Test that an additional edge contributes at most 1 to the objective penalty,
    even when it is used by multiple paths."""
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=2)
    g.add_edge("a", "t", flow=2)

    # Two paths are needed; both can traverse the additional edge s->t.
    # With subpath_constraints we force both paths through s->t.
    model = fp.kMinPathError(
        g,
        flow_attr="flow",
        k=2,
        additional_edges=[("s", "t")],
        additional_edges_lambda=5.0,
        subpath_constraints=[[("s", "t")], [("s", "t")]],
        solver_options={"external_solver": "highs"},
    )
    model.solve()
    assert model.is_solved()
    assert model.is_valid_solution()

    obj = model.get_objective_value()
    # If the additional edge s->t is used (by one or both paths) it counts exactly once.
    # Penalty is at most 5.0 * 1 = 5.0, regardless of how many paths use it.
    edge_used_sol = model.solver.get_values(model.additional_edges_used_vars)
    assert edge_used_sol[("s", "t")] <= 1.0 + 1e-6

    # Confirm that the reported objective equals slacks + lambda * used
    slack_sum = sum(model.get_solution(remove_empty_paths=False)["slacks"])
    expected_obj = slack_sum + 5.0 * edge_used_sol[("s", "t")]
    assert abs(obj - expected_obj) < 1e-4
