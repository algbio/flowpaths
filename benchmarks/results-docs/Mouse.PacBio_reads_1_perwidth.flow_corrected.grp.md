## MinFlowDecomp - Mouse.PacBio_reads_1_perwidth.flow_corrected

Rows show width intervals; `All` aggregates every width interval in the dataset.
Columns: `Width Range`, `# Graphs` (unique graph IDs), `Nodes` and `Edges` as `average (max)` over unique graphs in the row, optimization config timing columns, and `Speedup` (ratio of no_optimizations / default) showing `mean` value with `(count)` when available.

| Width Range | # Graphs | Nodes avg (max) | Edges avg (max) | no_optimizations | default | Speedup |
|---|---|---|---|---|---|---|
| 1-3 | 3 | 8.7 (12) | 7.7 (11) | 0.009s (3) | 0.002s (3) | 4.949x (3) |
| 4-6 | 3 | 34.0 (45) | 34.3 (48) | 1.144s (3) | 0.059s (3) | 33.413x (3) |
| **All** | **6** | **21.3 (45)** | **21.0 (48)** | **0.577s** (6) | **0.031s** (6) | **19.181x** (6) |
