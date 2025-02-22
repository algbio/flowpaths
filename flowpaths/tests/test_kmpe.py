import unittest
import itertools
from utils import graphutils as graphutils
import kminpatherror as kmpe
import stdigraph as stdigraph

# Run as `python -m tests.test_mfd` in the `flowpaths` directory


class TestkMinPathError(unittest.TestCase):

    def setUp(self):
        weight_type = [float]  # 0
        optimize_with_safe_paths = [True, False]  # 1
        optimize_with_safe_sequences = [True, False]  # 2
        optimize_with_safe_zero_edges = [True, False]  # 3
        solvers = ["gurobi", "highs"]  # 4

        self.graphs = graphutils.read_graphs("./tests/tests.graph")
        self.params = list(
            itertools.product(
                weight_type,
                optimize_with_safe_paths,
                optimize_with_safe_sequences,
                optimize_with_safe_zero_edges,
                solvers,
            )
        )

    def test_min_flow_decomp_solved(self):

        for graph in self.graphs:

            print("Testing graph: ", graph.graph["id"])
            stG = stdigraph.stDiGraph(graph)
            num_paths = stG.get_width()

            first_solution_size = None

            for settings in self.params:
                # safe paths and safe sequences cannot be both True
                if settings[1] == True and settings[2] == True:
                    continue
                # we don't allow safe paths and safe sequences both False
                if (
                    settings[1] == False
                    and settings[2] == False
                ):
                    continue
                # if optimize_with_greedy, it makes no sense to try the safety optimizations
                if settings[4] == True and (
                    settings[2] == True or settings[3] == True or settings[4] == True
                ):
                    continue

                kmpe_model = kmpe.kMinPathError(
                    graph,
                    flow_attr="flow",
                    num_paths=num_paths,
                    weight_type=settings[0],
                    optimize_with_safe_paths=settings[1],
                    optimize_with_safe_sequences=settings[2],
                    optimize_with_safe_zero_edges=settings[3],
                    external_solver=settings[4],
                )
                kmpe_model.solve()
                # print(kmpe_model.kwargs)
                print(settings)
                print(kmpe_model.solve_statistics)
                self.assertTrue(kmpe_model.is_solved, "Model should be solved")
                self.assertTrue(
                    kmpe_model.verify_solution(),
                    "The solution is not a valid flow decomposition, under the default tolerance.",
                )
                self.assertTrue(
                    kmpe_model.verify_edge_position(),
                    "The MILP encoded edge positions (inside paths) are not correct.",
                )

                if first_solution_size == None:
                    first_solution_size = len(kmpe_model.solution[0])
                else:
                    self.assertEqual(
                        first_solution_size,
                        len(kmpe_model.solution[0]),
                        "The size of the solution should be the same for all settings.",
                    )


if __name__ == "__main__":
    unittest.main()
