from pathlib import Path

import flowpaths as fp


DATASET_FOLDER = Path(__file__).resolve().parents[1] / "tests" / "acyclic_graphs" / "SIRV.ONT_R10.real_exp_downsample"
TIME_LIMIT_SECONDS = 10
FIXED_K = None

def run_kmin_path_error_on_intron_graphs(
    dataset_folder: Path,
    time_limit: int | None,
    k: int | None,
):
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )

    graphs = fp.utils.read_intron_graphs(dataset_folder) # all graphs
    # graphs = [fp.utils.read_intron_graph(dataset_folder/ "SIRV6.1.SIRV6")] # for testing with a single graph
    print(f"Loaded {len(graphs)} graph(s) from: {dataset_folder}")
    fp.utils.logger.debug(f"Running with hard-coded settings: time_limit={time_limit}, fixed_k={k}")

    solved = 0
    not_solved = 0

    for graph in graphs:
        graph_id = graph.graph.get("id", "unknown")
        graph_source_folder = Path(graph.graph.get("source_folder", dataset_folder / graph_id))
        graph_source_folder.mkdir(parents=True, exist_ok=True)
        constraints = graph.graph.get("constraints", [])
        additional_edges = graph.graph.get("additional_edges", [])
        groundtruth_paths = graph.graph.get("groundtruth_paths_nodes", [])
        groundtruth_weights = graph.graph.get("groundtruth_weights", [])

        print(
            f"\nGraph {graph_id}: n={graph.number_of_nodes()}, m={graph.number_of_edges()}, "
            f"constraints={len(constraints)}, additional_edges={len(additional_edges)}"
        )
        fp.utils.logger.debug(
            f"Graph {graph_id}: first groundtruth path={groundtruth_paths[0] if len(groundtruth_paths) > 0 else []}, "
            f"groundtruth weights count={len(groundtruth_weights)}"
        )

        original_no_constraints_file = graph_source_folder / f"{graph_id}_original_no_constraints.pdf"
        fp.utils.draw(
            graph,
            filename=str(original_no_constraints_file),
            flow_attr="flow",
            additional_edges=additional_edges,
            draw_options={
                "show_graph_edges": True,
                "show_node_weights": True,
                "show_graph_title": True,
                "show_path_weights": False,
                "show_path_weight_on_first_edge": True,
                "style": "default",
            },
        )
        print(f"  original graph (no constraints) saved to: {original_no_constraints_file}")

        original_with_constraints_file = graph_source_folder / f"{graph_id}_original_with_constraints.pdf"
        fp.utils.draw(
            graph,
            filename=str(original_with_constraints_file),
            flow_attr="flow",
            subpath_constraints=constraints,
            additional_edges=additional_edges,
            draw_options={
                "show_graph_edges": True,
                "show_node_weights": True,
                "show_graph_title": True,
                "show_path_weights": False,
                "show_path_weight_on_first_edge": True,
                "style": "default",
            },
        )
        print(f"  original graph (with constraints) saved to: {original_with_constraints_file}")

        if len(groundtruth_paths) > 0:
            groundtruth_no_constraints_file = graph_source_folder / f"{graph_id}_groundtruth_no_constraints.pdf"
            fp.utils.draw(
                graph,
                filename=str(groundtruth_no_constraints_file),
                flow_attr="flow",
                paths=groundtruth_paths,
                weights=groundtruth_weights,
                additional_edges=additional_edges,
                draw_options={
                    "show_graph_edges": True,
                    "show_node_weights": True,
                    "show_graph_title": True,
                    "show_path_weights": False,
                    "show_path_weight_on_first_edge": True,
                    "style": "default",
                },
            )
            print(f"  groundtruth graph (no constraints) saved to: {groundtruth_no_constraints_file}")
        else:
            print("  skipping groundtruth drawing: no groundtruth paths found")

        model = fp.kMinPathError(
            graph,
            flow_attr="flow",
            flow_attr_origin="node",
            subpath_constraints=constraints,
            additional_edges=additional_edges,
            additional_edges_lambda=None, # use default lambda
            weight_type=int,
            solver_options={"time_limit": time_limit} if time_limit is not None else {},
        )
        fp.utils.logger.debug(
            f"Initialized kMinPathError for {graph_id} with k={model.k}, "
            f"additional_edges={additional_edges}"
        )

        model.solve()
        if model.is_solved():
            solved += 1
            solution = model.get_solution()
            objective = model.get_objective_value()
            print(
                f"  solved: objective={objective}, "
                f"k={model.k}, "
                f"num_paths={len(solution.get('paths', []))}, "
                f"total_weight={sum(solution.get('weights', []))}"
            )

            output_file = graph_source_folder / f"{graph_id}_kmin_path_error_solved.pdf"
            fp.utils.draw(
                graph,
                filename=str(output_file),
                flow_attr="flow",
                paths=solution.get("paths", []),
                weights=solution.get("weights", []),
                additional_edges=additional_edges,
                draw_options={
                    "show_graph_edges": True,
                    "show_node_weights": True,
                    "show_graph_title": True,
                    "show_path_weights": False,
                    "show_path_weight_on_first_edge": True,
                    "style": "default",
                },
            )
            print(f"  drawing saved to: {output_file}")
        else:
            not_solved += 1
            print(f"  not solved (k={model.k})")
        print(model.solve_statistics)
        fp.utils.logger.debug(f"Solve statistics for {graph_id}: {model.solve_statistics}")

    print(f"\nDone. solved={solved}, not_solved={not_solved}")


def main():
    dataset_folder = DATASET_FOLDER
    if not dataset_folder.is_dir():
        raise ValueError(f"Dataset folder not found: {dataset_folder}")

    fp.utils.configure_logging(level=fp.utils.logging.INFO, log_to_console=True)
    run_kmin_path_error_on_intron_graphs(
        dataset_folder,
        time_limit=TIME_LIMIT_SECONDS,
        k=FIXED_K,
    )


if __name__ == "__main__":
    main()
