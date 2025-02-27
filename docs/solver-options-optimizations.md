# Solver options and optimizations

The [AbstractPathModelDAG](abstract-path-model.md) class can receive several options for the Mixed Integer Linear Programming solvers that is uses to solve the problems. 

## 1. MILP solver options

Set this options by passing a dictionary `solver_options`, with the following possible keys, and values:

- `"threads"` (int): Number of threads to use. Defaults to 4.
- `"time_limit"` (int): Time limit for solving in secods. Defaults to 300. 
- `"presolve"` (str): Presolve option. Defaults to `"choose"`.
- `"log_to_console"` (str): Log to console option. Defaults to `"false"`.
- `"external_solver"` (str): External solver to use. Defaults to `"highs"`.

!!! warning "Time limit"
    Large or complex graphs may take more than the default 300 seconds to run. In this case, `your_model.is_solved()` will be `False`. You can also check the model status with `your_model.get_model_status()`. If it equals `"kTimeLimit"`, then you should pass a larger `"time_limit"`.

Example:

``` python
solver_options = {
    "threads": 8,
    "time_limit": 3600,
}

your_model = fp.kMinPathError(
    graph,
    flow_attr="flow",
    num_paths=5,
    solver_options=solver_options,
)
```

## 2. Optimizations

Flowpaths implements several optimizations that reduce the search space for the solution paths, based on the structure of the graph, while guaranteeing exact solutions. A typical user does not need to worry about these. However, they can be changed by passing a dictionary `optimization_options`, with the following possible keys, and values:

- `"optimize_with_safe_paths"` (bool): Whether to optimize with safe paths. Defaults to `True`.
- `"optimize_with_safe_sequences"` (bool): Whether to optimize with safe sequences. Defaults to `False`. At the moment, you cannot set both `"optimize_with_safe_paths"` and `"optimize_with_safe_sequences"`.
- `"optimize_with_safe_zero_edges"` (bool): Whether to optimize with safe zero edges. Defaults to `False`. You cannot set this without setting one of the above.

Example:

``` python
optimization_options = {
    "optimize_with_safe_paths": False,
    "optimize_with_safe_sequences": True
}

your_model = fp.kMinPathError(
    graph,
    flow_attr="flow",
    num_paths=5,
    solver_options=solver_options,
)
```


