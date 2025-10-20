import pytest
import itertools
import flowpaths as fp

weight_type = [int, float]
solvers = ["highs", "gurobi"]

settings_flags = {
    "optimize_with_safe_paths": [True, False],
    "optimize_with_safe_sequences": [True, False],
    "optimize_with_safe_zero_edges": [True, False],
    "optimize_with_flow_safe_paths": [True, False],
    "optimize_with_greedy": [True, False],
    "optimize_with_safety_as_subpath_constraints": [True, False],
}

params = list(itertools.product(
    weight_type,
    solvers,
    *settings_flags.values()
    ))

def is_valid_optimization_setting_mfd(opt):
        safety_opt = (
            opt["optimize_with_safe_paths"]
            + opt["optimize_with_safe_sequences"]
            + opt["optimize_with_flow_safe_paths"]
        )
        if safety_opt > 1:
            return False
        if safety_opt == 0 and (opt["optimize_with_safe_zero_edges"] or opt["optimize_with_safety_as_subpath_constraints"]):
            return False
        if opt["optimize_with_greedy"] and safety_opt > 0:
            return False
        if opt["optimize_with_safety_as_subpath_constraints"] and opt["optimize_with_safe_zero_edges"]:
            return False
        return True

def run_test(graph, test_index, params):
    print("*******************************************")
    print(f"Testing graph {test_index}: {fp.utils.fpid(graph)}") 
    print("*******************************************")

    first_solution_size = None

    for settings in params:
        print("Testing settings:", settings)
        optimization_options = {key: setting for key, setting in zip(settings_flags.keys(), settings[2:])}
        if not is_valid_optimization_setting_mfd(optimization_options):
            continue

        print("-------------------------------------------")
        print("Solving with optimization options:", {key for key in optimization_options if optimization_options[key]})

        mfd_model = fp.MinFlowDecomp(
            graph,
            flow_attr="flow",
            weight_type=settings[0],
            optimization_options=optimization_options,
            solver_options={"external_solver": settings[1]},
        )
        mfd_model.solve()
        print(mfd_model.solve_statistics)

        # Checks
        assert mfd_model.is_solved(), "Model should be solved"
        assert mfd_model.is_valid_solution(), "The solution is not a valid flow decomposition, under the default tolerance."

        current_solution = mfd_model.get_solution()
        if first_solution_size is None:
            first_solution_size = len(current_solution["paths"])
        else:
            assert first_solution_size == len(current_solution["paths"]), "The size of the solution should be the same for all settings."


graphs = fp.graphutils.read_graphs("./tests/test_graphs_flow_conservation.graph")
@pytest.mark.parametrize("graph, idx", [(g, i) for i, g in enumerate(graphs)])
def test(graph, idx):
    run_test(graph, idx, params)
