import networkx as nx
import pytest

import flowpaths as fp


def test_additional_edges_lambda_validation_kminpatherrorcycles():
    # Simple graph with source/sink for validation tests
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=2)
    g.add_edge("a", "b", flow=2)
    g.add_edge("b", "a", flow=1)  # back edge
    g.add_edge("b", "t", flow=1)

    with pytest.raises(ValueError, match="additional_edges_lambda must be non-negative"):
        fp.kMinPathErrorCycles(
            g,
            flow_attr="flow",
            k=1,
            additional_edges_lambda=-1,
            solver_options={"external_solver": "highs"},
        )

    with pytest.raises(ValueError, match="additional_edges_lambda must be numeric"):
        fp.kMinPathErrorCycles(
            g,
            flow_attr="flow",
            k=1,
            additional_edges_lambda="invalid",
            solver_options={"external_solver": "highs"},
        )


def test_additional_edges_penalty_in_objective_kminpatherrorcycles():
    """Penalty adds lambda * used_val to objective when an additional edge is used."""
    # s is source (no incoming), t is sink (no outgoing); a<->b cycle in middle
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=3)
    g.add_edge("a", "b", flow=3)
    g.add_edge("b", "a", flow=2)   # back edge
    g.add_edge("b", "t", flow=1)
    # additional edge a->t is not in the original graph

    base_model = fp.kMinPathErrorCycles(
        g,
        flow_attr="flow",
        k=2,
        additional_edges=[("a", "t")],
        additional_edges_lambda=0.0,
        solver_options={"external_solver": "highs"},
    )
    base_model.solve()
    assert base_model.is_solved()
    assert base_model.is_valid_solution()

    penalized_model = fp.kMinPathErrorCycles(
        g,
        flow_attr="flow",
        k=2,
        additional_edges=[("a", "t")],
        additional_edges_lambda=2.0,
        solver_options={"external_solver": "highs"},
    )
    penalized_model.solve()
    assert penalized_model.is_solved()
    assert penalized_model.is_valid_solution()

    base_obj = base_model.get_objective_value()
    penalized_obj = penalized_model.get_objective_value()

    # The penalty model should have objective >= base + 2.0 * used_val
    edge_used_sol = penalized_model.solver.get_values(penalized_model.additional_edges_used_vars)
    used_val = edge_used_sol[("a", "t")]
    assert penalized_obj >= base_obj + 2.0 * used_val - 1e-6


def test_additional_edge_used_binary_counted_once_kminpatherrorcycles():
    """Additional edge used by multiple walks counts only once in the penalty."""
    # s is source, t is sink; a<->b cycle in middle
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=3)
    g.add_edge("a", "b", flow=3)
    g.add_edge("b", "a", flow=2)  # back edge
    g.add_edge("b", "t", flow=1)
    # additional edge a->t not in the original graph

    model = fp.kMinPathErrorCycles(
        g,
        flow_attr="flow",
        k=2,
        additional_edges=[("a", "t")],
        additional_edges_lambda=5.0,
        subset_constraints=[[("a", "t")], [("a", "t")]],
        solver_options={"external_solver": "highs"},
    )
    model.solve()
    assert model.is_solved()
    assert model.is_valid_solution()

    edge_used_sol = model.solver.get_values(model.additional_edges_used_vars)
    # Binary var: at most 1
    assert edge_used_sol[("a", "t")] <= 1.0 + 1e-6

    obj = model.get_objective_value()
    slack_sum = sum(model.get_solution(remove_empty_walks=False)["slacks"])
    expected_obj = slack_sum + 5.0 * edge_used_sol[("a", "t")]
    assert abs(obj - expected_obj) < 1e-4


def test_k_none_uses_constrained_width_with_subset_constraints_cycles():
    g = nx.DiGraph()
    g.add_edge("s", "a", flow=1)
    g.add_edge("a", "t", flow=1)
    g.add_edge("s", "b", flow=1)
    g.add_edge("b", "t", flow=1)

    edges_to_ignore = [("s", "b"), ("b", "t")]
    subset_constraints = [[("s", "b"), ("b", "t")]]

    stg = fp.stDiGraph(g)
    unconstrained_width = stg.get_width(edges_to_ignore=edges_to_ignore)
    constrained_width = stg.get_width(
        edges_to_ignore=edges_to_ignore,
        subset_constraints=subset_constraints,
        solver_options={"external_solver": "highs"},
    )

    assert unconstrained_width == 1
    assert constrained_width == 2

    model = fp.kMinPathErrorCycles(
        g,
        flow_attr="flow",
        k=None,
        elements_to_ignore=edges_to_ignore,
        subset_constraints=subset_constraints,
        solver_options={"external_solver": "highs"},
    )

    assert model.k == 2
    model.solve()
    assert model.is_solved()
