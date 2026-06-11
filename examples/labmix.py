from pathlib import Path

import flowpaths as fp


# GRAPH_FILE = "tests/cyclic_graphs/gt1.kmer27.(0.10000).V28.E36.mincyc100.perf.graph"
# GRAPH_FILE = "tests/cyclic_graphs/gt2.kmer63.(0.10000).V85.E115.mincyc100.perf.graph"
# GRAPH_FILE = "tests/cyclic_graphs/gt3.kmer63.(0.10000).V157.E230.mincyc100.perf.graph"
# GRAPH_FILE = "tests/cyclic_graphs/gt4.kmer63.(0.10000).V281.E415.mincyc100.perf.graph"
GRAPH_FILE = "tests/cyclic_graphs/gt5.kmer63.(0.10000).V375.E560.mincyc100.perf.graph"


# Configure logging
fp.utils.configure_logging(
    level=fp.utils.logging.DEBUG,
    log_to_console=True,
)

graphs = fp.graphutils.read_graphs(GRAPH_FILE)

assert graphs, f"Expected at least one graph in {GRAPH_FILE}, but found none."
graph = graphs[0]

# model = fp.kLeastAbsErrorsCycles(
model = fp.MinFlowDecompCycles(
    G=graph,
    flow_attr="flow",
    weight_type=int,
    solver_options={
        "external_solver": "highs",
        "time_limit": 3000,
        "log_to_console": False,
    },
    optimization_options={
        "optimize_with_safe_sequences": True,
        "optimize_with_safety_from_largest_antichain": True,
    },
    # trusted_edges_for_safety=graph.edges,
)
model.solve()

assert model.is_solved(), "MinFlowDecompCycles did not solve the instance"
assert model.is_valid_solution(), "Solution should be a valid cyclic flow decomposition"

solution = model.get_solution()
assert "walks" in solution and "weights" in solution
assert len(solution["walks"]) == len(solution["weights"])
assert len(solution["walks"]) > 0

objective_value = model.get_objective_value()
assert objective_value >= 0
