## MinFlowDecomp - Mouse.PacBio_reads_1_perwidth.flow_corrected

Rows show width intervals; `All` aggregates every width interval in the dataset.
Columns: `Width Range`, `# Graphs` (unique graph IDs), `Nodes` and `Edges` as `average (max)` over unique graphs in the row, optimization config timing columns, and `Speedup` (ratio of no_optimizations / default) showing `mean` value with `(count)` when available.

| Width Range | # Graphs | Nodes avg (max) | Edges avg (max) | no_optimizations | default | Speedup | given_weights+min_gen_set+safety | given_weights+min_gen_set+safety+partition_constraints | greedy+min_gen_set |
|---|---|---|---|---|---|---|---|---|---|
| 1-3 | 3 | 8.7 (12) | 7.7 (11) | 0.006s (3) | 0.002s (3) | 3.989x (3) | 0.007s (3) | 0.007s (3) | 0.003s (3) |
| 4-6 | 3 | 34.0 (45) | 34.3 (48) | 0.106s (3) | 0.046s (3) | 3.680x (3) | 0.362s (3) | 0.492s (3) | 0.440s (3) |
| 7-9 | 3 | 50.7 (72) | 49.7 (73) | 40.447s (3, 1 failed) | 40.089s (3, 1 failed) | 4.818x (3) | 41.237s (3, 1 failed) | 199.584s (3) | 199.106s (3) |
| **All** | **9** | **31.1 (72)** | **30.6 (73)** | **13.520s** (9, 1 failed) | **13.379s** (9, 1 failed) | **4.162x** (9) | **13.869s** (9, 1 failed) | **66.694s** (9) | **66.516s** (9) |
