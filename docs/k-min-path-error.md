# k-Minimum Path Error

!!! info inline end "See also"

    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

In the k-Minimum Path Error problem tries to model problems where the weight along a path is not constant. As such, edges that appear in more solution paths will be allowed to have a higher error (i.e. difference betweehn their input weight/flow value and the sum of the weights of the paths that use them). More formally, path now receive also a *slack*, which intuitively models how much the weight along a path can vary. Ideally, we can decompose the weighted graphs with $k$ paths that overall have small slack values.

## 1. Definition

The k-Minimum Path Error problem on a directed **acyclic** graph (*DAG*) is defined as follows:

- **INPUT**: 

    - A directed graph $G = (V,E)$, and a *weight function* on $G$, namely weights $f(u,v)$ for every edge $(u,v)$ of $G$. The weights are arbitrary non-negative numbers and do not need to satisfy flow conservation.
    - $k \in \mathbb{Z}$

- **OUTPUT**: A list of $k$ of source-to-sink paths, $P_1,\dots,P_k$, with a weight $w_i$, and a slack $\rho_i$ associated to each $P_i$, that satisfy the constraint
$$
\left|f(u,v) - \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }w_i\right| \leq \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }\rho_i, ~\forall (u,v) \in E,
$$
and minimize the objective function
$$
\rho_1 + \cdots + \rho_k.
$$

## 2. Generalizations

This class implements a more general version, as follows:

1. The paths can start/end not only in source/sink nodes, but also in given sets of start/end nodes (set parameters `additional_starts` and `additional_ends`). See also [Additional start/end nodes](additional-start-end-nodes.md).
2. This class supports adding subpath constraints, that is, lists of edges that must appear in some solution path. See [Subpath constraints](subpath-constraints.md) for details.
3. The above constrating can happen only over a given subset $E' \subseteq E$ of the edges (set parameter `edges_to_ignore` to be $E \setminus E'$), 
4. The error (i.e. the above absolute of the difference) of every edge can contribute differently to the objective function, according to a scale factor $\in [0,1]$. Set these via a dictionary that you pass to `edge_error_scaling`, which stores the scale factor $\lambda_{(u,v)} \in [0,1]$ of each edge $(u,v)$ in the dictionary. Setting $\lambda_{(u,v)} = 0$ will add the edge $(u,v)$ to `edges_to_ignore`, because the constraint for $(u,v)$ becomes always true.
5. Another way to relax the constraint is to allow also some loosenes in the slack value, based on the length of the solution path. Intuitively, suppose that longer paths have even higher variance in their weight across the edges of the path, while shorter paths less. Formally, suppose that we have a function $\alpha : \mathbb{N} \rightarrow \mathbb{R}^+$ that for every solution path length $\ell$, it returns a multiplicative factor $\alpha(\ell)$. Then, we can multiply each path slack $\rho_i$ by $\alpha(|P_i|)$ in the constraint of the problem (where $|P_i|$ denotes the length of solution path $P_i$). In the above example, we could set $\alpha(\ell) > 1$ for "large" lengths $\ell$. Note that in this model we keep the same objective function (i.e. sum of slacks), and thus this multiplier has no effect on the objective value. You can pass the function $\alpha$ to the class as a piecewise encoding, via parameters `path_length_ranges` and `path_length_factors`, see [kMinPathError()](k-min-path-error.md#flowpaths.kminpatherror.kMinPathError).

!!! info "Generalized constraint"
    Formally, the constraint generalized as in 3., 4. and 5. above is:
    $$
    \lambda_{u,v} \cdot \left|f(u,v) - \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }w_i\right| \leq \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }\rho_i \cdot \alpha(|P_i|), ~\forall (u,v) \in E'.
    $$

!!! warning "A lowerbound on $k$"
    The value of $k$ must be at least the edge width of graph, meaning the minimum number of paths to cover all the edges in $E'$, except those edges $(u,v)$ for which $\lambda_{u,v} = 0$.

## 3. References

1. Fernando H. C. Dias, Alexandru I. Tomescu
[**Accurate Flow Decomposition via Robust Integer Linear Programming**](https://doi.org/10.1109/TCBB.2024.3433523)
IEEE/ACM Transactions on Computational Biology and Bioinformatics 21(6), 1955-1964, 2024 [(preprint)](https://researchportal.helsinki.fi/files/325850154/TCBB3433523.pdf)

::: flowpaths.kminpatherror