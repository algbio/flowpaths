"""
Aggregate and display benchmark results as tables.

This script loads benchmark results from JSON files and generates
tables grouped by dataset and width intervals, with columns for
different optimization configurations.

Supports output formats:
- Markdown (for documentation)
- LaTeX (for papers)
- Console (for quick viewing)
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass
import statistics

from benchmark_utils import BenchmarkResult, ResultsManager


@dataclass
class GroupStats:
    """Statistics for a group of benchmark results."""
    count: int
    mean_time: float
    median_time: float
    min_time: float
    max_time: float
    solved_count: int
    failed_count: int
    
    @classmethod
    def from_results(cls, results: List[BenchmarkResult]) -> 'GroupStats':
        """Compute statistics from a list of results."""
        if not results:
            return cls(0, 0.0, 0.0, 0.0, 0.0, 0, 0)
        
        times = [r.solve_time for r in results]
        solved = sum(1 for r in results if r.is_solved)
        failed = len(results) - solved
        
        return cls(
            count=len(results),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            min_time=min(times),
            max_time=max(times),
            solved_count=solved,
            failed_count=failed
        )


class ResultsAggregator:
    """Aggregate and format benchmark results into tables."""
    
    def __init__(self, results_dir: str = 'results'):
        """
        Initialize aggregator.
        
        Parameters
        ----------
        results_dir : str
            Directory containing result JSON files
        """
        self.manager = ResultsManager(results_dir)

    @staticmethod
    def _get_metric_value(stats: GroupStats, metric: str) -> float:
        """Select the requested timing metric from grouped statistics."""
        if metric == 'mean':
            return stats.mean_time
        if metric == 'median':
            return stats.median_time
        if metric == 'min':
            return stats.min_time
        if metric == 'max':
            return stats.max_time
        return stats.mean_time

    @staticmethod
    def _unique_graph_stats(results: List[BenchmarkResult]) -> Tuple[int, float, int, float, int]:
        """
        Compute per-graph stats using unique graph IDs.

        Returns
        -------
        tuple
            (num_graphs, avg_nodes, max_nodes, avg_edges, max_edges)
        """
        unique_by_id: Dict[str, BenchmarkResult] = {}
        for result in results:
            if result.graph_id not in unique_by_id:
                unique_by_id[result.graph_id] = result

        unique_results = list(unique_by_id.values())
        if not unique_results:
            return 0, 0.0, 0, 0.0, 0

        node_counts = [r.num_nodes for r in unique_results]
        edge_counts = [r.num_edges for r in unique_results]

        return (
            len(unique_results),
            statistics.mean(node_counts),
            max(node_counts),
            statistics.mean(edge_counts),
            max(edge_counts),
        )

    @staticmethod
    def _get_ordered_configs(
        results: List[BenchmarkResult],
        grouped: Dict[Tuple[int, int], Dict[str, List[BenchmarkResult]]],
    ) -> List[str]:
        """
        Get config names in first-seen benchmark order.

        This preserves the order from benchmark scripts (for example,
        OPTIMIZATION_CONFIGS insertion order) instead of alphabetical sorting.
        """
        all_configs = set()
        for interval_data in grouped.values():
            all_configs.update(interval_data.keys())

        ordered_configs: List[str] = []
        seen = set()
        for result in results:
            config = result.optimization_config
            if config in all_configs and config not in seen:
                ordered_configs.append(config)
                seen.add(config)

        # Fallback for any config not seen in result order.
        for config in sorted(all_configs):
            if config not in seen:
                ordered_configs.append(config)

        return ordered_configs

    @staticmethod
    def _compute_speedup_stats(
        results: List[BenchmarkResult],
        grouped: Dict[Tuple[int, int], Dict[str, List[BenchmarkResult]]],
    ) -> Dict[Tuple[int, int], List[float]]:
        """
        Compute speedup (no_optimizations / default) per graph per width interval.

        Returns dict mapping (interval_start, interval_end) -> list of speedup values.
        Uses solve_time for all results (includes timeouts for unsolved).
        Excludes graphs missing either config.
        """
        # Build lookup: graph_id -> {config -> result}
        graph_results: Dict[str, Dict[str, BenchmarkResult]] = defaultdict(dict)
        for result in results:
            graph_results[result.graph_id][result.optimization_config] = result

        # Compute speedups per interval
        speedups_by_interval: Dict[Tuple[int, int], List[float]] = defaultdict(list)

        for interval, config_dict in grouped.items():
            # Collect all graph_ids in this interval
            graph_ids_in_interval = set()
            for config_results in config_dict.values():
                for res in config_results:
                    graph_ids_in_interval.add(res.graph_id)

            # For each graph in interval, compute speedup
            for graph_id in graph_ids_in_interval:
                if (graph_id in graph_results and
                    'no_optimizations' in graph_results[graph_id] and
                    'default' in graph_results[graph_id]):
                    no_opt_time = graph_results[graph_id]['no_optimizations'].solve_time
                    default_time = graph_results[graph_id]['default'].solve_time
                    if default_time > 0:  # Avoid division by zero
                        speedup = no_opt_time / default_time
                        speedups_by_interval[interval].append(speedup)

        return dict(speedups_by_interval)
    
    def load_from_file(self, file_path: str) -> Tuple[str, str, List[BenchmarkResult]]:
        """
        Load results from a specific JSON file.

        Parameters
        ----------
        file_path : str
            Path to the results JSON file

        Returns
        -------
        tuple
            (model_name, dataset_name, list of BenchmarkResult)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Results file not found: {file_path}")

        with open(path, 'r') as f:
            data = json.load(f)

        model_name = data['model']
        dataset_name = data['dataset']
        results = [BenchmarkResult.from_dict(r) for r in data['results']]
        return model_name, dataset_name, results

    def load_model_results(self, model_name: str) -> Dict[str, List[BenchmarkResult]]:
        """
        Load all results for a specific model across all datasets.
        
        Parameters
        ----------
        model_name : str
            Name of the model
            
        Returns
        -------
        dict
            Dictionary mapping dataset_name -> list of results
        """
        results_by_dataset = {}
        
        # Find all result files for this model
        for result_file in self.manager.get_all_result_files():
            if result_file.stem.startswith(model_name + '_'):
                dataset_name = result_file.stem[len(model_name) + 1:]
                results = self.manager.load_results(dataset_name, model_name)
                if results:
                    results_by_dataset[dataset_name] = results
        
        return results_by_dataset
    
    def group_by_width_intervals(
        self,
        results: List[BenchmarkResult],
        interval_size: int = 3
    ) -> Dict[Tuple[int, int], Dict[str, List[BenchmarkResult]]]:
        """
        Group results by width intervals and optimization configs.
        
        Parameters
        ----------
        results : list of BenchmarkResult
            Results to group
        interval_size : int
            Size of each width interval
            
        Returns
        -------
        dict
            Nested dict: (interval_start, interval_end) -> config_name -> [results]
        """
        grouped = defaultdict(lambda: defaultdict(list))
        
        for result in results:
            # Compute interval
            interval_start = ((result.graph_width - 1) // interval_size) * interval_size + 1
            interval_end = interval_start + interval_size - 1
            interval_key = (interval_start, interval_end)
            
            # Group by config
            grouped[interval_key][result.optimization_config].append(result)
        
        return dict(grouped)
    
    def generate_markdown_table(
        self,
        model_name: str,
        dataset_name: str,
        results: List[BenchmarkResult],
        interval_size: int = 3,
        metric: str = 'mean'
    ) -> str:
        """
        Generate a markdown table for a single dataset.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        dataset_name : str
            Name of the dataset
        results : list of BenchmarkResult
            Results to display
        interval_size : int
            Width interval size
        metric : str
            Which metric to display ('mean', 'median', 'min', 'max')
            
        Returns
        -------
        str
            Markdown formatted table
        """
        # Group results
        grouped = self.group_by_width_intervals(results, interval_size)
        
        if not grouped:
            return f"No results for {model_name} on {dataset_name}\n"
        
        # Get config columns in benchmark-defined order.
        configs = self._get_ordered_configs(results, grouped)
        
        # Compute speedups (no_optimizations / default)
        speedups_by_interval = self._compute_speedup_stats(results, grouped)
        
        # Build table
        lines = []
        lines.append(f"## {model_name} - {dataset_name}\n")
        lines.append(
            "Rows show width intervals; `All` aggregates every width interval in the dataset."
        )
        lines.append(
            "Columns: `Width Range`, `# Graphs` (unique graph IDs), "
            "`Nodes` and `Edges` as `average (max)` over unique graphs in the row, "
            "optimization config timing columns, and `Speedup` (ratio of no_optimizations / default) "
            f"showing `{metric}` value with `(count)` when available."
        )
        lines.append("")
        
        # Header with speedup column after "default"
        header_parts = ["Width Range", "# Graphs", "Nodes avg (max)", "Edges avg (max)"]
        for config in configs:
            header_parts.append(config)
            if config == 'default':
                header_parts.append("Speedup")
        header = "| " + " | ".join(header_parts) + " |"
        lines.append(header)
        separator = "|" + "---|" * len(header_parts)
        lines.append(separator)
        
        # Data rows (sorted by interval start)
        for interval in sorted(grouped.keys()):
            interval_start, interval_end = interval
            interval_results = []
            for config_results in grouped[interval].values():
                interval_results.extend(config_results)
            num_graphs, avg_nodes, max_nodes, avg_edges, max_edges = self._unique_graph_stats(interval_results)
            row = (
                f"| {interval_start}-{interval_end} | {num_graphs} | "
                f"{avg_nodes:.1f} ({max_nodes}) | {avg_edges:.1f} ({max_edges}) |"
            )
            
            for config in configs:
                if config in grouped[interval]:
                    stats = GroupStats.from_results(grouped[interval][config])
                    value = self._get_metric_value(stats, metric)
                    
                    # Format with count and solved info
                    if stats.failed_count > 0:
                        cell = f" {value:.3f}s ({stats.count}, {stats.failed_count} failed) |"
                    else:
                        cell = f" {value:.3f}s ({stats.count}) |"
                else:
                    cell = " - |"
                
                row += cell
                
                # Add speedup column after default
                if config == 'default':
                    if interval in speedups_by_interval and speedups_by_interval[interval]:
                        speedup_values = speedups_by_interval[interval]
                        if metric == 'mean':
                            speedup_value = statistics.mean(speedup_values)
                        elif metric == 'median':
                            speedup_value = statistics.median(speedup_values)
                        elif metric == 'min':
                            speedup_value = min(speedup_values)
                        else:  # max
                            speedup_value = max(speedup_values)
                        speedup_cell = f" {speedup_value:.3f}x ({len(speedup_values)}) |"
                    else:
                        speedup_cell = " - |"
                    row += speedup_cell
            
            lines.append(row)

        # Add summary row across all widths
        total_graphs, avg_nodes, max_nodes, avg_edges, max_edges = self._unique_graph_stats(results)
        summary_row = (
            f"| **All** | **{total_graphs}** | **{avg_nodes:.1f} ({max_nodes})** | "
            f"**{avg_edges:.1f} ({max_edges})** |"
        )

        for config in configs:
            config_results = []
            for interval_data in grouped.values():
                if config in interval_data:
                    config_results.extend(interval_data[config])

            if config_results:
                stats = GroupStats.from_results(config_results)
                value = self._get_metric_value(stats, metric)
                if stats.failed_count > 0:
                    cell = f" **{value:.3f}s** ({stats.count}, {stats.failed_count} failed) |"
                else:
                    cell = f" **{value:.3f}s** ({stats.count}) |"
            else:
                cell = " - |"

            summary_row += cell
            
            # Add speedup column after default
            if config == 'default':
                all_speedups = []
                for speedup_list in speedups_by_interval.values():
                    all_speedups.extend(speedup_list)
                if all_speedups:
                    if metric == 'mean':
                        speedup_value = statistics.mean(all_speedups)
                    elif metric == 'median':
                        speedup_value = statistics.median(all_speedups)
                    elif metric == 'min':
                        speedup_value = min(all_speedups)
                    else:  # max
                        speedup_value = max(all_speedups)
                    speedup_cell = f" **{speedup_value:.3f}x** ({len(all_speedups)}) |"
                else:
                    speedup_cell = " - |"
                summary_row += speedup_cell

        lines.append(summary_row)
        
        lines.append("")  # Empty line after table
        return "\n".join(lines)
    
    def generate_latex_table(
        self,
        model_name: str,
        dataset_name: str,
        results: List[BenchmarkResult],
        interval_size: int = 3,
        metric: str = 'mean'
    ) -> str:
        """
        Generate a LaTeX table for a single dataset.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        dataset_name : str
            Name of the dataset
        results : list of BenchmarkResult
            Results to display
        interval_size : int
            Width interval size
        metric : str
            Which metric to display ('mean', 'median', 'min', 'max')
            
        Returns
        -------
        str
            LaTeX formatted table
        """
        # Group results
        grouped = self.group_by_width_intervals(results, interval_size)
        
        if not grouped:
            return f"% No results for {model_name} on {dataset_name}\n"
        
        # Get config columns in benchmark-defined order.
        configs = self._get_ordered_configs(results, grouped)
        
        # Compute speedups (no_optimizations / default)
        speedups_by_interval = self._compute_speedup_stats(results, grouped)
        
        # Build table
        lines = []
        lines.append("% " + f"{model_name} - {dataset_name}")
        lines.append("\\begin{table}[h]")
        lines.append("\\centering")
        # Count columns: 4 (range, graphs, nodes, edges) + len(configs) + 1 (speedup)
        num_cols = 4 + len(configs) + 1
        lines.append("\\begin{tabular}{" + "l" + "r" * (num_cols - 1) + "}")
        lines.append("\\toprule")
        
        # Header with speedup after default
        header_parts = ["Width Range", "\\# Graphs", "Nodes avg (max)", "Edges avg (max)"]
        for config in configs:
            header_parts.append(config)
            if config == 'default':
                header_parts.append("Speedup")
        header = " & ".join(header_parts) + " \\\\"
        lines.append(header)
        lines.append("\\midrule")
        
        # Data rows
        for interval in sorted(grouped.keys()):
            interval_start, interval_end = interval
            
            interval_results = []
            for config_results in grouped[interval].values():
                interval_results.extend(config_results)
            num_graphs, avg_nodes, max_nodes, avg_edges, max_edges = self._unique_graph_stats(interval_results)

            row = (
                f"{interval_start}--{interval_end} & {num_graphs} & "
                f"{avg_nodes:.1f} ({max_nodes}) & {avg_edges:.1f} ({max_edges})"
            )
            
            for config in configs:
                if config in grouped[interval]:
                    stats = GroupStats.from_results(grouped[interval][config])
                    
                    value = self._get_metric_value(stats, metric)
                    
                    cell = f" & {value:.3f}"
                else:
                    cell = " & ---"
                
                row += cell
                
                # Add speedup column after default
                if config == 'default':
                    if interval in speedups_by_interval and speedups_by_interval[interval]:
                        speedup_values = speedups_by_interval[interval]
                        if metric == 'mean':
                            speedup_value = statistics.mean(speedup_values)
                        elif metric == 'median':
                            speedup_value = statistics.median(speedup_values)
                        elif metric == 'min':
                            speedup_value = min(speedup_values)
                        else:  # max
                            speedup_value = max(speedup_values)
                        speedup_cell = f" & {speedup_value:.3f}x"
                    else:
                        speedup_cell = " & ---"
                    row += speedup_cell
            
            row += " \\\\"
            lines.append(row)
        
        # Add summary row for all widths
        total_graphs, avg_nodes, max_nodes, avg_edges, max_edges = self._unique_graph_stats(results)
        summary_row = (
            "\\midrule\n"
            f"All & {total_graphs} & {avg_nodes:.1f} ({max_nodes}) & {avg_edges:.1f} ({max_edges})"
        )
        
        for config in configs:
            # Collect all results for this config across all intervals
            config_results = []
            for interval_data in grouped.values():
                if config in interval_data:
                    config_results.extend(interval_data[config])
            
            if config_results:
                stats = GroupStats.from_results(config_results)
                
                value = self._get_metric_value(stats, metric)
                
                cell = f" & {value:.3f}"
            else:
                cell = " & ---"
            
            summary_row += cell
            
            # Add speedup column after default
            if config == 'default':
                all_speedups = []
                for speedup_list in speedups_by_interval.values():
                    all_speedups.extend(speedup_list)
                if all_speedups:
                    if metric == 'mean':
                        speedup_value = statistics.mean(all_speedups)
                    elif metric == 'median':
                        speedup_value = statistics.median(all_speedups)
                    elif metric == 'min':
                        speedup_value = min(all_speedups)
                    else:  # max
                        speedup_value = max(all_speedups)
                    speedup_cell = f" & {speedup_value:.3f}x"
                else:
                    speedup_cell = " & ---"
                summary_row += speedup_cell
        
        summary_row += " \\\\"
        lines.append(summary_row)
        
        lines.append("\\bottomrule")
        lines.append("\\end{tabular}")
        lines.append(
            f"\\caption{{{model_name} on {dataset_name}. Rows represent width intervals, "
            "with an All row aggregating all widths. \\# Graphs counts unique graph IDs. "
            "Nodes avg (max) and Edges avg (max) are computed over unique graphs in the row. "
            f"Optimization columns report {metric} solve time in seconds.}}"
        )
        lines.append(f"\\label{{tab:{model_name.lower()}_{dataset_name.lower()}}}")
        lines.append("\\end{table}")
        lines.append("")
        
        return "\n".join(lines)
    
    def print_console_table(
        self,
        model_name: str,
        dataset_name: str,
        results: List[BenchmarkResult],
        interval_size: int = 3,
        metric: str = 'mean'
    ):
        """
        Print a formatted table to console.
        
        Parameters
        ----------
        model_name : str
            Name of the model
        dataset_name : str
            Name of the dataset
        results : list of BenchmarkResult
            Results to display
        interval_size : int
            Width interval size
        metric : str
            Which metric to display ('mean', 'median', 'min', 'max')
        """
        print(f"\n{'='*80}")
        print(f"{model_name} - {dataset_name}")
        print('='*80)
        
        # Group results
        grouped = self.group_by_width_intervals(results, interval_size)
        
        if not grouped:
            print(f"No results found.")
            return
        
        # Get config columns in benchmark-defined order.
        configs = self._get_ordered_configs(results, grouped)
        
        # Compute speedups (no_optimizations / default)
        speedups_by_interval = self._compute_speedup_stats(results, grouped)
        
        # Determine column widths
        width_col = 12
        graphs_col = 10
        nodes_col = 17
        edges_col = 17
        config_cols = [max(len(c), 12) for c in configs]
        speedup_col = 12  # For speedup column after default
        
        # Header
        header = (
            "Width Range".ljust(width_col)
            + " | "
            + "# Graphs".ljust(graphs_col)
            + " | "
            + "Nodes avg(max)".ljust(nodes_col)
            + " | "
            + "Edges avg(max)".ljust(edges_col)
            + " | "
        )
        for i, config in enumerate(configs):
            header += config.ljust(config_cols[i]) + " | "
            if config == 'default':
                header += "Speedup".ljust(speedup_col) + " | "
        print(header)
        print("-" * len(header))
        
        # Data rows
        for interval in sorted(grouped.keys()):
            interval_start, interval_end = interval
            
            interval_results = []
            for config_results in grouped[interval].values():
                interval_results.extend(config_results)
            num_graphs, avg_nodes, max_nodes, avg_edges, max_edges = self._unique_graph_stats(interval_results)
            
            row = (
                f"{interval_start}-{interval_end}".ljust(width_col)
                + " | "
                + str(num_graphs).ljust(graphs_col)
                + " | "
                + f"{avg_nodes:.1f} ({max_nodes})".ljust(nodes_col)
                + " | "
                + f"{avg_edges:.1f} ({max_edges})".ljust(edges_col)
                + " | "
            )
            
            for i, config in enumerate(configs):
                if config in grouped[interval]:
                    stats = GroupStats.from_results(grouped[interval][config])
                    
                    value = self._get_metric_value(stats, metric)
                    
                    cell = f"{value:.3f}s"
                    if stats.failed_count > 0:
                        cell += f" ({stats.failed_count}F)"
                else:
                    cell = "-"
                
                row += cell.ljust(config_cols[i]) + " | "
                
                # Add speedup column after default
                if config == 'default':
                    if interval in speedups_by_interval and speedups_by_interval[interval]:
                        speedup_values = speedups_by_interval[interval]
                        if metric == 'mean':
                            speedup_value = statistics.mean(speedup_values)
                        elif metric == 'median':
                            speedup_value = statistics.median(speedup_values)
                        elif metric == 'min':
                            speedup_value = min(speedup_values)
                        else:  # max
                            speedup_value = max(speedup_values)
                        speedup_cell = f"{speedup_value:.3f}x"
                    else:
                        speedup_cell = "-"
                    row += speedup_cell.ljust(speedup_col) + " | "
            
            print(row)
        
        # Add summary row for all widths
        print("-" * len(header))
        total_graphs, avg_nodes, max_nodes, avg_edges, max_edges = self._unique_graph_stats(results)
        summary_row = (
            "All".ljust(width_col)
            + " | "
            + str(total_graphs).ljust(graphs_col)
            + " | "
            + f"{avg_nodes:.1f} ({max_nodes})".ljust(nodes_col)
            + " | "
            + f"{avg_edges:.1f} ({max_edges})".ljust(edges_col)
            + " | "
        )
        
        for i, config in enumerate(configs):
            # Collect all results for this config across all intervals
            config_results = []
            for interval_data in grouped.values():
                if config in interval_data:
                    config_results.extend(interval_data[config])
            
            if config_results:
                stats = GroupStats.from_results(config_results)
                
                value = self._get_metric_value(stats, metric)
                
                cell = f"{value:.3f}s"
                if stats.failed_count > 0:
                    cell += f" ({stats.failed_count}F)"
            else:
                cell = "-"
            
            summary_row += cell.ljust(config_cols[i]) + " | "
            
            # Add speedup column after default
            if config == 'default':
                all_speedups = []
                for speedup_list in speedups_by_interval.values():
                    all_speedups.extend(speedup_list)
                if all_speedups:
                    if metric == 'mean':
                        speedup_value = statistics.mean(all_speedups)
                    elif metric == 'median':
                        speedup_value = statistics.median(all_speedups)
                    elif metric == 'min':
                        speedup_value = min(all_speedups)
                    else:  # max
                        speedup_value = max(all_speedups)
                    speedup_cell = f"{speedup_value:.3f}x"
                else:
                    speedup_cell = "-"
                summary_row += speedup_cell.ljust(speedup_col) + " | "
        
        print(summary_row)
        print()


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Aggregate and display benchmark results',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'model',
        nargs='?',
        help='Model name (e.g., MinFlowDecomp). Required unless --results-file is given.'
    )
    parser.add_argument(
        '--results-file',
        help='Path to a specific results JSON file. When provided, a table is generated '
             'from that file only and --results-dir / model are ignored.'
    )
    parser.add_argument(
        '--results-dir',
        default='results',
        help='Directory containing result files (default: results)'
    )
    parser.add_argument(
        '--format',
        choices=['markdown', 'latex', 'console'],
        default='console',
        help='Output format (default: console)'
    )
    parser.add_argument(
        '--metric',
        choices=['mean', 'median', 'min', 'max'],
        default='mean',
        help='Metric to display (default: mean)'
    )
    parser.add_argument(
        '--interval-size',
        type=int,
        default=3,
        help='Width interval size (default: 3)'
    )
    parser.add_argument(
        '--output',
        help='Output file (optional, for markdown/latex)'
    )
    
    args = parser.parse_args()
    
    # Load results
    aggregator = ResultsAggregator(args.results_dir)

    if args.results_file:
        # Load from a specific JSON file
        model_name, dataset_name, results = aggregator.load_from_file(args.results_file)
        results_by_dataset = {dataset_name: results}
        effective_model = model_name
    else:
        if not args.model:
            parser.error("model is required when --results-file is not provided")
        results_by_dataset = aggregator.load_model_results(args.model)
        effective_model = args.model
    
    if not results_by_dataset:
        print(f"No results found")
        return
    
    # Generate output
    output_lines = []
    
    for dataset_name, results in sorted(results_by_dataset.items()):
        if args.format == 'markdown':
            table = aggregator.generate_markdown_table(
                effective_model, dataset_name, results, args.interval_size, args.metric
            )
            output_lines.append(table)
        elif args.format == 'latex':
            table = aggregator.generate_latex_table(
                effective_model, dataset_name, results, args.interval_size, args.metric
            )
            output_lines.append(table)
        else:  # console
            aggregator.print_console_table(
                effective_model, dataset_name, results, args.interval_size, args.metric
            )
    
    # Write to file if specified, or default to results directory
    if args.format != 'console':
        if args.output:
            output_path = Path(args.output)
        else:
            # Default to results directory with model-based filename
            output_dir = Path(args.results_dir)
            output_dir.mkdir(exist_ok=True)
            ext = 'md' if args.format == 'markdown' else 'tex'
            output_path = output_dir / f"{effective_model}.{ext}"
        
        if output_lines:
            # Make overwrite behavior explicit for generated markdown/latex exports.
            if output_path.exists():
                output_path.unlink()

            with open(output_path, 'w') as f:
                f.write('\n'.join(output_lines))
            print(f"\nOutput written to: {output_path}")


if __name__ == '__main__':
    main()
