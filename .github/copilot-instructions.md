## AI coding agent guide for this repo (flowpaths)

Purpose: Python package to decompose weighted digraphs into weighted paths/walks via (M)ILP. Default solver is HiGHS (highspy); Gurobi (gurobipy) is optional.

Architecture (what to know first)
- Public API: `flowpaths/__init__.py` re-exports solvers (`MinFlowDecomp`, `kMinPathError`, `kLeastAbsErrors`, `*Cycles`, path-/set-cover, etc.).
- Two model bases: `AbstractPathModelDAG` (acyclic, s–t paths; uses `stDAG`) and `AbstractWalkModelDiGraph` (general digraphs, walks).
- ILP bridge: `utils/solverwrapper.py` unifies HiGHS/Gurobi (vars, constraints, binary×continuous, objective, status, timeouts).
- Node-weighted graphs: `nodeexpandeddigraph.py` handles `flow_attr_origin="node"`, expands/condenses paths; supports `additional_starts/ends`.
- Safety/optimizations live under `flowpaths/utils/*` and are toggled via `optimization_options` in concrete solvers.

How solutions are built (DAG models)
- Create k edge-binary vars x(u,v,i) constrained to be s–t paths; add weights/constraints per objective. Output is `{'paths'|'walks', 'weights'}`; node-origin paths are condensed back.
- `MinFlowDecomp` minimizes number of paths; uses width lower bound, minimal generating set, and subgraph scanning; may accept a greedy solution if it matches a lower bound.

Project-specific conventions
- Options are dicts:
  - `solver_options`: {threads, time_limit, presolve, log_to_console, external_solver: "highs"|"gurobi"}.
  - `optimization_options`: {optimize_with_safe_paths|safe_sequences|safe_zero_edges, use_min_gen_set_lowerbound, use_subgraph_scanning_lowerbound, ...}.
- `weight_type` is int or float; choose deliberately (affects feasibility/integrality). `flow_attr_origin` is "edge" (default) or "node"; only node-mode allows `additional_starts/ends`.
- `elements_to_ignore`: edges (tuples) in edge-mode; node names (strings) in node-mode. `subpath_constraints` support coverage by fraction or length (`length_attr`).

Example (from README/tests)
```python
import flowpaths as fp, networkx as nx
G = nx.DiGraph(); G.add_edge('s','a', flow=2); G.add_edge('a','t', flow=2)
m = fp.MinFlowDecomp(G, flow_attr='flow'); m.solve(); sol = m.get_solution()
```

Developer workflows
- Setup: `pip install -e ".[dev]"`; optional `pip install gurobipy` and set `GRB_LICENSE_FILE`.
- Tests (pytest.ini pins discovery to `tests/`): `pytest -vv -ra --durations=10`; targeted: `pytest -k "min_flow_decomp"`.
- Examples/CLI: `python examples/min_flow_decomp.py`; `python -m flowpaths`.
- Docs: `mkdocs serve` (sources in `docs/`, nav in `mkdocs.yml`).

Pitfalls/checks
- Path models require a DAG; flows must be non-negative and conserve at non s/t nodes. If `is_solved()` is False, check `solver.get_model_status()`; `kTimeLimit` → raise `time_limit`.

Pointers
- Overview/examples: `README.md`, `examples/*.py`.
- Options/optimizations: `docs/solver-options-optimizations.md`; internals: `abstract-path-model.md`, `stdag.md`.
