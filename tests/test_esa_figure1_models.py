import flowpaths as fp
import networkx as nx
import pytest

@pytest.fixture
def esa_figure1():
    """Create the DAG from ESA Figure 1 (first TikZ picture)."""
    #                    s
    #                  /   \
    #                 3     4
    #                /       \
    #               a         h
    #             2/ \1     2/ \2
    #             b-> c <-1 k  i->j
    #              \  |     ^   |\ \
    #               2 4     |   |1 2
    #                \ |    |   v  \
    #                  d    k'  l-> p ->3 q
    #                  |4         1    / \
    #                  e                1  2
    #                1/ \3             r-> u ->3 t
    #                f-> g ->4 t
    #
    # Edge set follows the TikZ exactly; flows are assigned to satisfy
    # conservation at every internal node.
    G = nx.DiGraph()

    # Upper part
    G.add_edge("s", "a", flow=3)
    G.add_edge("a", "b", flow=2)
    G.add_edge("a", "c", flow=1)
    G.add_edge("b", "c", flow=2)
    G.add_edge("c", "d", flow=14)
    G.add_edge("d", "e", flow=14)
    G.add_edge("e", "f", flow=1)
    G.add_edge("e", "g", flow=13)
    G.add_edge("f", "g", flow=1)
    G.add_edge("g", "t", flow=14)

    # Lower part
    G.add_edge("s", "h", flow=14)
    G.add_edge("h", "i", flow=2)
    G.add_edge("i", "j", flow=2)
    G.add_edge("h", "j", flow=12)
    G.add_edge("j", "l", flow=1)
    G.add_edge("j", "p", flow=2)
    G.add_edge("l", "p", flow=1)
    G.add_edge("p", "q", flow=3)
    G.add_edge("q", "r", flow=1)
    G.add_edge("q", "u", flow=2)
    G.add_edge("r", "u", flow=1)
    G.add_edge("u", "t", flow=3)

    # Connector
    G.add_edge("j", "k'", flow=11)
    G.add_edge("k'", "k", flow=11)
    G.add_edge("k", "c", flow=11)

    return G

# python -m pytest tests/test_esa_figure1_models.py::test_esa_figure1_min_flow_decomp -s
def test_esa_figure1_min_flow_decomp(esa_figure1):
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    
    optimization_options = {
        "optimize_with_greedy": False,
        "optimize_with_flow_safe_paths": True,
        "optimize_with_safe_sequences": True,
        "optimize_with_safe_zero_edges": True,
    }
    mfd = fp.MinFlowDecomp(
        esa_figure1, 
        flow_attr="flow", 
        optimization_options=optimization_options)
    mfd.solve()

    assert mfd.is_solved()
    assert mfd.is_valid_solution()

    solution = mfd.get_solution()
    for i, (path, weight) in enumerate(zip(solution["paths"], solution["weights"]), start=1):
        print(f"path {i}: weight={weight}, nodes={path}")
    print(mfd.solve_statistics)
    
    assert "paths" in solution
    assert "weights" in solution
    assert len(solution["paths"]) == len(solution["weights"])
    assert sum(solution["weights"]) == 17

    assert mfd.solve_statistics["edge_variables=1"] == 37
    assert mfd.solve_statistics["edge_variables=0"] == 78


def test_esa_figure1_kflow_decomp(esa_figure1):
    kfd = fp.kFlowDecomp(esa_figure1, k=7, flow_attr="flow")
    kfd.solve()

    assert kfd.is_solved()
    assert kfd.is_valid_solution()

    solution = kfd.get_solution()
    assert len(solution["paths"]) == 7
    assert sum(solution["weights"]) == 17


def test_esa_figure1_kmin_path_error(esa_figure1):
    kpe = fp.kMinPathError(esa_figure1, k=5, flow_attr="flow")
    kpe.solve()

    assert kpe.is_solved()

    solution = kpe.get_solution()
    assert len(solution["paths"]) == 5
    assert len(solution["weights"]) == 5
    assert all(w >= 0 for w in solution["weights"])


def test_esa_figure1_kleast_abs_errors(esa_figure1):
    klae = fp.kLeastAbsErrors(esa_figure1, k=4, flow_attr="flow")
    klae.solve()

    assert klae.is_solved()

    solution = klae.get_solution()
    assert len(solution["paths"]) == 4
    assert len(solution["weights"]) == 4
    assert all(w >= 0 for w in solution["weights"])


def test_esa_figure1_min_path_cover(esa_figure1):
    mpc = fp.MinPathCover(esa_figure1)
    mpc.solve()

    assert mpc.is_solved()
    assert mpc.is_valid_solution()

    solution = mpc.get_solution()
    assert len(solution["paths"]) > 0

    original_edges = set(esa_figure1.edges())
    covered_edges = set()
    for path in solution["paths"]:
        for i in range(len(path) - 1):
            edge = (path[i], path[i + 1])
            if edge in original_edges:
                covered_edges.add(edge)

    assert original_edges.issubset(covered_edges)
