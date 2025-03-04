!!! info inline end "See also"

    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

# k-Least Absolute Errors

## 1. Definition

The k-Least Absolute Errors problem on a directed **acyclic** graph (*DAG*) is defined as follows:

- **INPUT**: 

    - A directed graph $G = (V,E)$, and a *weight function* on $G$, namely weights $f(u,v)$ for every edge $(u,v)$ of $G$. The weights are arbitrary non-negative numbers and do not need to satisfy flow conservation.
    - $k \in \mathbb{Z}$

- **OUTPUT**: A list of $k$ of source-to-sink paths, $P_1,\dots,P_k$, with a weight $w_i$ associated to each $P_i$, that minimize the objective function:
$$
\sum_{(u,v) \in E} \left|f(u,v) - \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }w_i\right|.
$$

## 2. Generalizations

This class implements a more general version, as follows:

1. This class supports adding subpath constraints, that is, lists of edges that must appear in some solution path. See [Subpath constraints](subpath-constraints.md) for details.
2. The paths can start/end not only in source/sink nodes, but also in given sets of start/end nodes (set parameters `additional_starts` and `additional_ends`). See also [Additional start/end nodes](additional-start-end-nodes.md).
3. The above summation can happen only over a given subset $E' \subseteq E$ of the edges (set parameter `edges_to_ignore` to be $E \setminus E'$), 
4. The error (i.e. the above absolute of the difference) of every edge can contribute differently to the objective function, according to a scale factor $\in [0,1]$. Set these via a dictionary that you pass to `edge_error_scaling`, which stores the scale factor $\lambda_{(u,v)} \in [0,1]$ of each edge $(u,v)$ in the dictionary. Setting $\lambda_{(u,v)} = 0$ is equivalent to adding the edge $(u,v)$ to `edges_to_ignore`; the latter option is more efficient, as it results in a smaller model.

!!! info "Generalized objective function"
    Formally, the minimized objective function generalized as in 3. and 4. above is:
    $$
    \sum_{(u,v) \in E'} \lambda_{(u,v)} \cdot \left|f(u,v) - \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }w_i\right|.
    $$


::: flowpaths.kleastabserrors