# k-Flow Decomposition in General Graphs

!!! info inline end "See also"

    - [Minimum Flow Decomposition in General Graphs](minimum-flow-decomposition-cycles.md)
    - [k-Flow Decomposition in Acyclic Graphs](k-flow-decomposition.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

This class implements a solver for the problem of decomposing a flow in a general graph possibly with cycles into a given number $k$ of walks (*$k$-flow decomposition*). This problem is a generalization of [Minimum Flow Decomposition](minimum-flow-decomposition-cycles.md), in the sense that we are also given the number of walks that we need to decompose the flow in.


The class [MinFlowDecompCycles](minimum-flow-decomposition-cycles.md) uses this class internally to find the minimum value of $k$ for which a $k$-flow decomposition exists.

!!! warning "Warning"

    Suppose that the number of walks of a minimum flow decomposition is $k^*$. If we ask for a decomposition with $k > k^*$ walks, this class will always return a decomposition with $k$ walks, but some walks might have weight 0.

::: flowpaths.kflowdecompcycles
    options:
      filters: 
        - "!^_"