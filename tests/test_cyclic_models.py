import pytest
import itertools
import networkx as nx
import flowpaths as fp


class TestCyclicModels:
    """Test suite for cyclic graph decomposition models."""
    
    @pytest.fixture
    def simple_cycle_graph(self):
        """Create a simple graph with cycles for testing."""
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=3)
        G.add_edge("a", "b", flow=2)  # part of cycle
        G.add_edge("b", "a", flow=2)  # part of cycle
        G.add_edge("a", "t", flow=3)
        return G
    
    @pytest.fixture
    def complex_cycle_graph(self):
        """Create a more complex graph with multiple cycles."""
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=4)
        G.add_edge("a", "b", flow=9)
        G.add_edge("b", "c", flow=6)
        G.add_edge("c", "a", flow=6)  # cycle: a->b->c->a
        G.add_edge("b", "d", flow=3)
        G.add_edge("d", "b", flow=1)  # cycle: b->d->b
        G.add_edge("c", "t", flow=1)
        G.add_edge("d", "t", flow=2)
        return G

    def test_min_flow_decomp_cycles_basic(self, simple_cycle_graph):
        """Test MinFlowDecompCycles with basic cycle graph."""
        mfd = fp.MinFlowDecompCycles(simple_cycle_graph, flow_attr="flow")
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
        
        solution = mfd.get_solution()
        assert "walks" in solution
        assert "weights" in solution
        assert len(solution["walks"]) > 0
        assert len(solution["weights"]) == len(solution["walks"])
        
        # Verify weights are positive
        assert all(w > 0 for w in solution["weights"])
    
    def test_kflow_decomp_cycles(self, simple_cycle_graph):
        """Test kFlowDecompCycles with various k values."""
        for k in [2, 3]:
            kfd = fp.kFlowDecompCycles(simple_cycle_graph, k=k, flow_attr="flow")
            kfd.solve()
            
            assert kfd.is_solved()
            assert kfd.is_valid_solution()
            
            solution = kfd.get_solution()
            assert len(solution["walks"]) == k
            assert len(solution["weights"]) == k
    
    def test_kleast_abs_errors_cycles(self, complex_cycle_graph):
        """Test kLeastAbsErrorsCycles functionality."""
        k = 3
        lae = fp.kLeastAbsErrorsCycles(
            complex_cycle_graph, 
            k=k, 
            flow_attr="flow",
            weight_type=int
        )
        lae.solve()
        
        assert lae.is_solved()
        assert lae.is_valid_solution()
        
        solution = lae.get_solution()
        assert len(solution["walks"]) == k
        
        # Check objective value is reasonable
        obj_value = lae.get_objective_value()
        assert obj_value >= 0
    
    def test_kmin_path_error_cycles(self, complex_cycle_graph):
        """Test kMinPathErrorCycles functionality."""
        k = 2
        mpe = fp.kMinPathErrorCycles(
            complex_cycle_graph,
            k=k,
            flow_attr="flow",
            weight_type=int
        )
        mpe.solve()
        
        assert mpe.is_solved()
        assert mpe.is_valid_solution()
        
        solution = mpe.get_solution()
        assert len(solution["walks"]) == k
        assert "slacks" in solution
    
    def test_cycles_with_subset_constraints(self, complex_cycle_graph):
        """Test cyclic models with subset constraints."""
        # Create subset constraints
        subset_constraints = [
            [("a", "b"), ("b", "c")],  # edges that should appear together
            [("b", "d")]  # single edge constraint
        ]
        
        k = 3
        mpe = fp.kMinPathErrorCycles(
            complex_cycle_graph,
            k=k,
            flow_attr="flow",
            subset_constraints=subset_constraints,
            weight_type=int
        )
        mpe.solve()
        
        assert mpe.is_solved()
        assert mpe.is_valid_solution()
    
    def test_cycles_with_solver_options(self, simple_cycle_graph):
        """Test cyclic models with different solver options."""
        solvers = ["highs"]
        try:
            import gurobipy
            solvers.append("gurobi")
        except ImportError:
            pass
        
        for solver in solvers:
            mfd = fp.MinFlowDecompCycles(
                simple_cycle_graph,
                flow_attr="flow",
                solver_options={"external_solver": solver}
            )
            mfd.solve()
            
            assert mfd.is_solved()
            assert mfd.is_valid_solution()
    
    def test_cycles_optimization_flags(self, simple_cycle_graph):
        """Test cyclic models with various optimization flags."""
        optimization_options = [
            {"optimize_with_safe_sequences": True},
            {"optimize_with_safe_sequences": False},
            {"allow_empty_walks": True},
            {"allow_empty_walks": False},
        ]
        
        for opt in optimization_options:
            # Add trusted_edges_for_safety when using safety optimizations
            if opt.get("optimize_with_safe_sequences", False):
                opt["trusted_edges_for_safety"] = set(simple_cycle_graph.edges())
            
            mfd = fp.MinFlowDecompCycles(
                simple_cycle_graph,
                flow_attr="flow",
                optimization_options=opt
            )
            mfd.solve()
            
            assert mfd.is_solved()
    
    def test_empty_walks_allowed(self):
        """Test allowing empty walks."""
        G = nx.DiGraph()
        G.add_edge("s", "a", flow=1)
        G.add_edge("a", "t", flow=1)
        
        mfd = fp.MinFlowDecompCycles(
            G,
            flow_attr="flow",
        )
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
    
    def test_cycles_weight_types(self, simple_cycle_graph):
        """Test cyclic models with different weight types."""
        weight_types = [int, float]
        
        for wtype in weight_types:
            lae = fp.kLeastAbsErrorsCycles(
                simple_cycle_graph,
                k=2,
                flow_attr="flow",
                weight_type=wtype
            )
            lae.solve()
            
            assert lae.is_solved()
            assert lae.is_valid_solution()
            
            solution = lae.get_solution()
            # Check that weights match expected type
            for weight in solution["weights"]:
                assert isinstance(weight, wtype)
    
    def test_cycles_invalid_inputs(self):
        """Test error handling with invalid inputs."""
        G = nx.DiGraph()
        G.add_edge("a", "b", flow=1)
        
        # Test with k=0
        with pytest.raises(ValueError):
            fp.kFlowDecompCycles(G, k=0, flow_attr="flow")
                
        # Test with invalid subset_constraints_coverage
        with pytest.raises(ValueError):
            fp.kMinPathErrorCycles(
                G, 
                k=1, 
                flow_attr="flow", 
                subset_constraints=[("a", "b")],
                subset_constraints_coverage=0
            )
    
    @pytest.mark.parametrize("graph_file", [
        "gt3.kmer15.(130000.132000).V23.E32.cyc100.graph",
        "gt4.kmer15.(2898000.2900000).V29.E40.cyc448.graph",
    ])
    def test_cycles_real_data(self, graph_file):
        """Test cyclic models on real cyclic graph data."""
        import os
        graph_path = f"tests/cyclic_graphs/{graph_file}"
        
        if not os.path.exists(graph_path):
            pytest.skip(f"Graph file {graph_file} not found")
        
        graphs = fp.graphutils.read_graphs(graph_path)
        if not graphs:
            pytest.skip(f"No graphs found in {graph_file}")
        
        graph = graphs[0]  # Test first graph
        
        # Test MinFlowDecompCycles
        mfd = fp.MinFlowDecompCycles(graph, flow_attr="flow")
        mfd.solve()
        
        assert mfd.is_solved()
        assert mfd.is_valid_solution()
        
        # Test kLeastAbsErrorsCycles with small k
        k = min(3, len(list(graph.edges())))
        if k > 0:
            lae = fp.kLeastAbsErrorsCycles(
                graph, 
                k=k, 
                flow_attr="flow",
                solver_options={"time_limit": 300},  # Limit time for larger graphs
            )
            lae.solve()
            
            assert lae.is_solved()

    @pytest.mark.parametrize("graph_file", [
        "gt5.kmer15.(92000.94000).V76.E104.cyc64.graph",
    ])
    def test_cycles_no_solve_call(self, graph_file):
        """Test no solve call."""
        import os
        graph_path = f"tests/cyclic_graphs/{graph_file}"
        
        if not os.path.exists(graph_path):
            pytest.skip(f"Graph file {graph_file} not found")
        
        graphs = fp.graphutils.read_graphs(graph_path)
        if not graphs:
            pytest.skip(f"No graphs found in {graph_file}")

        graph = graphs[0]  # Test first graph

        # Test MinFlowDecompCycles
        mfd = fp.MinFlowDecompCycles(
            graph, 
            flow_attr="flow",
            solver_options={
                "time_limit": 1, # Very small time limit
                "external_solver": "gurobi"},  
            optimization_options={"optimize_with_safe_sequences": False}
        )
        assert not mfd.is_solved()

        with pytest.raises(Exception):
            mfd.is_valid_solution()

        with pytest.raises(Exception):
            mfd.get_solution()
