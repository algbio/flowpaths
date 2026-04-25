!!! info inline end "See also"

    - [k-Minimum Discordant Nodes in DAGs](k-min-discordant-nodes.md)
    - [Minimum-Paths Minimum Discordant Nodes in General Graphs](min-paths-min-discordant-nodes-cycles.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

# k-Minimum Discordant Nodes in General Graphs

This is the cyclic-graph variant of k-Minimum Discordant Nodes, inspired by the transcript-assembly formulation introduced by Zhao et al. (MultiTrans, 2022). It finds $k$ weighted source-to-sink walks that minimize the number of discordant nodes.

## 1. Definition

The k-Minimum Discordant Nodes problem on a directed graph, possibly with cycles, is defined as follows.

- **INPUT**:

    - A directed graph $G = (V,E)$ with non-negative observed flow values $f(v)$ on nodes.
    - A tolerance value $\tau \geq 0$.
    - $k \in \mathbb{Z}_+$.

- **OUTPUT**: A list of $k$ walks $W_1,\dots,W_k$ and corresponding non-negative weights $w_1,\dots,w_k$, minimizing the number of discordant nodes.

For each node $v$, let $W_i(v)$ denote the number of occurrences of $v$ in walk $W_i$.
The explained flow at node $v$ is
$$
\widehat{f}(v) = \sum_{i=1}^{k} w_i \cdot W_i(v).
$$
Node $v$ is discordant if
$$
\widehat{f}(v) \notin \left[(1-\tau)f(v),\ (1+\tau)f(v)\right].
$$
The objective is to minimize the number of discordant nodes.

For example, a cyclic input graph can be:

``` mermaid
flowchart LR
    s((s:5))
    a((a:5))
    b((b:5))
    t((t:5))
    s --> a
    a --> b
    b --> a
    b --> t
```

## 2. Solving the problem

``` python
import flowpaths as fp
import networkx as nx

G = nx.DiGraph()
G.add_node("s", flow=5)
G.add_node("a", flow=5)
G.add_node("b", flow=5)
G.add_node("t", flow=5)
G.add_edge("s", "a")
G.add_edge("a", "b")
G.add_edge("b", "a")
G.add_edge("b", "t")

model = fp.kMinDiscordantNodesCycles(
    G=G,
    flow_attr="flow",
    k=2,
    discordance_tolerance=0.1,
)
model.solve()

if model.is_solved():
    sol = model.get_solution(remove_empty_walks=True)
    print(sol["walks"])
    print(sol["weights"])
    print(sol["discordant_nodes"])
```

## 3. References

1. Jin Zhao, Haodi Feng, Daming Zhu, Yu Lin,
[**MultiTrans: An Algorithm for Path Extraction Through Mixed Integer Linear Programming for Transcriptome Assembly**](https://doi.org/10.1109/TCBB.2021.3083277),
IEEE/ACM Transactions on Computational Biology and Bioinformatics 19(1), 48-56, 2022.

2. See also flowpaths [References](references.md).

::: flowpaths.kmindiscordantnodescycles
    options:
      filters:
        - "!^_"