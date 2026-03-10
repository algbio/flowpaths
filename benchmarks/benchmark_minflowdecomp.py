"""
Benchmark script for MinFlowDecomp model.

This script runs the MinFlowDecomp solver on specified datasets with
different optimization configurations and saves the results.

Usage:
    python benchmark_minflowdecomp.py --datasets Mouse.PacBio_reads_unzipped.grp
    python benchmark_minflowdecomp.py --all-datasets --min-width 5 --max-width 20
"""

import argparse
from pathlib import Path
import sys

# Add parent directory to path to import benchmark_utils
sys.path.insert(0, str(Path(__file__).parent))

import flowpaths as fp
from benchmark_utils import (
    DatasetLoader,
    WidthFilter,
    BenchmarkRunner,
    ResultsManager,
    print_progress
)


# Model configuration
MODEL_NAME = 'MinFlowDecomp'
FLOW_ATTR = 'flow'
WEIGHT_TYPE = int  


# Optimization configurations to benchmark
OPTIMIZATION_CONFIGS = {
    'no_optimizations': {
        'optimize_with_greedy': False,
        'optimize_with_flow_safe_paths': False,
        'optimize_with_safe_paths': False,
        'optimize_with_safe_sequences': False,
        'optimize_with_safe_zero_edges': False,
        'optimize_with_symmetry_breaking': False,
    },
    'default': {
        # Default settings
    },
    'no_optimizations': {
        'optimize_with_greedy': False,
        'optimize_with_flow_safe_paths': False,
        'optimize_with_safe_paths': False,
        'optimize_with_safe_sequences': True,
        'optimize_with_safe_zero_edges': False,
        'optimize_with_symmetry_breaking': False,
    },
    'given_weights+min_gen_set+safety': {
        'optimize_with_greedy': False,
        'optimize_with_flow_safe_paths': False,
        'optimize_with_safe_paths': False,
        'optimize_with_safe_sequences': True,
        'optimize_with_safe_zero_edges': True,
        'optimize_with_symmetry_breaking': True,
        'use_min_gen_set_lowerbound': True,
        'optimize_with_given_weights': True,
    },
    'given_weights+min_gen_set+safety+partition_constraints': {
        'optimize_with_greedy': False,
        'optimize_with_flow_safe_paths': False,
        'optimize_with_safe_paths': False,
        'optimize_with_safe_sequences': True,
        'optimize_with_safe_zero_edges': True,
        'optimize_with_symmetry_breaking': True,
        'use_min_gen_set_lowerbound': True,
        'optimize_with_given_weights': True,
        'use_min_gen_set_lowerbound_partition_constraints': True,
    },
    'greedy+min_gen_set': {
        'optimize_with_greedy': True,
        'optimize_with_flow_safe_paths': False,
        'optimize_with_safe_paths': False,
        'optimize_with_safe_sequences': True,
        'optimize_with_safe_zero_edges': True,
        'optimize_with_symmetry_breaking': True,
        'use_min_gen_set_lowerbound': True,
        'use_min_gen_set_lowerbound_partition_constraints': True,
    },
}

# Solver options
SOLVER_OPTIONS = {
    'threads': 1,
    'log_to_console': 'false',
}


def get_flow_conserving_graph(graph, flow_attr: str, solver_options: dict):
    """
    Return a graph that satisfies flow conservation.

    If flow conservation is violated, run MinErrorFlow once to correct the graph.
    The caller is responsible for any timing; this function does not contribute
    to benchmark solve_time because it is executed outside benchmark runs.
    """
    if fp.utils.check_flow_conservation(graph, flow_attr):
        return graph, False

    correction_model = fp.MinErrorFlow(
        G=graph,
        flow_attr=flow_attr,
        weight_type=WEIGHT_TYPE,
        solver_options=solver_options,
    )
    correction_model.solve()
    if not correction_model.is_solved():
        raise RuntimeError(
            f"MinErrorFlow failed on graph id={graph.graph.get('id', 'unknown')} "
            f"with status {correction_model.solver.get_model_status()}"
        )

    corrected_graph = correction_model.get_corrected_graph()
    return corrected_graph, True


def run_benchmarks(
    dataset_paths: list,
    min_width: int = None,
    max_width: int = None,
    results_dir: str = 'results',
    time_limit: int = 300,
):
    """
    Run benchmarks on specified datasets.
    
    Parameters
    ----------
    dataset_paths : list of str
        Paths to dataset files
    min_width : int, optional
        Minimum width to include
    max_width : int, optional
        Maximum width to include
    results_dir : str
        Directory to save results
    time_limit : int
        Solver time limit per instance in seconds
    """
    solver_options = {
        **SOLVER_OPTIONS,
        'time_limit': time_limit,
    }

    # Initialize components
    width_filter = WidthFilter(min_width, max_width)
    runner = BenchmarkRunner(
        model_class=fp.MinFlowDecomp,
        flow_attr=FLOW_ATTR,
        weight_type=WEIGHT_TYPE
    )
    results_manager = ResultsManager(results_dir)
    
    # Process each dataset
    for dataset_path in dataset_paths:
        print(f"\n{'='*80}")
        print(f"Processing dataset: {dataset_path}")
        print('='*80)
        
        # Load dataset
        loader = DatasetLoader(dataset_path)
        dataset_name = loader.get_dataset_name()
        
        print(f"Loading graphs from {dataset_path}...")
        graphs = loader.load_graphs()
        print(f"Loaded {len(graphs)} graphs")
        
        # Filter by width
        filtered_graphs = []
        for graph in graphs:
            if width_filter.filter_graph(graph):
                filtered_graphs.append(graph)
        
        print(f"After width filtering ({min_width}-{max_width}): {len(filtered_graphs)} graphs")
        
        if not filtered_graphs:
            print("No graphs to process after filtering.")
            continue
        
        # Run benchmarks
        all_results = []
        total_runs = len(filtered_graphs) * len(OPTIMIZATION_CONFIGS)
        current_run = 0
        
        for graph in filtered_graphs:
            graph_id = graph.graph.get('id', 'unknown')
            width = width_filter.get_width(graph)
            
            for config_name, optimization_options in OPTIMIZATION_CONFIGS.items():
                current_run += 1
                
                # Run benchmark
                result = runner.run_single_instance(
                    graph=graph,
                    optimization_config_name=config_name,
                    optimization_options=optimization_options,
                    solver_options=solver_options
                )
                
                all_results.append(result)
                
                # Print progress
                status = "✓" if result.is_solved else "✗"
                message = f"{status} {graph_id} (w={width}) [{config_name}]: {result.solve_time:.3f}s"
                print_progress(current_run, total_runs, message)
        
        # Save results
        print(f"\nSaving results for {dataset_name}...")
        results_manager.save_results(dataset_name, MODEL_NAME, all_results)
        
        # Print summary
        solved_count = sum(1 for r in all_results if r.is_solved)
        total_count = len(all_results)
        print(f"Summary: {solved_count}/{total_count} instances solved")
        print(f"Average time: {sum(r.solve_time for r in all_results) / len(all_results):.3f}s")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description=f'Benchmark {MODEL_NAME} on datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run on specific dataset
  python benchmark_minflowdecomp.py --datasets datasets/esa2025/Mouse.PacBio_reads_unzipped.grp
  
  # Run on all datasets in folder with width filtering
  python benchmark_minflowdecomp.py --all-datasets --min-width 5 --max-width 20
  
  # Specify custom results directory
  python benchmark_minflowdecomp.py --datasets data.grp --results-dir my_results
        """
    )
    
    parser.add_argument(
        '--datasets',
        nargs='+',
        help='Paths to dataset files (.grp, .graph, or compressed: .gz, .zip)'
    )
    parser.add_argument(
        '--all-datasets',
        action='store_true',
        help='Run on all datasets in datasets/esa2025/ folder'
    )
    parser.add_argument(
        '--min-width',
        type=int,
        help='Minimum graph width to include (inclusive)'
    )
    parser.add_argument(
        '--max-width',
        type=int,
        help='Maximum graph width to include (inclusive)'
    )
    parser.add_argument(
        '--results-dir',
        default='results',
        help='Directory to save results (default: results)'
    )
    parser.add_argument(
        '--time-limit',
        type=int,
        default=300,
        help='Solver time limit per instance in seconds (default: 300)'
    )
    
    args = parser.parse_args()
    
    # Determine dataset paths
    dataset_paths = []
    
    if args.all_datasets:
        datasets_dir = Path(__file__).parent / 'datasets' / 'esa2025'
        if datasets_dir.exists():
            # Find all graph dataset files
            dataset_paths.extend(datasets_dir.glob('*.grp'))
            dataset_paths.extend(datasets_dir.glob('*.grp.gz'))
            dataset_paths.extend(datasets_dir.glob('*.graph'))
            dataset_paths.extend(datasets_dir.glob('*.graph.gz'))
            dataset_paths.extend(datasets_dir.glob('*.zip'))
        else:
            print(f"Error: Dataset directory not found: {datasets_dir}")
            sys.exit(1)
    elif args.datasets:
        dataset_paths = [Path(p) for p in args.datasets]
    else:
        print("Error: Must specify either --datasets or --all-datasets")
        parser.print_help()
        sys.exit(1)
    
    # Validate paths
    valid_paths = []
    for path in dataset_paths:
        if path.exists():
            valid_paths.append(str(path))
        else:
            print(f"Warning: File not found: {path}")
    
    if not valid_paths:
        print("Error: No valid dataset files found")
        sys.exit(1)
    
    # Run benchmarks
    print(f"Benchmark configuration:")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Datasets: {len(valid_paths)} file(s)")
    print(f"  Width range: {args.min_width}-{args.max_width}")
    print(f"  Optimization configs: {len(OPTIMIZATION_CONFIGS)}")
    print(f"  Time limit: {args.time_limit}s")
    print(f"  Results directory: {args.results_dir}")
    
    run_benchmarks(
        dataset_paths=valid_paths,
        min_width=args.min_width,
        max_width=args.max_width,
        results_dir=args.results_dir,
        time_limit=args.time_limit,
    )
    
    print("\n" + "="*80)
    print("Benchmarking complete!")
    print(f"View results with: python aggregate_results.py {MODEL_NAME}")
    print("="*80)


if __name__ == '__main__':
    main()
