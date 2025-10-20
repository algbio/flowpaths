# k-Flow Decomposition

!!! info inline end "See also"

    - [Minimum Flow Decomposition](minimum-flow-decomposition.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)
    - [k-Flow Decomposition with cycles](k-flow-decomposition-cycles.md)

This class implements a solver for the problem of decomposing a flow into a given number $k$ of paths (*$k$-flow decomposition*). This problem is a generalization of [Minimum Flow Decomposition](minimum-flow-decomposition.md), in the sense that we are also given the number of paths that we need to decompose the flow in.


The class [MinFlowDecomp](minimum-flow-decomposition.md) uses this class internally to find the minimum value of $k$ for which a $k$-flow decomposition exists.

!!! warning "Warning"

    Suppose that the number of paths of a minimum flow decomposition is $k^*$. If we ask for a decomposition with $k > k^*$ paths, this class will always return a decomposition with $k$ paths, but some paths might have weight 0.

::: flowpaths.kflowdecomp
    options:
      filters: 
        - "!^_"