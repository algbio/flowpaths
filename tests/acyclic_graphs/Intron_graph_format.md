## Graph format description

Each folder contains a single per-gene graph with at most 6 files.

### 1. Vertices (nodes)

**`vertices.tsv`** — `vertex_id  type  chr  start  end  weight`

| vertex kind | type column | start, end | weight |
|---|---|---|---|
| super-source (opt-in) | `source` | `*`, `*` | `*` |
| intron | `intron` | `(start, end)` | `clustered_introns[intron]` |
| polyA sink | `polya` | `(pos, pos)` | Σ incoming edge weights |
| read-end sink | `read_end` | `(pos, pos)` | Σ incoming edge weights |
| polyT source | `polyt` | `(pos, pos)` | Σ outgoing edge weights |
| read-start source | `read_start` | `(pos, pos)` | Σ outgoing edge weights |
| super-target (opt-in) | `target` | `*`, `*` | `*` |


### 2. Edges 
**`edges.tsv`** — `u  v` by default.

With the internal
`include_edge_weights=True` flag, a third `weight` column is appended;
values come from `flow.flow_dict`. All real edges (intron → intron,
intron → terminal, starting → intron) carry the populated edge
weight; only the implicit `source → starting` / `terminal → target`
super edges (opt-in via `add_super_source_target=True`) remain as
documented sums.


### 3. Ground truth paths

**`paths.tsv`** 

- `transcript_id  count  count_scaled  status  path  path_simple  missing_vertices  missing_edges`
- `count` is the original (pre-downsampling) ground-truth abundance from
`--ground_truth_counts`. 
- `count_scaled = round(count / gene_info.coverage_scale_factor)` is the expected post-downsampling
load - it matches the observed-read weights elsewhere in the dump
(`vertices.tsv` weights, `read_subpaths.tsv` `read_count`) when
`--max_coverage_small_chr` / `--max_coverage_normal_chr` triggered the
"process 1 read out of every N" path. With no downsampling (scale ==
1, the common case) the two columns are equal. Note: this is the
expected average — the keep-rule is `counter % N == 0`, so per-region
counts can drift by ±1 around the rounded value.

- `status`

| status | meaning                                                                                      |
|---|----------------------------------------------------------------------------------------------|
| `monoexonic` | transcript has no introns — `path` is empty, terminals are skipped, can be ignored           |                                                                                
| `ok` | every threaded intron maps to a graph vertex AND every consecutive pair is an edge the graph |
| `disconnected` | all vertices present, but at least one consecutive pair is not an edge in the graph          |
| `partial` | at least one intron has no matching vertex                                                   |


- `path`: each slot becomes either its integer vertex id or
the gap token `*`, and adjacent tokens are joined by an edge separator
that carries connectivity:

  - `-` (dash): both sides are real vertices and the edge exists in the graph
  - `|` (pipe): both sides are real vertices but no edge is present in the graph
  - `-` (default): used whenever either side is `*` 

So `5-0-1-2|3-4-7` means "low terminal 5 → intron 0 → … → intron 4 →
high terminal 7, with edge 2→3 missing". `*-0-1-2-3-*` means "neither
boundary mapped, the intron chain is fully connected".

- `path_simple`: a comma-separated list of the vertex ids that
actually map to the graph (terminals included when matched) — missing
slots are dropped, no `*`, edge state ignored. 

Counts:
- `missing_vertices` — number of vertices (introns or terminals) with no
  graph vertex
- `missing_edges` — number of consecutive vertex pairs whose edge is not
  in the graph.

Note: only edges through real graph vertices are validated; the
super-source / super-target wiring (when `add_super_source_target=True`)
is not.

### 4. Subpath constraints

**`read_subpaths.tsv`** 

One row per distinct read-supported path (the keys of
`IntronPathStorage.paths`), sorted by descending `read_count`:

- `read_count` — number of reads producing this exact path tuple
- `is_fl` — `1` when the path is full-length (goes from source to targe); 
`0` otherwise (partial paths missing one or both ends)
- `status` / `path` / `path_simple` / `missing_vertices` /
  `missing_edges` — same encoding as `paths.tsv`. Threaded read paths
  are built from real graph vertices, so `partial` should not occur and
  `disconnected` is rare.

### 5. Reference vertices 

**`ref_vertices.tsv` ** :
`kind  ref_start  ref_end  status  vertex_id  graph_start  graph_end`

  - `kind` ∈ `intron` / `starting` / `terminal` (`starting` = low-coord
    boundary matched against polyT / read_start; `terminal` =
    high-coord boundary matched against polyA / read_end)
  - `status` for introns ∈ `in_graph` / `discarded` / `unmapped`; for
    boundaries ∈ `in_graph` / `unmapped`
  - terminal `unmapped` means no graph vertex sits within
    `intron_graph.params.apa_delta` of the annotated boundary —
    nothing synthesized, just recorded as missing
  - `*` for `vertex_id` when unresolved; `*` for `graph_start`/
    `graph_end` on `discarded` introns and `unmapped` boundaries
  
### 6. Reference edges

**`ref_edges.tsv`** : `kind  u_start  u_end  v_start  v_end  status  u_id  v_id`

  - `kind` ∈ `intron` / `starting` / `terminal` (matching the vertex
    kind on the boundary side; `starting` = `low_boundary →
    first_intron`, `terminal` = `last_intron → high_boundary`)
  - `status` ∈ `in_graph` / `missing_edge` / `missing_vertex`; absent
    ids rendered as `*`

Independent of `--ground_truth_counts`: a gene is written iff it has
annotated introns, regardless of whether it appears in the counts TSV.

The `chr` column uses `self.gene_info.chr_id`; for intergenic / novel
gene regions without a `gene_db_list`, the per-gene directory falls back
to `<chr>.region_<start>_<end>/`.
