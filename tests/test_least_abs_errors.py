import pytest
import itertools
import flowpaths as fp

weight_type = [int]
solvers = ["highs"]

tolerance = 1

settings_flags = {
    "optimize_with_safe_paths": [False],
    "optimize_with_safe_sequences": [False],
    "optimize_with_safety_as_subpath_constraints": [False],
}

params = list(itertools.product(
    weight_type,
    solvers,
    *settings_flags.values()
    ))

def is_valid_optimization_setting_lae(opt):
        safety_opt = (
            opt["optimize_with_safe_paths"]
            + opt["optimize_with_safe_sequences"]
        )
        if safety_opt > 1:
            return False
        return True

def run_test(graph, test_index, params):
    print("*******************************************")
    print(f"Testing graph {test_index}: {fp.utils.fpid(graph)}") 
    print("*******************************************")

    first_obj_value = None
    first_path_weights = None
    first_weight_type = None
    first_paths = None

    for settings in params:
        print("Testing settings:", settings)
        optimization_options = {key: setting for key, setting in zip(settings_flags.keys(), settings[2:])}
        if not is_valid_optimization_setting_lae(optimization_options):
            continue

        print("-------------------------------------------")
        print("Solving with optimization options:", {key for key in optimization_options if optimization_options[key]})

        width = fp.stDAG(graph).get_width()
        print("Width:", width)

        lae_model = fp.kLeastAbsErrors(
            G=graph,
            k=width,
            flow_attr="flow",
            weight_type=settings[0],
            optimization_options=optimization_options,
            solver_options={"external_solver": settings[1]},
        )
        lae_model.solve() 
        print(lae_model.solve_statistics)

        # Checks
        assert lae_model.is_solved(), "Model should be solved"
        assert lae_model.is_valid_solution(), f"The solution is not a valid solution, under the default tolerance. Solution: {lae_model.get_solution()}"
        

        obj_value = lae_model.get_objective_value()
        if first_obj_value is None:
            first_weight_type = settings[0]
            first_obj_value = lae_model.get_objective_value()
            first_path_weights = lae_model.get_solution()["weights"]
            first_paths = lae_model.get_solution()["paths"]
            print("First path weights:", first_path_weights)
        else:
            assert abs(first_obj_value - obj_value) < tolerance, f"The objective value should be the same for all settings. settings: {settings}"

    # Testing the solution_weights_superset optimization
    solution_weights_superset = first_path_weights + [first_weight_type(weight * (2 if idx % 2 else 0.5)) for idx, weight in enumerate(first_path_weights)]
    print("Solution weights superset:", solution_weights_superset)

    lae_model = fp.kLeastAbsErrors(
            G=graph,
            k=width,
            flow_attr="flow",
            weight_type=first_weight_type,
            solution_weights_superset=solution_weights_superset,
            solver_options={"external_solver": "highs"},
        )
    lae_model.solve() 
    print(lae_model.solve_statistics)
    assert lae_model.is_solved(), "Model should be solved"
    assert lae_model.is_valid_solution(), "The solution is not a valid solution, under the default tolerance."
    obj_value = lae_model.get_objective_value()
    assert abs(first_obj_value - obj_value) < tolerance, "The objective value should be the same for all settings."

    # Generate some subpath constraints from first_paths and test the model
    subpath_constraints = []
    for path in first_paths:
        # Choose a random interval in path to create a subpath constraint
        if len(path) > 2:
            start = int(len(path) * 0.2)
            end = int(len(path) * 0.8)
            if start == end - 1:
                continue
            subpath_constraints.append(list(zip(path[start:end-1], path[start + 1:end])))
    print("Subpath constraints:", subpath_constraints)

    lae_model = fp.kLeastAbsErrors(
            G=graph,
            k=width,
            flow_attr="flow",
            weight_type=first_weight_type,
            solution_weights_superset=solution_weights_superset,
            subpath_constraints=subpath_constraints,
            solver_options={"external_solver": "highs"},
        )
    lae_model.solve() 
    print(lae_model.solve_statistics)
    assert lae_model.is_solved(), "Model should be solved"
    assert lae_model.is_valid_solution(), "The solution is not a valid solution, under the default tolerance."
    obj_value = lae_model.get_objective_value()
    print("Objective value with subpath constraints:", obj_value)
    print("Objective value without subpath constraints and without solution_weights_superset:", first_obj_value)
    assert abs(first_obj_value - obj_value) < tolerance, "The objective value should be the same for all settings."

graphs = fp.graphutils.read_graphs("./tests/test_graphs_errors.graph")
@pytest.mark.parametrize("graph, idx", [(g, i) for i, g in enumerate(graphs)])
def test(graph, idx):
    run_test(graph, idx, params)


# Tests for additional_edges_lambda parameter
def test_additional_edges_lambda_parameter_validation():
    """Test that additional_edges_lambda parameter is properly validated."""
    import networkx as nx
    
    # Create a simple test graph
    G = nx.DiGraph()
    G.add_edge('s', 'a', flow=2)
    G.add_edge('a', 't', flow=2)
    
    # Test negative lambda (should raise ValueError)
    with pytest.raises(ValueError, match="additional_edges_lambda must be non-negative"):
        fp.kLeastAbsErrors(
            G=G,
            k=1,
            flow_attr="flow",
            additional_edges_lambda=-0.5,
        )
    
    # Test non-numeric lambda (should raise ValueError)
    with pytest.raises(ValueError, match="additional_edges_lambda must be numeric"):
        fp.kLeastAbsErrors(
            G=G,
            k=1,
            flow_attr="flow",
            additional_edges_lambda="invalid",
        )
    
    # Test that valid lambda values are accepted
    for valid_lambda in [0.0, 0.5, 1.0, 2.0, 100.0]:
        model = fp.kLeastAbsErrors(
            G=G,
            k=1,
            flow_attr="flow",
            additional_edges_lambda=valid_lambda,
        )
        assert model.additional_edges_lambda == float(valid_lambda)


def test_additional_edges_lambda_objective_value():
    """Test that additional_edges_lambda correctly affects the objective value."""
    import networkx as nx
    
    # Create a simple test graph with multiple paths
    G = nx.DiGraph()
    G.add_edge('s', 'a', flow=4)
    G.add_edge('a', 'b', flow=4)
    G.add_edge('b', 't', flow=4)
    G.add_edge('a', 't', flow=0)  # Alternative edge
    
    # Define additional edges
    additional_edges = [('s', 't')]
    
    # Solve without additional edges
    model_no_additional = fp.kLeastAbsErrors(
        G=G,
        k=2,
        flow_attr="flow",
        additional_edges=[],
        additional_edges_lambda=1.0,
        solver_options={"external_solver": "highs"},
    )
    model_no_additional.solve()
    obj_no_additional = model_no_additional.get_objective_value()
    
    # Solve with additional edges and lambda=0 (should be same or very close to no additional edges)
    model_lambda_0 = fp.kLeastAbsErrors(
        G=G,
        k=2,
        flow_attr="flow",
        additional_edges=additional_edges,
        additional_edges_lambda=0.0,
        solver_options={"external_solver": "highs"},
    )
    model_lambda_0.solve()
    obj_lambda_0 = model_lambda_0.get_objective_value()
    
    # Solve with additional edges and lambda=1.0
    model_lambda_1 = fp.kLeastAbsErrors(
        G=G,
        k=2,
        flow_attr="flow",
        additional_edges=additional_edges,
        additional_edges_lambda=1.0,
        solver_options={"external_solver": "highs"},
    )
    model_lambda_1.solve()
    obj_lambda_1 = model_lambda_1.get_objective_value()
    
    # Solve with additional edges and lambda=10.0
    model_lambda_10 = fp.kLeastAbsErrors(
        G=G,
        k=2,
        flow_attr="flow",
        additional_edges=additional_edges,
        additional_edges_lambda=10.0,
        solver_options={"external_solver": "highs"},
    )
    model_lambda_10.solve()
    obj_lambda_10 = model_lambda_10.get_objective_value()
    
    # Verify that increasing lambda increases the objective when additional edges are used
    # (or keeps it the same if additional edges are not used)
    assert obj_lambda_0 <= obj_lambda_1 <= obj_lambda_10 or \
           (obj_lambda_0 == obj_lambda_1 == obj_lambda_10)  # All equal if no additional edges used


def test_k_none_uses_constrained_width_with_subpath_constraints_lae():
    import networkx as nx

    g = nx.DiGraph()
    g.add_edge("s", "a", flow=1)
    g.add_edge("a", "t", flow=1)
    g.add_edge("s", "b", flow=1)
    g.add_edge("b", "t", flow=1)

    edges_to_ignore = [("s", "b"), ("b", "t")]
    subpath_constraints = [[("s", "b"), ("b", "t")]]

    model = fp.kLeastAbsErrors(
        G=g,
        flow_attr="flow",
        k=None,
        elements_to_ignore=edges_to_ignore,
        subpath_constraints=subpath_constraints,
        solver_options={"external_solver": "highs"},
    )

    assert model.k == 2
    model.solve()
    assert model.is_solved()


def test_additional_edges_counted_once():
    """Test that each additional edge is counted at most once in the objective, regardless of how many paths use it."""
    import networkx as nx
    
    # Create a diamond-shaped graph where multiple paths can use the same additional edge
    G = nx.DiGraph()
    G.add_edge('s', 'a', flow=2)
    G.add_edge('s', 'b', flow=2)
    G.add_edge('a', 't', flow=2)
    G.add_edge('b', 't', flow=2)
    
    # Additional edge that could be used by multiple paths
    additional_edges = [('a', 'b')]
    
    model = fp.kLeastAbsErrors(
        G=G,
        k=2,
        flow_attr="flow",
        additional_edges=additional_edges,
        additional_edges_lambda=5.0,
        solver_options={"external_solver": "highs"},
    )
    model.solve()
    
    assert model.is_solved(), "Model should be solved"
    assert model.is_valid_solution(), "Solution should be valid"
    
    solution = model.get_solution()
    edge_vars_sol = model.solver.get_values(model.edge_vars)
    additional_edges_used_sol = model.solver.get_values(model.additional_edges_used_vars)
    
    # Check that each additional edge is counted at most once
    for edge in additional_edges:
        u, v = edge
        # Count how many paths use this edge
        paths_using_edge = sum(edge_vars_sol[(u, v, i)] for i in range(model.k))
        # The binary variable should be 1 if any path uses it, 0 otherwise
        binary_value = additional_edges_used_sol[edge]
        
        if paths_using_edge > 0:
            assert binary_value == 1, f"Edge {edge} is used by {paths_using_edge} paths, so binary variable should be 1"
        else:
            assert binary_value == 0, f"Edge {edge} is not used, so binary variable should be 0"


def test_additional_edges_lambda_with_different_values():
    """Test that model behaves correctly with various lambda values."""
    import networkx as nx
    
    # Create a test graph
    G = nx.DiGraph()
    G.add_edge('s', 'a', flow=3)
    G.add_edge('s', 'b', flow=3)
    G.add_edge('a', 't', flow=3)
    G.add_edge('b', 't', flow=3)
    
    additional_edges = [('a', 'b')]
    
    objectives = {}
    
    for lambda_val in [0.0, 0.5, 1.0, 2.0, 5.0]:
        model = fp.kLeastAbsErrors(
            G=G,
            k=2,
            flow_attr="flow",
            additional_edges=additional_edges,
            additional_edges_lambda=lambda_val,
            solver_options={"external_solver": "highs"},
        )
        model.solve()
        
        assert model.is_solved(), f"Model should be solved for lambda={lambda_val}"
        assert model.is_valid_solution(), f"Solution should be valid for lambda={lambda_val}"
        
        objectives[lambda_val] = model.get_objective_value()
    
    # Verify that objectives form a reasonable progression
    # Generally, as lambda increases, the objective should not decrease
    # (assuming additional edges are being used)
    lambda_vals = sorted(objectives.keys())
    for i in range(len(lambda_vals) - 1):
        curr_obj = objectives[lambda_vals[i]]
        next_obj = objectives[lambda_vals[i + 1]]
        # Due to different optimization paths, we allow some tolerance
        # but generally higher lambda should lead to higher or equal objective
        assert next_obj >= curr_obj - 1e-6, \
            f"Objective should increase with lambda: {curr_obj} at lambda={lambda_vals[i]} vs {next_obj} at lambda={lambda_vals[i+1]}"


def test_additional_edges_lambda_validation_in_objective():
    """Test that the objective value reported by get_objective_value() matches solver objective."""
    import networkx as nx
    
    # Create test graph
    G = nx.DiGraph()
    G.add_edge('s', 'a', flow=2)
    G.add_edge('a', 't', flow=2)
    G.add_edge('s', 'b', flow=2)
    G.add_edge('b', 't', flow=2)
    
    additional_edges = [('a', 'b')]
    
    model = fp.kLeastAbsErrors(
        G=G,
        k=2,
        flow_attr="flow",
        additional_edges=additional_edges,
        additional_edges_lambda=3.0,
        solver_options={"external_solver": "highs"},
    )
    model.solve()
    
    assert model.is_solved(), "Model should be solved"
    
    # Get objective values
    computed_obj = model.get_objective_value()
    solver_obj = model.solver.get_objective_value()
    
    # They should be very close (within numerical tolerance)
    assert abs(computed_obj - solver_obj) < 1e-5, \
        f"Computed objective {computed_obj} should match solver objective {solver_obj}"
