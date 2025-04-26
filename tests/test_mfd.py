import unittest
import itertools
import functools
import flowpaths as fp

# Run as `python -m tests.test_mfd` in the top `flowpaths` directory

class TestMinFlowDecomp(unittest.TestCase):
    
    def test(self, graph, test_index, params):
        print("*******************************************")
        print(f"Testing graph {test_index}: {fp.utils.fpid(graph)}")
        print("*******************************************")

        first_solution_size = None

        for settings in params:

            optimization_options = {
                "optimize_with_safe_paths":         settings[2],
                "optimize_with_safe_sequences":     settings[3],
                "optimize_with_safe_zero_edges":    settings[4],
                "optimize_with_flow_safe_paths":    settings[5],
                "optimize_with_greedy":             settings[6],
                "optimize_with_safety_as_subpath_constraints": settings[7],
            }

            safety_opt = optimization_options["optimize_with_safe_paths"] + \
                            optimization_options["optimize_with_safe_sequences"] + \
                            optimization_options["optimize_with_flow_safe_paths"]

            if safety_opt > 1:
                continue 
            if safety_opt == 0:
                if optimization_options["optimize_with_safe_zero_edges"] or \
                    optimization_options["optimize_with_safety_as_subpath_constraints"]:
                    continue
                        
            # if optimize_with_greedy, it makes no sense to try the safety optimizations
            if optimization_options["optimize_with_greedy"] and safety_opt > 0:
                continue

            if optimization_options["optimize_with_safety_as_subpath_constraints"] and optimization_options["optimize_with_safe_zero_edges"]:
                continue

            print("-------------------------------------------")
            print("Solving with optimization options:", {key for key in optimization_options if optimization_options[key]})

            solver_options = {"solver": settings[1]}

            mfd_model = fp.MinFlowDecomp(
                graph,
                flow_attr="flow",
                weight_type=settings[0],
                optimization_options=optimization_options,
                solver_options=solver_options,
            )
            mfd_model.solve()
            print(mfd_model.solve_statistics)


            # Checks
            self.assertTrue(mfd_model.is_solved(), "Model should be solved")
            self.assertTrue(mfd_model.is_valid_solution(),
                "The solution is not a valid flow decomposition, under the default tolerance.")

            current_solution = mfd_model.get_solution()
            if first_solution_size is None:
                first_solution_size = len(current_solution["paths"])
            else:
                self.assertEqual(first_solution_size, len(current_solution["paths"]),
                    "The size of the solution should be the same for all settings.")

weight_type = [int, float]  # 0
solvers = ["highs", "gurobi"]  # 1
optimize_with_safe_paths = [True, False]  # 2
optimize_with_safe_sequences = [True, False]  # 3
optimize_with_safe_zero_edges = [True, False]  # 4
optimize_with_flow_safe_paths = [True, False]  # 5
optimize_with_greedy = [True, False]  # 6
optimize_with_safety_as_subpath_constraints = [True, False]  # 7

graphs = fp.graphutils.read_graphs("./tests/tests.graph")
params = list(
    itertools.product(
        weight_type,
        solvers,
        optimize_with_safe_paths,
        optimize_with_safe_sequences,
        optimize_with_safe_zero_edges,
        optimize_with_flow_safe_paths,
        optimize_with_greedy,
        optimize_with_safety_as_subpath_constraints
    )
)

# Dynamically create one test per graph
graphs = fp.graphutils.read_graphs("./tests/test_graphs_mfd.graph")
for idx, graph in enumerate(graphs):
    test_func = functools.partialmethod(TestMinFlowDecomp.test, graph, idx, params)
    setattr(TestMinFlowDecomp, f"test_graph_{idx}", test_func)

# Remove the template method, so unittest doesn't try to run it
delattr(TestMinFlowDecomp, 'test')    

if __name__ == "__main__":
    unittest.main()
