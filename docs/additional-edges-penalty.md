# Additional Edges and Usage Penalty

This page describes how `additional_edges` and `additional_edges_lambda` work in:

- [`kLeastAbsErrors`](k-least-absolute-errors.md) (acyclic model)
- [`kLeastAbsErrorsCycles`](k-least-absolute-errors-cycles.md) (general directed graph model)
- [`kMinPathError`](k-min-path-error.md) (acyclic model)
- [`kMinPathErrorCycles`](k-min-path-error-cycles.md) (general directed graph model)

## 1. Why Use Additional Edges?

Sometimes the observed graph may be missing a small number of edges that would improve decomposition quality.
You can add such candidate edges via `additional_edges`.

Because these edges are not in the original data, the model penalizes their usage in the objective with `additional_edges_lambda`.

In node-weighted mode, the additional edges are specified in terms of the original graph and are then expanded internally in the node-expanded graph.

## 2. Objective Pattern

The objective is the sum of:

1. The original objective of the problem.
2. A one-time penalty per additional edge used by at least one path/walk.

For the least-absolute-errors models, the original objective is the sum of scaled edge errors.

For the k-minimum-path-error models, the original objective is the sum of path or walk slacks.

## 3. Validation Rules

For each edge in `additional_edges`:

- It must be a 2-tuple `(u, v)`.
- Both endpoints must be nodes already present in the graph.
- The edge must not already exist in the original graph.

And:

- `additional_edges_lambda` can be either:
	- `None` (automatic graph-dependent default), or
	- a numeric non-negative constant.

When `additional_edges_lambda=None`, the models use:

$$
\lambda_{\mathrm{add}} = \max\left(1.0,\ 0.1 \cdot \frac{Q_{0.9}(\text{flow values})}{\text{graph width}}\right),
$$

where $Q_{0.9}$ is the 90th percentile of edge flows (or node flows in node-weighted mode).

## 4. Practical Guidance

- By default, pass `additional_edges_lambda=None` to use the automatic graph-dependent value above.
- You can still pass an explicit constant if you want stronger/weaker penalization.
- Increase it if the solver overuses additional edges.
- Decrease it if additional edges are plausible and needed to reduce large errors.
