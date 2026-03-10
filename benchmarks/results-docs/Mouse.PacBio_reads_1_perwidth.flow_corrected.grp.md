## MinFlowDecomp - Mouse.PacBio_reads_5_perwidth.flow_corrected

Rows show width intervals; `All` aggregates every width interval in the dataset.
Columns: `Width Range`, `# Graphs` (unique graph IDs), `Nodes` and `Edges` as `average (max)` over unique graphs in the row, optimization config timing columns, and `Speedup` (ratio of no_optimizations / default) showing `mean` value with `(count)` when available.

| Width Range | # Graphs | Nodes avg (max) | Edges avg (max) | no_optimizations | default | Speedup |
|---|---|---|---|---|---|---|
| 1-3 | 15 | 14.7 (31) | 13.8 (30) | 0.025s (15) | 0.003s (15) | 5.290x (15) |
| 4-6 | 15 | 38.9 (119) | 39.8 (124) | 18.070s (15, 2 failed) | 0.301s (15) | 39.325x (15) |
| **All** | **30** | **26.8 (119)** | **26.8 (124)** | **9.048s** (30, 2 failed) | **0.152s** (30) | **22.308x** (30) |
