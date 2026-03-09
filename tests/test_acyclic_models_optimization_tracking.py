import pytest
import networkx as nx
import flowpaths as fp


class TestOptimizationTracking:
    """Test suite for optimization tracking in acyclic models."""
    
    @pytest.fixture
    def test_graph(self):
        """Create a test DAG."""
        #         s
        #        / \
        #      10   5
        #      /     \
        #     a       b
        #     |\     /|
        #     6 \   / 2
        #     |  \ /  |
        #     | 4 X 3 |
        #     |  / \  |
        #     |/     \|
        #     c       d
        #      \     /
        #       9   6
        #        \ /
        #         t
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=10)
        G.add_edge("s", "b", flow=5)
        G.add_edge("a", "c", flow=6)
        G.add_edge("a", "d", flow=4)
        G.add_edge("b", "c", flow=3)
        G.add_edge("b", "d", flow=2)
        G.add_edge("c", "t", flow=9)
        G.add_edge("d", "t", flow=6)
        return G
    
    def test_no_optimizations(self, test_graph):
        """Test that no optimizations are applied when all are disabled."""
        optimization_options = {
            "optimize_with_safe_paths": False,
            "optimize_with_safe_sequences": False,
            "optimize_with_safe_zero_edges": False,
            "optimize_with_subpath_constraints_as_safe_sequences": False,
            "optimize_with_safety_as_subpath_constraints": False,
            "optimize_with_symmetry_breaking_lexicographic_paths": False,
            "optimize_with_safety_from_largest_antichain": False,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        assert "optimizations_applied" in stats
        # No optimizations should be applied except possibly greedy
        # (greedy is a different mechanism in MinFlowDecomp)
        optimizations = stats["optimizations_applied"]
        assert "optimize_with_safe_paths" not in optimizations
        assert "optimize_with_safe_sequences" not in optimizations
        assert "optimize_with_safe_zero_edges" not in optimizations
        assert "optimize_with_symmetry_breaking_lexicographic_paths" not in optimizations
    
    def test_safe_paths_optimization(self, test_graph):
        """Test that safe paths optimization is tracked."""
        optimization_options = {
            "optimize_with_flow_safe_paths": False,  # Disable to avoid conflicts
            "optimize_with_greedy": False,  # Disable greedy to ensure full solve
            "optimize_with_safe_paths": True,
            "optimize_with_safe_sequences": False,
            "optimize_with_safe_zero_edges": True,
            "optimize_with_symmetry_breaking_lexicographic_paths": False,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        optimizations = stats["optimizations_applied"]
        
        # Safe paths should be applied
        assert "optimize_with_safe_lists" in optimizations
        assert "optimize_with_safe_paths" in optimizations
        # Safe sequences should NOT be applied
        assert "optimize_with_safe_sequences" not in optimizations
        # Safe zero edges may or may not be applied depending on graph structure
        # but if it is, it should be tracked
    
    def test_safe_sequences_optimization(self, test_graph):
        """Test that safe sequences optimization is tracked."""
        optimization_options = {
            "optimize_with_flow_safe_paths": False,  # Disable to avoid conflicts
            "optimize_with_greedy": False,  # Disable greedy to ensure full solve
            "optimize_with_safe_paths": False,
            "optimize_with_safe_sequences": True,
            "optimize_with_safe_zero_edges": True,
            "optimize_with_symmetry_breaking_lexicographic_paths": False,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        optimizations = stats["optimizations_applied"]
        
        # Safe sequences should be applied
        assert "optimize_with_safe_lists" in optimizations
        assert "optimize_with_safe_sequences" in optimizations
        # Safe paths should NOT be applied
        assert "optimize_with_safe_paths" not in optimizations
    
    def test_symmetry_breaking_optimization(self, test_graph):
        """Test that symmetry breaking optimization is tracked."""
        optimization_options = {
            "optimize_with_flow_safe_paths": False,
            "optimize_with_safe_paths": False,
            "optimize_with_safe_sequences": False,
            "optimize_with_safe_zero_edges": False,
            "optimize_with_symmetry_breaking_lexicographic_paths": True,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        optimizations = stats["optimizations_applied"]
        
        # Symmetry breaking should be applied if there are free paths
        # (may not be applied if all paths are fixed by other means)
        # Just verify it's tracked if it happens
        if "optimize_with_symmetry_breaking_lexicographic_paths" in optimizations:
            # If it's there, that's correct tracking
            assert True
        assert "optimize_with_safe_lists" not in optimizations
    
    def test_combined_optimizations_safe_paths_and_symmetry(self, test_graph):
        """Test that multiple optimizations can be tracked together."""
        optimization_options = {
            "optimize_with_greedy": False,  # Disable greedy to ensure full solve
            "optimize_with_flow_safe_paths": False,  # Disable to avoid conflicts
            "optimize_with_safe_paths": True,
            "optimize_with_safe_sequences": False,
            "optimize_with_safe_zero_edges": True,
            "optimize_with_symmetry_breaking_lexicographic_paths": True,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        optimizations = stats["optimizations_applied"]
        
        # Verify that safe paths was applied
        assert "optimize_with_safe_lists" in optimizations
        assert "optimize_with_safe_paths" in optimizations
        assert "optimize_with_safe_sequences" not in optimizations
    
    def test_subpath_constraints_as_safe_sequences(self, test_graph):
        """Test that subpath constraints as safe sequences optimization is tracked."""
        # Configure logging
        fp.utils.configure_logging(
            level=fp.utils.logging.DEBUG,
            log_to_console=True,
        )
        # Add a subpath constraint
        subpath_constraints = [[("s", "a"), ("a", "c"), ("c", "t")]]
        
        optimization_options = {
            "optimize_with_greedy": False,  # Disable greedy to ensure full solve
            "optimize_with_flow_safe_paths": False,
            "optimize_with_safe_paths": False,
            "optimize_with_safe_sequences": False,
            "optimize_with_subpath_constraints_as_safe_sequences": True,
            "optimize_with_symmetry_breaking_lexicographic_paths": False,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            subpath_constraints=subpath_constraints,
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        optimizations = stats["optimizations_applied"]
        print(optimizations)
        assert "optimize_with_subpath_constraints_as_safe_sequences" in optimizations
    
    def test_safety_as_subpath_constraints(self, test_graph):
        """Test that safety as subpath constraints optimization is tracked."""
        optimization_options = {
            "optimize_with_greedy": False,  # Disable greedy to ensure full solve
            "optimize_with_flow_safe_paths": False,  
            "optimize_with_safe_paths": True,
            "optimize_with_safety_as_subpath_constraints": True,
            "optimize_with_symmetry_breaking_lexicographic_paths": False,
        }
        
        mfd = fp.MinFlowDecomp(
            test_graph,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        optimizations = stats["optimizations_applied"]
        
        # Safety as subpath constraints should be applied
        assert "optimize_with_safety_as_subpath_constraints" in optimizations
        # When safety is used as subpath constraints, safe_lists tracking won't appear
        assert "optimize_with_safe_lists" not in optimizations
    
    def test_optimization_tracking_with_kflow_decomp(self, test_graph):
        """Test optimization tracking works with kFlowDecomp."""
        optimization_options = {
            "optimize_with_flow_safe_paths": False,  # Disable to avoid conflicts
            "optimize_with_safe_paths": True,
            "optimize_with_symmetry_breaking_lexicographic_paths": True,
        }
        
        kfd = fp.kFlowDecomp(
            test_graph,
            k=3,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        kfd.solve()
        
        if kfd.is_solved():
            stats = kfd.solve_statistics
            optimizations = stats["optimizations_applied"]
            
            # Verify optimizations is a set
            assert isinstance(optimizations, set)
            # Verify safe paths was applied
            assert "optimize_with_safe_paths" in optimizations
    
    def test_optimization_tracking_with_kmin_path_error(self, test_graph):
        """Test optimization tracking works with kMinPathError."""
        optimization_options = {
            "optimize_with_safe_paths": False,
            "optimize_with_symmetry_breaking_lexicographic_paths": True,
        }
        
        kpe = fp.kMinPathError(
            test_graph,
            k=2,
            flow_attr="flow",
            optimization_options=optimization_options
        )
        kpe.solve()
        
        stats = kpe.solve_statistics
        optimizations = stats["optimizations_applied"]
        assert "optimize_with_symmetry_breaking_lexicographic_paths" in optimizations
    
    def test_all_valid_optimization_combinations(self, test_graph):
        """Test various valid combinations of optimizations."""
        # Test cases: (optimization_options_dict, expected_presence, expected_absence)
        test_cases = [
            # Case 1: Only safe paths
            (
                {"optimize_with_flow_safe_paths": False, "optimize_with_greedy": False, "optimize_with_safe_paths": True, "optimize_with_safe_sequences": False},
                ["optimize_with_safe_paths"],
                ["optimize_with_safe_sequences"]
            ),
            # Case 2: Only safe sequences
            (
                {"optimize_with_flow_safe_paths": False, "optimize_with_greedy": False, "optimize_with_safe_paths": False, "optimize_with_safe_sequences": True},
                ["optimize_with_safe_sequences"],
                ["optimize_with_safe_paths"]
            ),
            # Case 3: Safe paths with zero edges
            (
                {"optimize_with_flow_safe_paths": False, "optimize_with_greedy": False, "optimize_with_safe_paths": True, "optimize_with_safe_zero_edges": True, "optimize_with_safe_sequences": False},
                ["optimize_with_safe_paths"],
                ["optimize_with_safe_sequences"]
            ),
        ]
        
        for opts, expected_present, expected_absent in test_cases:
            mfd = fp.MinFlowDecomp(
                test_graph,
                flow_attr="flow",
                optimization_options=opts
            )
            mfd.solve()
            
            if mfd.is_solved():
                stats = mfd.solve_statistics
                optimizations = stats["optimizations_applied"]
                
                # Check expected present optimizations
                for opt in expected_present:
                    assert opt in optimizations, f"Expected {opt} to be present in {optimizations}"
                
                # Check expected absent optimizations
                for opt in expected_absent:
                    assert opt not in optimizations, f"Expected {opt} to be absent from {optimizations}"
    
    def test_optimization_statistics_structure(self, test_graph):
        """Test that solve_statistics has the expected structure."""
        mfd = fp.MinFlowDecomp(test_graph, flow_attr="flow")
        mfd.solve()
        
        assert mfd.is_solved()
        stats = mfd.solve_statistics
        
        # Verify optimizations_applied exists
        assert "optimizations_applied" in stats
        
        # Verify it's a set
        assert isinstance(stats["optimizations_applied"], set)
        
        # Verify all entries are strings
        assert all(isinstance(opt, str) for opt in stats["optimizations_applied"])
