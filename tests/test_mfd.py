import unittest
import itertools
import flowpaths as fp

# Run as `python -m tests.test_mfd` in the top `flowpaths` directory


class TestMinFlowDecomp(unittest.TestCase):

    def setUp(self):
        weight_type = [int, float]  # 0
        solvers = ["highs", "gurobi"]  # 1
        optimize_with_safe_paths = [True, False]  # 2
        optimize_with_safe_sequences = [True, False]  # 3
        optimize_with_safe_zero_edges = [True, False]  # 4
        optimize_with_flow_safe_paths = [True, False]  # 5
        optimize_with_greedy = [True, False]  # 6
        

        self.graphs = fp.graphutils.read_graphs("./tests/tests.graph")
        self.params = list(
            itertools.product(
                weight_type,
                solvers,
                optimize_with_safe_paths,
                optimize_with_safe_sequences,
                optimize_with_safe_zero_edges,
                optimize_with_flow_safe_paths,
                optimize_with_greedy,
            )
        )

    def test_min_flow_decomp_solved(self):

        for graph in self.graphs:

            print("*******************************************")
            print("Testing graph: ", graph.graph["id"])
            print("*******************************************")

            first_solution_size = None

            for settings in self.params:

                optimization_options = {
                    "optimize_with_safe_paths":         settings[2],
                    "optimize_with_safe_sequences":     settings[3],
                    "optimize_with_safe_zero_edges":    settings[4],
                    "optimize_with_flow_safe_paths":    settings[5],
                    "optimize_with_greedy":             settings[6],
                }

                # we don't allow safe paths and safe sequences both True
                if optimization_options["optimize_with_safe_paths"] and optimization_options["optimize_with_safe_sequences"]:
                    continue

                # we don't allow flow safe paths and safe sequences both True
                if optimization_options["optimize_with_flow_safe_paths"] and optimization_options["optimize_with_safe_sequences"]:
                    continue

                # we don't allow safe paths and flow safe paths both True
                if optimization_options["optimize_with_safe_paths"] and optimization_options["optimize_with_flow_safe_paths"]:
                    continue
                
                # we don't allow safe paths, safe sequences, flow safe paths all False
                if not optimization_options["optimize_with_safe_paths"] and not optimization_options["optimize_with_safe_sequences"] and not optimization_options["optimize_with_flow_safe_paths"]:
                    continue
                
                # if optimize_with_greedy, it makes no sense to try the safety optimizations
                if optimization_options["optimize_with_greedy"] and (
                    optimization_options["optimize_with_safe_paths"]
                    or optimization_options["optimize_with_safe_sequences"]
                    or optimization_options["optimize_with_safe_zero_edges"]
                    or optimization_options["optimize_with_flow_safe_paths"]
                ):
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
                # optimization_options.pop("trusted_edges_for_safety", None)
                # optimization_options.pop("external_safe_paths", None)
                # print(optimization_options)
                print(mfd_model.solve_statistics)
                self.assertTrue(mfd_model.is_solved(), "Model should be solved")
                self.assertTrue(
                    mfd_model.is_valid_solution(),
                    "The solution is not a valid flow decomposition, under the default tolerance.",
                )

                current_solution = mfd_model.get_solution()
                if first_solution_size == None:
                    first_solution_size = len(current_solution["paths"])
                else:
                    self.assertEqual(
                        first_solution_size,
                        len(current_solution["paths"]),
                        "The size of the solution should be the same for all settings.",
                    )


if __name__ == "__main__":
    unittest.main()
