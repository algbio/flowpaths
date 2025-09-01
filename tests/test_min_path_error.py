import pytest
import itertools
import flowpaths as fp

weight_type = [int]
solvers = ["highs", "gurobi"]

tolerance = 1

settings_flags = {
    "optimize_with_safe_paths": [True, False],
    "optimize_with_safe_sequences": [True, False],
    "optimize_with_safe_zero_edges": [True, False],
    "optimize_with_safety_as_subpath_constraints": [True, False],
}

params = list(itertools.product(
    weight_type,
    solvers,
    *settings_flags.values()
    ))

def is_valid_optimization_setting_mpe(opt):
        safety_opt = (
            opt["optimize_with_safe_paths"]
            + opt["optimize_with_safe_sequences"]
        )
        if safety_opt > 1:
            return False
        if safety_opt == 0:
            if opt["optimize_with_safe_zero_edges"] or opt["optimize_with_safety_as_subpath_constraints"]:
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
        if not is_valid_optimization_setting_mpe(optimization_options):
            continue

        print("-------------------------------------------")
        print("Solving with optimization options:", {key for key in optimization_options if optimization_options[key]})

        width = fp.stDAG(graph).get_width()

        mpe_model = fp.kLeastAbsErrors(
            G=graph,
            k=width,
            flow_attr="flow",
            weight_type=settings[0],
            optimization_options=optimization_options,
            solver_options={"external_solver": settings[1]},
        )
        mpe_model.solve()
        print(mpe_model.solve_statistics)

        # Checks
        assert mpe_model.is_solved(), "Model should be solved"
        assert mpe_model.is_valid_solution(), "The solution is not a valid solution, under the default tolerance."
        assert mpe_model.verify_edge_position(), "Edge positions are not valid."

        obj_value = mpe_model.get_objective_value()
        if first_obj_value is None:
            first_obj_value = mpe_model.get_objective_value()
            first_path_weights = mpe_model.get_solution()["weights"]
            first_weight_type = settings[0]
            first_paths = mpe_model.get_solution()["paths"]
        else:
            assert abs(first_obj_value - obj_value) < tolerance, "The objective value should be the same for all settings."

    # Testing the solution_weights_superset optimization
    solution_weights_superset = first_path_weights + [first_weight_type(weight * (2 if idx % 2 else 0.5)) for idx, weight in enumerate(first_path_weights)]
    print("Solution weights superset:", solution_weights_superset)

    mpe_model = fp.kLeastAbsErrors(
            G=graph,
            k=width,
            flow_attr="flow",
            weight_type=first_weight_type,
            solution_weights_superset=solution_weights_superset,
            solver_options={"external_solver": "gurobi"},
        )
    mpe_model.solve() 
    print(mpe_model.solve_statistics)
    assert mpe_model.is_solved(), "Model should be solved"
    assert mpe_model.is_valid_solution(), "The solution is not a valid solution, under the default tolerance."
    obj_value = mpe_model.get_objective_value()
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

    mpe_model = fp.kLeastAbsErrors(
            G=graph,
            k=width,
            flow_attr="flow",
            weight_type=first_weight_type,
            solution_weights_superset=solution_weights_superset,
            subpath_constraints=subpath_constraints,
            solver_options={"external_solver": "gurobi"},
        )
    mpe_model.solve() 
    print(mpe_model.solve_statistics)
    assert mpe_model.is_solved(), "Model should be solved"
    assert mpe_model.is_valid_solution(), "The solution is not a valid solution, under the default tolerance."
    obj_value = mpe_model.get_objective_value()
    print("Objective value with subpath constraints:", obj_value)
    print("Objective value without subpath constraints and without solution_weights_superset:", first_obj_value)
    assert abs(first_obj_value - obj_value) < tolerance, "The objective value should be the same for all settings."

graphs = fp.graphutils.read_graphs("./tests/test_graphs_errors.graph")
@pytest.mark.parametrize("graph, idx", [(g, i) for i, g in enumerate(graphs)])
def test(graph, idx):
    run_test(graph, idx, params)
