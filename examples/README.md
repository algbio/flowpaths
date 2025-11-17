# Examples of using the _flowpaths_ package

This folder contains example implementations demonstrating the various solvers and features of the flowpaths package.

## Prerequisites

Before running the examples, you need to install the flowpaths package.

### Install from PyPI

```bash
pip install flowpaths
```

### Install from Source (for development)

From the repository root:

```bash
pip install -e .
```

Or for development with all dependencies:

```bash
pip install -e ".[dev]"
```

## Running Examples

All example files can be run from the command line. From the repository root:

```bash
python examples/min_flow_decomp.py
python examples/min_path_error.py
# ... or any other example file
```

**Note:** On some systems (particularly macOS and Linux with multiple Python versions), you may need to use `python3` instead of `python`:

```bash
python3 examples/min_flow_decomp.py
```

This is typically the case when:
- Python 2 is still installed as the default `python` command
- Your system has both Python 2 and Python 3, with `python` pointing to Python 2
- You're on a recent macOS or Linux distribution that doesn't include a `python` command (only `python3`)

To check which Python version is used by the `python` command, run:

```bash
python --version   # or python3 --version
```

You can also run all examples at once, from the repository root, using:

```bash
bash examples/runall.sh
```

If `runall.sh` fails, you may need to edit it to use `python3` instead of `python`.

## Examples for DAG (Acyclic) Graphs

These examples work with directed acyclic graphs (DAGs) and decompose flows into weighted paths.

### Flow Decomposition

- [**min_flow_decomp.py**](min_flow_decomp.py) - Basic usage of the Minimum Flow Decomposition solver to find the minimum number of weighted paths
- [**min_flow_decomp_automatic.py**](min_flow_decomp_automatic.py) - Using `NumPathsOptimization` to automatically find the minimum number of paths needed
- [**min_flow_decomp_subpaths.py**](min_flow_decomp_subpaths.py) - Setting subpath constraints to require certain edges appear in the solution
- [**mfd_demo.py**](mfd_demo.py) - Comprehensive demo showing various optimization options for MFD with file input

### Path Error Minimization

- [**min_path_error.py**](min_path_error.py) - Basic usage of $k$-Minimum Path Error solver to minimize path errors with a fixed number of paths
- [**min_path_error_iterative.py**](min_path_error_iterative.py) - Iteratively solving MPE with increasing $k$ using `NumPathsOptimization`
- [**min_path_error_ignore_edges.py**](min_path_error_ignore_edges.py) - Excluding specific edges from error calculation using `elements_to_ignore`
- [**min_path_error_extension.py**](min_path_error_extension.py) - Using edge lengths in path error calculation
- [**min_path_error_additional_starts.py**](min_path_error_additional_starts.py) - Using `additional_starts` and `additional_ends` for node-weighted graphs

### Other DAG Solvers

- [**least_abs_errors.py**](least_abs_errors.py) - Basic usage of $k$-Least Absolute Errors solver to minimize sum of absolute errors
- [**min_error_flow.py**](min_error_flow.py) - Minimum Error Flow solver for finding minimal flow corrections
- [**min_path_cover.py**](min_path_cover.py) - Minimum Path Cover solver to cover all edges with minimum paths
- [**min_set_cover.py**](min_set_cover.py) - Minimum Set Cover problem (selects minimum-weight subsets to cover universe)
- [**min_gen_set.py**](min_gen_set.py) - Minimum Generating Set solver with partition constraints

### Node-Weighted Graphs

- [**node_weights_mfd.py**](node_weights_mfd.py) - MFD on node-weighted graphs using `NodeExpandedDiGraph`
- [**node_weights_flow_correction.py**](node_weights_flow_correction.py) - Flow correction for node-weighted graphs
- [**internal_node_weights.py**](internal_node_weights.py) - Comprehensive examples of decomposition models on node-weighted graphs

### Extending the Package

- [**inexact_flow_solver.py**](inexact_flow_solver.py) - Custom solver example using `AbstractPathModelDAG` to decompose inexact flows (interval flows)

## Examples for General Graphs (with Cycles)

These examples work with general directed graphs that may contain cycles and decompose flows into weighted walks (paths that can revisit nodes/edges).

### Flow Decomposition with Cycles

- [**min_flow_decomp_cycles.py**](min_flow_decomp_cycles.py) - Basic Minimum Flow Decomposition on graphs with cycles
- [**mfd_cycles.py**](mfd_cycles.py) - Multiple MFD examples on graphs with cycles
- [**mfd_cycles_mingenset.py**](mfd_cycles_mingenset.py) - MFD with cycles using minimum generating set optimizations
- [**kfd_cycles.py**](kfd_cycles.py) - $k$-Flow Decomposition on graphs with cycles
- [**cycles_demo.py**](cycles_demo.py) - Comprehensive demo of MFD on graphs with cycles, including subset constraints

### Walk Error Minimization

- [**min_path_error_cycles.py**](min_path_error_cycles.py) - $k$-Minimum Path Error solver on graphs with cycles
- [**least_abs_errors_cycles.py**](least_abs_errors_cycles.py) - $k$-Least Absolute Errors solver on graphs with cycles
- [**min_error_flow_cycles.py**](min_error_flow_cycles.py) - Minimum Error Flow on graphs with cycles

### Other Cycle Solvers

- [**min_path_cover_cycles.py**](min_path_cover_cycles.py) - Minimum Path Cover for graphs with cycles
- [**cycles_percentile.py**](cycles_percentile.py) - Using percentile-based trusted edges for safety optimizations
- [**safe_seq_cycles.py**](safe_seq_cycles.py) - Computing safe sequences via dominators on graphs with cycles

## Utility and Advanced Examples

- [**condensation.py**](condensation.py) - Working with strongly connected components and graph condensation
- [**timeout.py**](timeout.py) - Utility for running solvers with time limits using signals/multiprocessing
- [**utils.py**](utils.py) - Helper functions used across examples