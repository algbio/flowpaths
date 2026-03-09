## MinFlowDecomp - Mouse.PacBio_reads_50.flow_corrected

Rows show width intervals; `All` aggregates every width interval in the dataset.
Columns: `Width Range`, `# Graphs` (unique graph IDs), `Nodes` and `Edges` as `average (max)` over unique graphs in the row, optimization config timing columns, and `Speedup` (ratio of no_optimizations / default) showing `mean` value with `(count)` when available.

| Width Range | # Graphs | Nodes avg (max) | Edges avg (max) | no_optimizations | default | Speedup |
|---|---|---|---|---|---|---|
| 1-3 | 45 | 12.9 (50) | 12.0 (51) | 0.030s (45) | 0.006s (45) | 4.093x (45) |
| 4-6 | 5 | 25.8 (33) | 26.0 (31) | 12.186s (5) | 0.048s (5) | 68.715x (5) |
| **All** | **50** | **14.2 (50)** | **13.4 (51)** | **1.246s** (50) | **0.011s** (50) | **10.556x** (50) |
