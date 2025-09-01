import pytest
import itertools
import flowpaths as fp
import networkx as nx
from pathlib import Path

weight_type = [float]
solvers = ["gurobi"]
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
