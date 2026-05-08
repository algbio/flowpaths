# Directed acyclic graphs with global source and global sink

This class is used in [AbstractPathModelDAG](abstract-path-model.md) as a wrapper (with unique global source and unique global sink) to pass the DAG to the ILP models.

!!! info "Width with subpath constraints"

    `stDAG.get_width(...)` supports optional subpath-constraint arguments. When constraints are passed,
    width is computed as the constrained minimum path cover size (via `MinPathCover`) instead of plain antichain width.

::: flowpaths.stdag
    options:
      filters: 
        - "!^_"