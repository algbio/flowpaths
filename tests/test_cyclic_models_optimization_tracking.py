import pytest
import networkx as nx
import flowpaths as fp


class TestCyclicOptimizationTracking:
    """Test suite for optimization tracking in cyclic models."""

    @pytest.fixture
    def test_graph(self):
        """Create a small cyclic graph with feasible source/sink flow."""
        #       s
        #       |
        #       4
        #       |
        #       v
        #  +--> a ----+
        #  |    |     |
        #  1    3     2
        #  |    |     |
        #  |    v     v
        #  +--- b -2> t
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=4)
        G.add_edge("a", "b", flow=3)
        G.add_edge("b", "a", flow=1)
        G.add_edge("a", "t", flow=2)
        G.add_edge("b", "t", flow=2)
        return G

    def test_no_optimizations(self, test_graph):
        """No cyclic safety optimization should be tracked when disabled."""
        optimization_options = {
            "optimize_with_safe_sequences": False,
            "optimize_with_safety_as_subset_constraints": False,
            "optimize_with_max_safe_antichain_as_subset_constraints": False,
            "optimize_with_safe_sequences_fix_zero_edges": False,
        }

        mfd = fp.MinFlowDecompCycles(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options,
        )
        mfd.solve()

        assert mfd.is_solved()
        stats = mfd.solve_statistics
        assert "optimizations_applied" in stats

        optimizations = stats["optimizations_applied"]
        assert "optimize_with_safe_sequences" not in optimizations
        assert "optimize_with_safe_lists" not in optimizations
        assert "optimize_with_safe_sequences_fix_zero_edges" not in optimizations
        assert "optimize_with_safety_as_subset_constraints" not in optimizations
        assert "optimize_with_max_safe_antichain_as_subset_constraints" not in optimizations

    def test_safe_sequences_optimization(self, test_graph):
        """Safe sequences and its downstream fixing should be tracked."""
        optimization_options = {
            "optimize_with_safe_sequences": True,
            "optimize_with_safety_as_subset_constraints": False,
            "optimize_with_max_safe_antichain_as_subset_constraints": False,
            "optimize_with_safe_sequences_fix_zero_edges": False,
        }

        mfd = fp.MinFlowDecompCycles(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options,
        )
        mfd.solve()

        assert mfd.is_solved()
        optimizations = mfd.solve_statistics["optimizations_applied"]

        assert "optimize_with_safe_sequences" in optimizations
        assert "optimize_with_safe_lists" in optimizations
        assert "optimize_with_safety_as_subset_constraints" not in optimizations

    def test_safe_sequences_fix_zero_edges_tracking(self, test_graph):
        """Zero-edge pruning from safe sequences should be tracked."""
        optimization_options = {
            "optimize_with_safe_sequences": True,
            "optimize_with_safety_as_subset_constraints": False,
            "optimize_with_max_safe_antichain_as_subset_constraints": False,
            "optimize_with_safe_sequences_fix_zero_edges": True,
        }

        mfd = fp.MinFlowDecompCycles(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options,
        )
        mfd.solve()

        assert mfd.is_solved()
        optimizations = mfd.solve_statistics["optimizations_applied"]

        assert "optimize_with_safe_sequences" in optimizations
        assert "optimize_with_safe_sequences_fix_zero_edges" in optimizations

    def test_safety_as_subset_constraints_optimization(self, test_graph):
        """Safety-as-subset-constraints should be tracked distinctly."""
        optimization_options = {
            "optimize_with_safe_sequences": False,
            "optimize_with_safety_as_subset_constraints": True,
            "optimize_with_max_safe_antichain_as_subset_constraints": False,
        }

        mfd = fp.MinFlowDecompCycles(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options,
        )
        mfd.solve()

        assert mfd.is_solved()
        optimizations = mfd.solve_statistics["optimizations_applied"]

        assert "optimize_with_safety_as_subset_constraints" in optimizations
        assert "optimize_with_safe_lists" not in optimizations

    def test_max_safe_antichain_as_subset_constraints_optimization(self, test_graph):
        """Max antichain safety conversion should be tracked."""
        optimization_options = {
            "optimize_with_safe_sequences": False,
            "optimize_with_safety_as_subset_constraints": False,
            "optimize_with_max_safe_antichain_as_subset_constraints": True,
        }

        mfd = fp.MinFlowDecompCycles(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options,
        )
        mfd.solve()

        assert mfd.is_solved()
        optimizations = mfd.solve_statistics["optimizations_applied"]

        assert "optimize_with_max_safe_antichain_as_subset_constraints" in optimizations
        assert "optimize_with_safe_lists" not in optimizations

    def test_optimization_tracking_with_kflow_decomp_cycles(self, test_graph):
        """Tracking should also work for kFlowDecompCycles."""
        optimization_options = {
            "optimize_with_safe_sequences": True,
            "optimize_with_safe_sequences_fix_zero_edges": True,
        }

        kfd = fp.kFlowDecompCycles(
            test_graph,
            flow_attr="flow",
            k=2,
            optimization_options=optimization_options,
        )
        kfd.solve()

        if kfd.is_solved():
            optimizations = kfd.solve_statistics["optimizations_applied"]
            assert isinstance(optimizations, set)
            assert "optimize_with_safe_sequences" in optimizations

    def test_optimization_tracking_with_kmin_path_error_cycles(self, test_graph):
        """Tracking should also work for kMinPathErrorCycles."""
        optimization_options = {
            "optimize_with_safe_sequences": True,
            "optimize_with_safe_sequences_fix_zero_edges": True,
        }

        mpe = fp.kMinPathErrorCycles(
            test_graph,
            flow_attr="flow",
            k=2,
            optimization_options=optimization_options,
        )
        mpe.solve()

        if mpe.is_solved():
            optimizations = mpe.solve_statistics["optimizations_applied"]
            assert isinstance(optimizations, set)
            assert "optimize_with_safe_sequences" in optimizations

    def test_optimization_statistics_structure(self, test_graph):
        """solve_statistics should expose optimization tracking as a string set."""
        mfd = fp.MinFlowDecompCycles(test_graph, flow_attr="flow")
        mfd.solve()

        assert mfd.is_solved()
        stats = mfd.solve_statistics

        assert "optimizations_applied" in stats
        assert isinstance(stats["optimizations_applied"], set)
        assert all(isinstance(opt, str) for opt in stats["optimizations_applied"])
        assert len(stats["optimizations_applied"]) == len(set(stats["optimizations_applied"]))
