from __future__ import annotations

import flowpaths as fp
from multiprocessing import cpu_count

# --- hardcoded settings ---
NGRAPH = "tests/acyclic_graphs/multitrans.82.ngraph"
GRAPH_INDEX = 0
TIME_LIMIT = 10.0
THREADS = max(1, min(8, cpu_count()))
DRAW_INPUT_FILENAME = "multitrans82_input.pdf"
DRAW_SOLUTION_FILENAME = "multitrans82_solution.pdf"

# Gurobi strategy presets that preserve exact optimality.
# Choose one of: "balanced", "bound", "feasible_first", "memory_safe",
# "prove_optimality", "hybrid_incumbent", "hybrid_bound".
GUROBI_STRATEGY = "bound"
GUROBI_STRATEGY_PRESETS = {
    "balanced": {
        "MIPFocus": 0,
        "Presolve": 2,
        "Cuts": 2,
        "Symmetry": 2,
    },
    "bound": {
        "MIPFocus": 3,
        "Presolve": 2,
        "Cuts": 2,
        "Symmetry": 2,
        "Heuristics": 0.05,
    },
    "feasible_first": {
        "MIPFocus": 1,
        "Presolve": 2,
        "Cuts": 1,
        "Symmetry": 2,
        "Heuristics": 0.2,
    },
    "memory_safe": {
        "MIPFocus": 3,
        "Presolve": 2,
        "Cuts": 1,
        "Symmetry": 2,
        "NodefileStart": 0.5,
    },
    "prove_optimality": {
        "MIPFocus": 3,
        "Presolve": 2,
        "Cuts": 3,
        "Symmetry": 2,
        "Heuristics": 0.01,
        "NodefileStart": 0.5,
        "NoRelHeurTime": 0,
    },
    "hybrid_incumbent": {
        "MIPFocus": 2,
        "Presolve": 2,
        "Cuts": 2,
        "Symmetry": 2,
        "Heuristics": 0.12,
        "NodefileStart": 0.5,
    },
    "hybrid_bound": {
        "MIPFocus": 3,
        "Presolve": 2,
        "Cuts": 3,
        "Symmetry": 2,
        "Heuristics": 0.03,
        "NodefileStart": 0.5,
    },
}
# --------------------------


def main():
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )

    graphs = fp.graphutils.read_ngraphs(NGRAPH)
    graph = graphs[GRAPH_INDEX]
    graph_id = graph.graph.get("id", f"graph[{GRAPH_INDEX}]")
    constraints = graph.graph.get("constraints", [])

    print(f"Loaded graph: {graph_id}")
    print(
        f"nodes={graph.number_of_nodes()} edges={graph.number_of_edges()} constraints={len(constraints)}"
    )

    # Draw the input graph (node weights, no edge weights)
    fp.graphutils.draw(
        G=graph,
        filename=DRAW_INPUT_FILENAME,
        flow_attr="flow",
        subpath_constraints=constraints,
        draw_options={
            "show_graph_edges": True,
            "show_edge_weights": False,
            "show_node_weights": True,
            "show_graph_title": True,
        },
    )
    print(f"Input graph drawn to {DRAW_INPUT_FILENAME}")

    gurobi_params = GUROBI_STRATEGY_PRESETS[GUROBI_STRATEGY]
    print(
        "Solver setup: "
        f"strategy={GUROBI_STRATEGY} threads={THREADS} time_limit={TIME_LIMIT}s"
    )

    model = fp.MinPathsMinDiscordantNodes(
        G=graph,
        flow_attr="flow",
        weight_type=int,
        subsequence_constraints=constraints,
        flow_values_divisor=2.0,
        round_flow_values_to_int=True,
        max_num_paths=max(1, graph.number_of_nodes()),
        time_limit=TIME_LIMIT,
        solver_options={
            "external_solver": "gurobi",
            "time_limit": TIME_LIMIT,
            "threads": THREADS,
            "log_to_console": "true",
            "gurobi_params": gurobi_params,
        },
    )

    try:
        solved = model.solve()
    except ValueError as exc:
        print(f"Solver failed before optimize: {exc}")
        return

    if not solved or not model.is_solved():
        solve_status = None
        if isinstance(model.solve_statistics, dict):
            solve_status = model.solve_statistics.get("solve_status")
        print(f"Model did not solve. solve_status={solve_status}")
        return

    solution = model.get_solution(remove_empty_paths=False)
    paths = solution.get("paths", [])
    weights = solution.get("weights", [])

    print(f"Solved with {len(paths)} paths.")
    for i, (path, weight) in enumerate(zip(paths, weights), start=1):
        print(f"path[{i}] weight={weight}: {path}")

    discordant_nodes = solution.get("discordant_nodes", {})
    nonzero_discordant = {n: v for n, v in discordant_nodes.items() if v != 0}
    print(f"nonzero_discordant_nodes={len(nonzero_discordant)}")
    print(f"is_valid_solution={model.is_valid_solution()}")

    # Draw the solution paths overlaid on the graph
    fp.graphutils.draw(
        G=graph,
        filename=DRAW_SOLUTION_FILENAME,
        flow_attr="flow",
        paths=paths,
        weights=weights,
        subpath_constraints=constraints,
        draw_options={
            "show_graph_edges": True,
            "show_edge_weights": False,
            "show_node_weights": True,
            "show_path_weight_on_first_edge": True,
            "show_graph_title": True,
        },
    )
    print(f"Solution drawn to {DRAW_SOLUTION_FILENAME}")


if __name__ == "__main__":
    main()