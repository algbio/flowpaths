# Handling graphs with flows / weights on nodes

If your graph has flow values or weights associated with the nodes, instead of the edges, the models implemented support such graphs by passing an appropriate parameter, usually `flow_attr_origin = "node"`.

Internally, these are handled via the class `NodeExpandedDiGraph`. See [this example](https://github.com/algbio/flowpaths/blob/main/examples/node_weights_flow_correction.py) on how to support node-weighted graphs without using the internal mechanism, support subpath constraints, and then apply Minimum Flow Decomposition on them. This is useful when implementing new decomposition models, or when using a decomposition model which does not yet support node-weighted graphs.

::: flowpaths.nodeexpandeddigraph
    options:
      filters: 
        - "!^_"