# Handling graphs with flows / weights on nodes

If your graph has flow values or weights associated with the nodes, instead of the edges, we provide a simple way to handle them, via the class `NodeExpandedDiGraph`, as described below. 

See [this example](https://github.com/algbio/flowpaths/blob/main/examples/node_weights_flow_correction.py) on how to correct weights on node-weighted graphs, support subpath constraints, and then apply Minimum Flow Decomposition on them.

::: flowpaths.nodeexpandeddigraph
    options:
      filters: 
        - "!^__"