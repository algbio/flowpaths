import pytest
import itertools
import flowpaths as fp

weight_type = [int]
solvers = ["highs", "gurobi"]

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
            solver_options={"external_solver": "gurobi"},
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
            solver_options={"external_solver": "gurobi"},
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
