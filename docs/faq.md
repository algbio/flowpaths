# Frequently Asked Questions (FAQ)

This page answers common questions about using the flowpaths package, its models, performance, and troubleshooting. For full guides see the model-specific docs linked throughout.

## What problems does flowpaths solve?

- Minimum Flow Decomposition (MFD) on DAGs and on directed graphs with cycles.
- k-Flow Decomposition, k-Least Absolute Errors, and k-Minimum Path Error.
- Minimum Path Cover, Minimum Generating Set, Minimum Set Cover, and utilities for node-weighted graphs.

See “[Models implemented](index.md)” on the Home page and links in the top navigation.

## How do I install it and what Python versions are supported?

- Install with: `pip install flowpaths`.
- Requires Python >= 3.8. Dependencies include networkx, highspy (HiGHS), graphviz, and numpy (see pyproject/requirements).

## Do I need to install a commercial MILP solver?

- No. By default flowpaths uses the open-source HiGHS solver via highspy.
- If you have Gurobi, install gurobipy and set `solver_options={"external_solver": "gurobi"}` for potential speed-ups. Academic users can obtain a free academic license—see the Gurobi website for details.

## What does a solution look like?

- The models expose the function `get_solution()`, which returns a dict:
  - `paths` (or `walks` for cycle models): list of s–t node lists.
  - `weights`: list of non-negative numbers, one per path/walk.
- Example: `{ 'paths': [['s','b','t'], ['s','a','t']], 'weights': [5, 2] }`.

## Can I use weights/flows on nodes instead of edges?

- Yes. Pass `flow_attr_origin="node"` and set `flow_attr` to the node attribute.
- Internally, node weights are supported via `NodeExpandedDiGraph`.
- See “[Flows/weights on nodes](node-expanded-digraph.md)” for details and examples.

## How do subpath or subset constraints work?

- On DAGs: use subpath constraints, i.e., sequences of edges that must appear in at least one solution path. See “[Subpath constraints](subpath-constraints.md)”.
- On general directed graphs (with cycles): use subset constraints, i.e., sets of edges that must co-occur in at least one solution walk. See “[Subset constraints](subset-constraints.md)”.
- Both support relaxing coverage: fraction of edges to be covered by a solution path/walk.

## My edge weights don’t satisfy flow conservation. What should I use?

- You can first correct the weights to become a flow, see “[Minimum Error Flow](minimum-error-flow.md)”, and then decompose the resulting flow.
- For a more principled approach, you can use the models that handle arbitrary weights:

  - For L1 error on edges: see [k-Least Absolute Errors](k-least-absolute-errors.md) (k-LAE).
  - For robust decomposition with per-path slack: see [k-Minimum Path Error](k-min-path-error.md) (k-MPE).


## How do I choose k?

- If you know k, use the k-model variant.
- If unknown on DAGs, `MinFlowDecomp` finds the minimum k by solving increasing k values starting from a width-based lower bound.
- See “[Optimizing k](numpathsoptimization.md)” (NumPathsOptimization) for routines and tips.
- Finally, some models allow passing no k (or `k = None`), and they set it internally as the minimum number of paths/walks needed to cover all edges of the graph (computed internally by the model).

## What are “safe paths” and “safe sequences” optimizations?

- They shrink the ILP search space by precomputing path fragments guaranteed to be part of any path cover, speeding up solves without losing optimality (under simple assumptions).
- Evidence: large speedups, especially on wide graphs.
  - DAG speedups up to two orders of magnitude for path-finding ILPs in realistic settings [Sena & Tomescu, 2024].
  - For MFD, search-space and dimensionality reductions speed up ILPs up to 34× on hard instances, and even higher on variants [Grigorjew et al., SEA 2024].
- These are turned on by default. You can further configure them with `optimization_options` (see “[Solver options and optimizations](solver-options-optimizations.md)”).

## Which papers back the formulations and performance?

- See “[References](references.md)” for links.

## Why do I get `is_solved() == False`?

- Common causes:
  - Time limit too low. Increase `solver_options["time_limit"]`.
  - Infeasible model (e.g., flow not conserved for MFD on DAGs; incompatible constraints). Check `get_model_status()` and input assumptions.
  - Using additional start/end nodes with `flow_attr_origin='edge'` in cycle models (unsupported in some APIs).

## What about graphs with cycles?

- Use the “with cycles” classes (e.g., `MinFlowDecompCycles`, `kFlowDecompCycles`, `kLeastAbsErrorsCycles`, `kMinPathErrorCycles`). These produce `walks` instead of simple paths.
- Constraints in cyclic models generalize subpath constraints to subset constraints since order can’t be enforced around cycles.

## Are the results exact or heuristic?

- The core models are solved via ILP/MILP and return optimal solutions subject to the model and time limits. If time-limited, `is_solved()` will be false and no solution is returned.

## How do I validate a solution?

- For decomposition models, you can verify: for each edge not ignored, the sum of weights of solution paths/walks using it equals the flow (MFD) or satisfies the model’s error/slack constraints (LAE, MPE, etc.). Some classes expose helpers like `is_valid_solution()`.

## Minimal code examples

- See the main README and the `examples/` directory for runnable scripts, including DAG and cyclic variants, node-weighted graphs, and constraints.
