import pytest
import itertools
import flowpaths as fp

weight_type = [int, float]
solvers = ["highs", "gurobi"]

tolerance = 1

settings_flags = {
    "optimize_with_safe_paths": [True, False],
    "optimize_with_safe_sequences": [True, False],
    "optimize_with_safety_as_subpath_constraints": [True],
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

    for settings in params:
        print("Testing settings:", settings)
        optimization_options = {key: setting for key, setting in zip(settings_flags.keys(), settings[2:])}
        if not is_valid_optimization_setting_lae(optimization_options):
            continue

        print("-------------------------------------------")
        print("Solving with optimization options:", {key for key in optimization_options if optimization_options[key]})

        width = fp.stDiGraph(graph).get_width()

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
        assert lae_model.is_valid_solution(), "The solution is not a valid solution, under the default tolerance."

        obj_value = lae_model.get_objective_value()
        if first_obj_value is None:
            first_obj_value = lae_model.get_objective_value()
        else:
            assert abs(first_obj_value - obj_value) < tolerance, "The objective value should be the same for all settings."


graphs = fp.graphutils.read_graphs("./tests/test_graphs_errors.graph")
@pytest.mark.parametrize("graph, idx", [(g, i) for i, g in enumerate(graphs)])
def test(graph, idx):
    run_test(graph, idx, params)
