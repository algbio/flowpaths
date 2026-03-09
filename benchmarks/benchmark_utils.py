"""
Utilities for benchmarking flowpaths solvers.

This module provides common functionality for:
- Loading graphs from dataset files
- Running solvers with different configurations
- Saving and loading results
- Computing statistics and generating tables
"""

import gzip
import json
import time
import zipfile
import io
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
import flowpaths as fp
from flowpaths.utils import graphutils


@dataclass
class BenchmarkResult:
    """Store results from a single graph instance benchmark."""
    graph_id: str
    graph_width: int
    num_nodes: int
    num_edges: int
    optimization_config: str  # Identifier for the optimization configuration
    solve_time: float  # Total solve time in seconds
    is_solved: bool
    model_status: str
    num_paths: Optional[int] = None  # Number of paths in solution (if applicable)
    solve_statistics: Optional[Dict] = None  # Full solve_statistics dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        import copy
        data = asdict(self)
        
        # Recursively convert sets to lists for JSON serialization
        def convert_sets(obj):
            if isinstance(obj, dict):
                return {k: convert_sets(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_sets(item) for item in obj]
            elif isinstance(obj, set):
                return list(obj)
            else:
                return obj
        
        # Deep copy to avoid modifying original data
        data = convert_sets(data)
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BenchmarkResult':
        """Create from dictionary (for loading from JSON)."""
        return cls(**data)


class DatasetLoader:
    """Load graphs from dataset files (.grp, .graph, .grp.gz, .graph.gz, .zip)."""
    
    def __init__(self, dataset_path: str):
        """
        Initialize dataset loader.
        
        Parameters
        ----------
        dataset_path : str
            Path to the dataset file (.grp, .graph, .grp.gz, .graph.gz, or .zip)
        """
        self.dataset_path = Path(dataset_path)
        # Clean up dataset name from various suffixes
        name = self.dataset_path.stem
        name = name.replace('_unzipped', '')
        if name.endswith('.grp'):
            name = name[:-4]
        elif name.endswith('.graph'):
            name = name[:-6]
        self.dataset_name = name
        
    def load_graphs(self) -> List:
        """
        Load all graphs from the dataset file.
        
        Supports:
        - Plain text files: .grp, .graph
        - Gzip compressed: .grp.gz, .graph.gz
        - Zip archives: .zip (reads first file in archive)
        
        Compressed files are read directly without extracting to disk.
        
        Returns
        -------
        list
            List of NetworkX DiGraph objects
        """
        suffix = self.dataset_path.suffix.lower()
        
        if suffix == '.gz':
            # Read gzip file directly without extracting to disk
            with gzip.open(self.dataset_path, 'rt', encoding='utf-8') as f:
                lines = f.readlines()
            return self._parse_graphs_from_lines(lines)
            
        elif suffix == '.zip':
            # Read first file in zip archive without extracting to disk
            with zipfile.ZipFile(self.dataset_path, 'r') as zip_file:
                # Get the first file in the archive
                names = zip_file.namelist()
                if not names:
                    raise ValueError(f"Zip file {self.dataset_path} is empty")
                
                # Read the first file
                with zip_file.open(names[0], 'r') as f:
                    # Read as text
                    content = f.read().decode('utf-8')
                    lines = content.splitlines(keepends=True)
                    
            return self._parse_graphs_from_lines(lines)
            
        else:
            # Plain text file (.grp or .graph)
            return graphutils.read_graphs(str(self.dataset_path))
    
    def _parse_graphs_from_lines(self, lines: List[str]) -> List:
        """
        Parse graphs from a list of lines (used for in-memory processing).
        
        This replicates the logic from graphutils.read_graphs but works
        on already-loaded lines instead of reading from a file.
        
        Parameters
        ----------
        lines : list of str
            Lines containing graph data
            
        Returns
        -------
        list
            List of NetworkX DiGraph objects
        """
        graphs = []
        n_lines = len(lines)
        i = 0

        # Iterate through lines, capturing blocks that start with '#' header lines
        while i < n_lines:
            # Move to the start of the next graph header
            while i < n_lines and not lines[i].lstrip().startswith('#'):
                i += 1
            if i >= n_lines:
                break

            start = i

            # Consume all consecutive header lines for this graph
            while i < n_lines and lines[i].lstrip().startswith('#'):
                i += 1

            # Advance until the next header line (start of next graph) or EOF
            j = i
            while j < n_lines and not lines[j].lstrip().startswith('#'):
                j += 1

            # Parse this graph block
            graphs.append(graphutils.read_graph(lines[start:j]))
            i = j

        return graphs
    
    def get_dataset_name(self) -> str:
        """Get the name of the dataset."""
        return self.dataset_name


class WidthFilter:
    """Filter and group graphs by width intervals."""
    
    def __init__(self, min_width: Optional[int] = None, max_width: Optional[int] = None):
        """
        Initialize width filter.
        
        Parameters
        ----------
        min_width : int, optional
            Minimum width to include (inclusive)
        max_width : int, optional
            Maximum width to include (inclusive)
        """
        self.min_width = min_width
        self.max_width = max_width
    
    def filter_graph(self, graph) -> bool:
        """
        Check if a graph passes the width filter.
        
        Parameters
        ----------
        graph : nx.DiGraph
            Graph to check
            
        Returns
        -------
        bool
            True if graph should be included
        """
        width = graph.graph.get('w', None)
        if width is None:
            # Compute width if not already stored
            width = fp.stDiGraph(graph).get_width()
            graph.graph['w'] = width
        
        if self.min_width is not None and width < self.min_width:
            return False
        if self.max_width is not None and width > self.max_width:
            return False
        return True
    
    def get_width(self, graph) -> int:
        """Get the width of a graph (compute if needed)."""
        width = graph.graph.get('w', None)
        if width is None:
            width = fp.stDiGraph(graph).get_width()
            graph.graph['w'] = width
        return width
    
    @staticmethod
    def create_width_intervals(interval_size: int = 3) -> List[Tuple[int, int]]:
        """
        Create a function that assigns width intervals.
        
        Parameters
        ----------
        interval_size : int
            Size of each width interval
            
        Returns
        -------
        function
            Function that takes a width and returns (interval_start, interval_end)
        """
        def assign_interval(width: int) -> Tuple[int, int]:
            interval_start = ((width - 1) // interval_size) * interval_size + 1
            interval_end = interval_start + interval_size - 1
            return (interval_start, interval_end)
        return assign_interval


class BenchmarkRunner:
    """Run benchmarks with different optimization configurations."""
    
    def __init__(
        self,
        model_class,
        flow_attr: str = 'flow',
        weight_type = float,
        additional_model_params: Optional[Dict] = None
    ):
        """
        Initialize benchmark runner.
        
        Parameters
        ----------
        model_class : class
            The flowpaths model class to benchmark (e.g., fp.MinFlowDecomp)
        flow_attr : str
            Name of the flow attribute on edges
        weight_type : type
            Type for weights (int or float)
        additional_model_params : dict, optional
            Additional parameters to pass to the model constructor
        """
        self.model_class = model_class
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.additional_model_params = additional_model_params or {}
    
    def run_single_instance(
        self,
        graph,
        optimization_config_name: str,
        optimization_options: Dict,
        solver_options: Optional[Dict] = None
    ) -> BenchmarkResult:
        """
        Run a single benchmark instance.
        
        Parameters
        ----------
        graph : nx.DiGraph
            Graph to solve
        optimization_config_name : str
            Name/identifier for this optimization configuration
        optimization_options : dict
            Optimization options to pass to the model
        solver_options : dict, optional
            Solver options to pass to the model
            
        Returns
        -------
        BenchmarkResult
            Results from this benchmark run
        """
        # Get graph properties
        graph_id = graph.graph.get('id', 'unknown')
        width = graph.graph.get('w', None)
        if width is None:
            width = fp.stDiGraph(graph).get_width()
            graph.graph['w'] = width
        
        # Default solver options
        if solver_options is None:
            solver_options = {
                'threads': 1,
                'log_to_console': 'false',
            }
        
        # Create and solve model
        start_time = time.perf_counter()
        try:
            model = self.model_class(
                G=graph,
                flow_attr=self.flow_attr,
                weight_type=self.weight_type,
                optimization_options=optimization_options,
                solver_options=solver_options,
                **self.additional_model_params
            )
            model.solve()
            solve_time = time.perf_counter() - start_time
            
            is_solved = model.is_solved()
            model_status = model.get_model_status() if hasattr(model, 'get_model_status') else 'unknown'
            
            # Get solution info if solved
            num_paths = None
            if is_solved:
                solution = model.get_solution()
                num_paths = len(solution.get('paths', []))
            
            # Get solve_statistics if available
            solve_statistics = None
            if hasattr(model, 'solve_statistics'):
                solve_statistics = model.solve_statistics
            
        except Exception as e:
            solve_time = time.perf_counter() - start_time
            is_solved = False
            model_status = f'error: {str(e)}'
            num_paths = None
            solve_statistics = None
        
        return BenchmarkResult(
            graph_id=graph_id,
            graph_width=width,
            num_nodes=graph.number_of_nodes(),
            num_edges=graph.number_of_edges(),
            optimization_config=optimization_config_name,
            solve_time=solve_time,
            is_solved=is_solved,
            model_status=model_status,
            num_paths=num_paths,
            solve_statistics=solve_statistics
        )


class ResultsManager:
    """Manage saving and loading benchmark results."""
    
    def __init__(self, results_dir: str = 'results'):
        """
        Initialize results manager.
        
        Parameters
        ----------
        results_dir : str
            Directory to store results files
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
    
    def save_results(
        self,
        dataset_name: str,
        model_name: str,
        results: List[BenchmarkResult]
    ):
        """
        Save benchmark results to JSON file.
        
        Parameters
        ----------
        dataset_name : str
            Name of the dataset
        model_name : str
            Name of the model
        results : list of BenchmarkResult
            Results to save
        """
        filename = self.results_dir / f'{model_name}_{dataset_name}.json'

        # Make overwrite behavior explicit for repeat benchmark runs.
        if filename.exists():
            filename.unlink()
        
        data = {
            'dataset': dataset_name,
            'model': model_name,
            'num_results': len(results),
            'results': [r.to_dict() for r in results]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Results saved to: {filename}")
    
    def load_results(self, dataset_name: str, model_name: str) -> Optional[List[BenchmarkResult]]:
        """
        Load benchmark results from JSON file.
        
        Parameters
        ----------
        dataset_name : str
            Name of the dataset
        model_name : str
            Name of the model
            
        Returns
        -------
        list of BenchmarkResult or None
            Loaded results, or None if file doesn't exist
        """
        filename = self.results_dir / f'{model_name}_{dataset_name}.json'
        
        if not filename.exists():
            return None
        
        with open(filename, 'r') as f:
            data = json.load(f)
        
        return [BenchmarkResult.from_dict(r) for r in data['results']]
    
    def get_all_result_files(self) -> List[Path]:
        """Get all result JSON files in the results directory."""
        return list(self.results_dir.glob('*.json'))


def print_progress(current: int, total: int, message: str = ""):
    """Print progress bar."""
    percent = (current / total) * 100
    bar_length = 50
    filled = int(bar_length * current / total)
    bar = '█' * filled + '-' * (bar_length - filled)
    print(f'\r[{bar}] {percent:.1f}% ({current}/{total}) {message}', end='', flush=True)
    if current == total:
        print()  # New line when complete
