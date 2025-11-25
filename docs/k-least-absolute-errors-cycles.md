!!! info inline end "See also"

    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

# k-Least Absolute Errors in General Graphs

## 1. Definition

The k-Least Absolute Errors problem on a directed **acyclic** graph (*DAG*) is defined as follows. For a walk $W$ and an edge $(u,v)$, we denote by $W(u,v)$ the number of times that the walk goes through the edge $(u,v)$. If $W(u,v)$ does not contain $(u,v)$ , then $W(u,v) = 0$.

- **INPUT**: 

    - A directed graph $G = (V,E)$, and a *weight function* on $G$, namely weights $f(u,v)$ for every edge $(u,v)$ of $G$. The weights are arbitrary non-negative numbers and do not need to satisfy flow conservation.
    - $k \in \mathbb{Z}$

- **OUTPUT**: A number $k$ of walks $W_1,\dots,W_k$, starting in some node in $S$ and ending in some node in $T$, with a weight $w_i$ associated to each $P_i$, that minimize the objective function:
$$
\sum_{(u,v) \in E} \left|f(u,v) - \sum_{i \in \\{1,\dots,k\\}}w_i \cdot W_i(u,v)\right|.
$$

!!! success "Note"
    - This class support also graphs with **flow values on nodes**. Set the parameter `flow_attr_origin = "node"`. For details on how these are handled internally, see [Handling graphs with flows / weights on nodes](node-expanded-digraph.md).
    - The graph may have more than one source or sink nodes, in which case the solution paths are just required to start in any source node, and end in any sink node.

## 2. Generalizations

This class implements a more general version, as follows:

1. This class supports adding subset constraints, that is, lists of edges that must appear in some solution path. See [Subset constraints](subset-constraints.md) for details.
2. The paths can start/end not only in source/sink nodes, but also in given sets of start/end nodes (set parameters `additional_starts` and `additional_ends`). See also [Additional start/end nodes](additional-start-end-nodes.md).
3. The above summation can happen only over a given subset $E' \subseteq E$ of the edges (set parameter `elements_to_ignore` to be $E \setminus E'$), 
4. The error (i.e. the above absolute of the difference) of every edge can contribute differently to the objective function, according to a scale factor $\in [0,1]$. Set these via a dictionary that you pass to `error_scaling`, which stores the scale factor $\lambda_{(u,v)} \in [0,1]$ of each edge $(u,v)$ in the dictionary. Setting $\lambda_{(u,v)} = 0$ is equivalent to adding the edge $(u,v)$ to `elements_to_ignore`; the latter option is more efficient, as it results in a smaller model.

!!! info "Generalized objective function"
    Formally, the minimized objective function generalized as in 3. and 4. above is:
    $$
    \sum_{(u,v) \in E'} \lambda_{(u,v)} \cdot \left|f(u,v) - \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }w_i\right|.
    $$


::: flowpaths.kleastabserrorscycles
    options:
      filters: 
        - "!^_"