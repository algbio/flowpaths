## MinFlowDecomp - Mouse.PacBio_reads_1_perwidth.flow_corrected

Rows show width intervals; `All` aggregates every width interval in the dataset.
Columns: `Width Range`, `# Graphs` (unique graph IDs), `Nodes` and `Edges` as `average (max)` over unique graphs in the row, optimization config timing columns, and `Speedup` (ratio of no_optimizations / default) showing `mean` value with `(count)` when available.

| Width Range | # Graphs | Nodes avg (max) | Edges avg (max) | no_optimizations | default | Speedup | given_weights+min_gen_set |
|---|---|---|---|---|---|---|---|
| 1-3 | 3 | 8.7 (12) | 7.7 (11) | 0.008s (3) | 0.001s (3) | 5.132x (3) | 0.009s (3) |
| 4-6 | 3 | 34.0 (45) | 34.3 (48) | 1.072s (3) | 0.053s (3) | 35.128x (3) | 1.201s (3) |
| 7-9 | 3 | 50.7 (72) | 49.7 (73) | 80.144s (3, 2 failed) | 40.090s (3, 1 failed) | 205.160x (3) | 80.187s (3, 2 failed) |
| **All** | **9** | **31.1 (72)** | **30.6 (73)** | **27.075s** (9, 2 failed) | **13.381s** (9, 1 failed) | **81.807x** (9) | **27.133s** (9, 2 failed) |
