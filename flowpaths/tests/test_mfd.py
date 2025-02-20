import unittest
import networkx as nx
import itertools
from utils import graphutils as graphutils
import minflowdecomp as mfd

# Run as `python -m tests.test_mfd` in the `flowpaths` directory


class TestMinFlowDecomp(unittest.TestCase):

    def setUp(self):
        weight_type = [int, float]  # 0
        optimize_with_safe_paths = [True, False]  # 1
        optimize_with_safe_sequences = [True, False]  # 2
        optimize_with_safe_zero_edges = [True, False]  # 3
        optimize_with_greedy = [True, False]  # 4
        solvers = ["gurobi", "highs"]  # 5

        self.graphs = graphutils.read_graphs("./tests/tests.graph")
        self.params = list(
            itertools.product(
                weight_type,
                optimize_with_safe_paths,
                optimize_with_safe_sequences,
                optimize_with_safe_zero_edges,
                optimize_with_greedy,
                solvers,
            )
        )

    def test_min_flow_decomp_solved(self):

        for graph in self.graphs:

            print("Testing graph: ", graph.graph["id"])

            first_solution_size = None

            for settings in self.params:
                # safe paths and safe sequences cannot be both True
                if settings[1] == True and settings[2] == True:
                    continue
                # if safe paths and safe sequences are False, then it makes no sense to optimize_with_safe_zero_edges
                if (
                    settings[1] == False
                    and settings[2] == False
                    and settings[3] == True
                ):
                    continue
                # if optimize_with_greedy, it makes no sense to try the safety optimizations
                if settings[4] == True and (
                    settings[2] == True or settings[3] == True or settings[4] == True
                ):
                    continue

                mfd_model = mfd.MinFlowDecomp(
                    graph,
                    flow_attr="flow",
                    weight_type=settings[0],
                    optimize_with_safe_paths=settings[1],
                    optimize_with_safe_sequences=settings[2],
                    optimize_with_safe_zero_edges=settings[3],
                    optimize_with_greedy=settings[4],
                    external_solver=settings[5],
                )
                mfd_model.solve()
                print(mfd_model.kwargs)
                print(mfd_model.solve_statistics)
                self.assertTrue(mfd_model.solved, "Model should be solved")
                self.assertTrue(
                    mfd_model.check_solution(),
                    "The solution is not a valid flow decomposition, under the default tolerance.",
                )

                if first_solution_size == None:
                    first_solution_size = len(mfd_model.solution[0])
                else:
                    self.assertEqual(
                        first_solution_size,
                        len(mfd_model.solution[0]),
                        "The size of the solution should be the same for all settings.",
                    )


if __name__ == "__main__":
    unittest.main()
