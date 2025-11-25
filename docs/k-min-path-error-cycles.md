# k-Minimum Path Error in General Graphs

!!! info inline end "See also"

    - [k-Minimum Path Error in DAGs](k-min-path-error.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

The k-Minimum Path Error problem tries to model cases where the weight along a walk is not constant. As such, edges that appear in more solution walks will be allowed to have a higher error (i.e. difference between their input weight/flow value and the sum of the weights of the walks that use them). More formally, walks now receive also a *slack*, which intuitively models how much the weight along a walk can vary. Ideally, we can decompose the weighted graphs with $k$ walks that overall have small slack values.

## 1. Definition

The k-Minimum Path Error problem on a directed graphs, possibly with cycles, is defined as follows. For a walk $W$ and an edge $(u,v)$, we denote by $W(u,v)$ the number of times that the walk goes through the edge $(u,v)$. If $W(u,v)$ does not contain $(u,v)$ , then $W(u,v) = 0$.

- **INPUT**: 

    - A directed graph $G = (V,E)$.
    - Node subsets $S \subseteq V$ and $T \subseteq V$, where the walks are allowed to start and allowed to end, respectively.
    - A *weight function* on $G$, namely weights $f(u,v)$ for every edge $(u,v)$ of $G$. The weights are arbitrary non-negative numbers and do not need to satisfy flow conservation.
    - $k \in \mathbb{Z}_+$.

- **OUTPUT**: A list of $k$ of walks $W_1,\dots,W_k$, starting in some node in $S$ and ending in some node in $T$, with a weight $w_i$, and a slack $\rho_i$ associated to each $W_i$, that satisfy the constraint
$$
\left|f(u,v) - \sum_{i \in \\{1,\dots,k\\}} w_i \cdot W_i(u,v)\right| \leq \sum_{i \in \\{1,\dots,k\\}}\rho_i\cdot W_i(u,v), ~\forall (u,v) \in E,
$$
and minimize the objective function
$$
\rho_1 + \cdots + \rho_k.
$$

!!! success "Note"
    - This class support also graphs with **flow values on nodes**. Set the parameter `flow_attr_origin = "node"`. For details on how these are handled internally, see [Handling graphs with flows / weights on nodes](node-expanded-digraph.md).
    - The graph may have more than one source or sink nodes, in which case the solution walks are just required to start in any source node, and end in any sink node.

## 2. Generalizations

This class implements a more general version, as follows:

1. The walks can start/end not only in source/sink nodes, but also in given sets of start/end nodes (set parameters `additional_starts` and `additional_ends`). See also [Additional start/end nodes](additional-start-end-nodes.md).
2. This class supports adding subset constraints, that is, lists of edges that must appear in some solution walks. See [Subset constraints](subset-constraints.md) for details.
3. The above constraint can happen only over a given subset $E' \subseteq E$ of the edges (set parameter `elements_to_ignore` to be $E \setminus E'$). See also [ignoring edges documentation](ignoring-edges.md).
4. The error (i.e. the above absolute of the difference) of every edge can contribute differently to the objective function, according to a scale factor $\in [0,1]$. Set these via a dictionary that you pass to `error_scaling`, which stores the scale factor $\lambda_{(u,v)} \in [0,1]$ of each edge $(u,v)$ in the dictionary. Setting $\lambda_{(u,v)} = 0$ will add the edge $(u,v)$ to `elements_to_ignore`, because the constraint for $(u,v)$ becomes always true. See also [ignoring edges documentation](ignoring-edges.md).

!!! info "Generalized constraint"
    Formally, the constraint generalized as in 3., 4. and 5. above is:
    $$
    \lambda_{(u,v)} \cdot \left|f(u,v) - \sum_{i \in \\{1,\dots,k\\}}w_i \cdot W_i(u,v)\right| \leq \sum_{i \in \\{1,\dots,k\\}}\rho_i \cdot W_i(u,v), ~\forall (u,v) \in E'.
    $$

!!! warning "A lowerbound on $k$"
    The value of $k$ must be at least the edge width of graph, meaning the minimum number of walks to cover all the edges in $E'$, except those edges $(u,v)$ for which $\lambda_{u,v} = 0$. This value always gives a feasible model. 
    
    If you do not know this lower bound, you can pass `k = None` and the model will automatically set `k` to this lowerbound value.

## 3. References

1. Fernando H. C. Dias, Alexandru I. Tomescu
[**Accurate Flow Decomposition via Robust Integer Linear Programming**](https://doi.org/10.1109/TCBB.2024.3433523)
IEEE/ACM Transactions on Computational Biology and Bioinformatics 21(6), 1955-1964, 2024 [(preprint)](https://researchportal.helsinki.fi/files/325850154/TCBB3433523.pdf)

2. Francisco Sena, Alexandru I. Tomescu
[**Fast and Flexible Flow Decompositions in General Graphs via Dominators**](https://arxiv.org/abs/2511.19153), arXiv, 2025

::: flowpaths.kminpatherrorcycles
    options:
      filters: 
        - "!^_"