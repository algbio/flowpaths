import pytest
import networkx as nx
import flowpaths as fp


class TestAcyclicModels:
    """Test suite for acyclic (DAG) graph decomposition models."""
    
    @pytest.fixture
    def simple_dag(self):
        """Create a simple DAG for testing acyclic models."""
        #         s
        #        / \
        #       5   3
        #      /     \
        #     a       b
        #     |\     /|
        #     3 \   / 2
        #     |  \ /  |
        #     | 2 X 1 |
        #     |  / \  |
        #     |/     \|
        #     c       d
        #      \     /
        #       4   4
        #        \ /
        #         t
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=5)
        G.add_edge("s", "b", flow=3)
        G.add_edge("a", "c", flow=3)
        G.add_edge("a", "d", flow=2)
        G.add_edge("b", "c", flow=1)
        G.add_edge("b", "d", flow=2)
        G.add_edge("c", "t", flow=4)
        G.add_edge("d", "t", flow=4)
        return G
    
    @pytest.fixture
    def linear_dag(self):
        """Create a linear path DAG."""
        # s -10-> a -10-> b -10-> c -10-> t
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=10)
        G.add_edge("a", "b", flow=10)
        G.add_edge("b", "c", flow=10)
        G.add_edge("c", "t", flow=10)
        return G
    
    @pytest.fixture
    def complex_dag(self):
        """Create a more complex DAG with multiple paths."""
        #           s
        #         / | \
        #        7  5  3
        #       /   |   \
        #      a    b    c
        #     /\   /\    |
        #    4  3 2  3   3
        #   /    \|    \|
        #  d      e      f
        #   \     |     /
        #    4    5    6
        #     \   |   /
        #      \  |  /
        #       \ | /
        #         t
        #
        # \| above e: a->e (3, diagonal) and b->e (2, straight) merge at e
        # \| above f: b->f (3, diagonal) and c->f (3, straight) merge at f
        G = nx.DiGraph()
        # Source splits into three paths
        G.add_edge("s", "a", flow=7)
        G.add_edge("s", "b", flow=5)
        G.add_edge("s", "c", flow=3)
        
        # Middle layer with cross connections
        G.add_edge("a", "d", flow=4)
        G.add_edge("a", "e", flow=3)
        G.add_edge("b", "e", flow=2)
        G.add_edge("b", "f", flow=3)
        G.add_edge("c", "f", flow=3)
        
        # Converge to sink
        G.add_edge("d", "t", flow=4)
        G.add_edge("e", "t", flow=5)
        G.add_edge("f", "t", flow=6)
        return G

    def test_min_flow_decomp_simple_dag(self, simple_dag):
        """Test MinFlowDecomp on a simple DAG."""
        mfd = fp.MinFlowDecomp(simple_dag, flow_attr="flow")
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
        
        solution = mfd.get_solution()
        assert "paths" in solution
        assert "weights" in solution
        assert len(solution["paths"]) == 4
        assert len(solution["weights"]) == len(solution["paths"])
        
        # Verify all weights are positive
        assert all(w > 0 for w in solution["weights"])
        
        # Verify paths are s-t paths
        for path in solution["paths"]:
            assert path[0] == "s"
            assert path[-1] == "t"
    
    def test_min_flow_decomp_linear_dag(self, linear_dag):
        """Test MinFlowDecomp on a linear DAG - should find exactly 1 path."""
        mfd = fp.MinFlowDecomp(linear_dag, flow_attr="flow")
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
        
        solution = mfd.get_solution()
        # Linear graph should have exactly 1 path
        assert len(solution["paths"]) == 1
        assert solution["weights"][0] == 10
        assert solution["paths"][0] == ["s", "a", "b", "c", "t"]
    
    def test_min_flow_decomp_complex_dag(self, complex_dag):
        """Test MinFlowDecomp on a complex DAG."""
        mfd = fp.MinFlowDecomp(complex_dag, flow_attr="flow")
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
        
        solution = mfd.get_solution()
        assert len(solution["paths"]) == 5
        
        # Verify flow conservation - sum of path flows should equal total flow
        total_flow = sum(solution["weights"])
        expected_flow = sum(attr["flow"] for _, _, attr in complex_dag.out_edges("s", data=True))
        assert abs(total_flow - expected_flow) < 1e-6
    
    def test_kflow_decomp_simple_dag(self, simple_dag):
        """Test kFlowDecomp with a fixed number of paths."""
        # Try with k=4 paths (enough to be feasible for simple_dag)
        kfd = fp.kFlowDecomp(simple_dag, k=4, flow_attr="flow")
        kfd.solve()
        
        # Check if solved (might be infeasible if k is too small)
        if kfd.is_solved():
            assert kfd.is_valid_solution()
            solution = kfd.get_solution()
            assert len(solution["paths"]) == 4
            assert len(solution["weights"]) == 4
    
    def test_kflow_decomp_linear_dag(self, linear_dag):
        """Test kFlowDecomp on linear DAG - k=1 should be feasible."""
        kfd = fp.kFlowDecomp(linear_dag, k=1, flow_attr="flow")
        kfd.solve()
        
        assert kfd.is_solved()
        assert kfd.is_valid_solution()
        
        solution = kfd.get_solution()
        assert len(solution["paths"]) == 1
        assert solution["paths"][0] == ["s", "a", "b", "c", "t"]
    
    def test_kmin_path_error_simple_dag(self, simple_dag):
        """Test kMinPathError - find k paths that minimize flow error."""
        # Use k=4 paths to approximate the flow
        kpe = fp.kMinPathError(simple_dag, k=4, flow_attr="flow")
        kpe.solve()
        
        # This model allows infeasibility, but should typically solve
        if kpe.is_solved():
            solution = kpe.get_solution()
            assert len(solution["paths"]) == 4
            assert len(solution["weights"]) == 4
            
            # Verify all weights are non-negative
            assert all(w >= 0 for w in solution["weights"])
    
    def test_kleast_abs_errors_simple_dag(self, simple_dag):
        """Test kLeastAbsErrors - minimize sum of absolute errors."""
        klae = fp.kLeastAbsErrors(simple_dag, k=2, flow_attr="flow")
        klae.solve()
        
        assert klae.is_solved()
        
        solution = klae.get_solution()
        assert len(solution["paths"]) == 2
        assert len(solution["weights"]) == 2
    
    def test_min_path_cover_simple_dag(self, simple_dag):
        """Test MinPathCover - find minimum number of paths to cover all edges."""
        mpc = fp.MinPathCover(simple_dag)
        mpc.solve()
        
        assert mpc.is_solved()
        assert mpc.is_valid_solution()
        
        solution = mpc.get_solution()
        assert len(solution["paths"]) > 0
        
        # Verify all original edges are covered (paths may include internal source/sink nodes)
        original_edges = set(simple_dag.edges())
        covered_edges = set()
        for path in solution["paths"]:
            for i in range(len(path) - 1):
                edge = (path[i], path[i+1])
                if edge in original_edges:
                    covered_edges.add(edge)
        
        assert original_edges.issubset(covered_edges)
    
    def test_min_set_cover_generic(self):
        """Test MinSetCover - generic set cover problem."""
        # MinSetCover is a generic set cover solver, not graph-specific
        universe = [1, 2, 3, 4, 5]
        subsets = [
            [1, 2],
            [2, 3, 4],
            [4, 5],
            [1, 3, 5]
        ]
        subset_weights = [1, 1, 1, 1]  # Equal weights
        
        msc = fp.MinSetCover(universe=universe, subsets=subsets, subset_weights=subset_weights)
        msc.solve()
        
        assert msc.is_solved()
        
        solution = msc.get_solution()
        assert len(solution) > 0
        
        # Verify all elements are covered
        covered = set()
        for idx in solution:
            covered.update(subsets[idx])
        
        assert set(universe).issubset(covered)
    
    def test_min_flow_decomp_with_weight_types(self, simple_dag):
        """Test MinFlowDecomp with different weight types (int vs float)."""
        # Test with integer weights
        mfd_int = fp.MinFlowDecomp(simple_dag, flow_attr="flow", weight_type=int)
        mfd_int.solve()
        assert mfd_int.is_solved()
        
        sol_int = mfd_int.get_solution()
        # All weights should be numeric and non-negative
        assert all(w > 0 for w in sol_int["weights"])
        
        # Test with float weights
        mfd_float = fp.MinFlowDecomp(simple_dag, flow_attr="flow", weight_type=float)
        mfd_float.solve()
        assert mfd_float.is_solved()
        
        sol_float = mfd_float.get_solution()
        # All weights should be numeric and non-negative
        assert all(w > 0 for w in sol_float["weights"])
    
    def test_min_flow_decomp_with_solver_options(self, simple_dag):
        """Test MinFlowDecomp with custom solver options."""
        solver_options = {
            "time_limit": 10.0,
            "threads": 1,
            "log_to_console": False,
        }
        
        mfd = fp.MinFlowDecomp(
            simple_dag,
            flow_attr="flow",
            solver_options=solver_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
    
    def test_min_flow_decomp_with_optimization_options(self, simple_dag):
        """Test MinFlowDecomp with various optimization options."""
        # Use greedy optimization which should work well
        optimization_options = {
            "optimize_with_greedy": True,
        }
        
        mfd = fp.MinFlowDecomp(
            simple_dag,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
    
    def test_elements_to_ignore(self):
        """Test MinFlowDecomp with ignored edges - test that solution is still valid."""
        # Create a graph with alternative paths
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=5)
        G.add_edge("s", "b", flow=5)
        G.add_edge("a", "t", flow=5)
        G.add_edge("b", "t", flow=5)
        
        # Ignore edge (s, b) - MinFlowDecomp will not explain flow on this edge
        edges_to_ignore = [("s", "b")]
        
        mfd = fp.MinFlowDecomp(
            G,
            flow_attr="flow",
            elements_to_ignore=edges_to_ignore
        )
        mfd.solve()
        
        # Should still solve (paths may not fully explain flow)
        assert mfd.is_solved()
        
        solution = mfd.get_solution()
        assert len(solution["paths"]) > 0
        # Paths should still be valid s-t paths
        for path in solution["paths"]:
            assert path[0] == "s"
            assert path[-1] == "t"
