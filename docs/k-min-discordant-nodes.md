!!! info inline end "See also"

    - [k-Minimum Discordant Nodes in General Graphs](k-min-discordant-nodes-cycles.md)
    - [Minimum-Paths Minimum Discordant Nodes](min-paths-min-discordant-nodes.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)
    - [Handling graphs with flows / weights on nodes](node-expanded-digraph.md)

# k-Minimum Discordant Nodes

The k-Minimum Discordant Nodes model is inspired by the transcript-assembly formulation introduced by Zhao et al. (MultiTrans, 2022). Given node flow values and a tolerance parameter, it finds $k$ weighted source-to-sink paths whose induced node flow explanations minimize the number of nodes that are discordant.

## 1. Definition

The k-Minimum Discordant Nodes problem on a directed **acyclic** graph (*DAG*) is defined as follows.

- **INPUT**:

    - A directed graph $G = (V,E)$ with non-negative observed flow values $f(v)$ on nodes.
    - A tolerance value $\tau \geq 0$.
    - $k \in \mathbb{Z}_+$.

- **OUTPUT**: A list of $k$ source-to-sink paths $P_1,\dots,P_k$ with associated non-negative weights $w_1,\dots,w_k$, minimizing the number of discordant nodes.

For each node $v$, define the explained flow
$$
\widehat{f}(v) = \sum_{i : v \in P_i} w_i.
$$
Node $v$ is discordant if
$$
\widehat{f}(v) \notin \left[(1-\tau)f(v),\ (1+\tau)f(v)\right].
$$
The objective is to minimize the number of discordant nodes.

!!! success "Note"
    - This model takes node flow values as input (`flow_attr` on nodes) and uses the node-expanded graph construction internally.
    - The graph may have multiple sources and sinks.

For example, in the graph below, all node flow values are shown on the nodes.

``` mermaid
flowchart LR
    s((s:5))
    a((a:10))
    b((b:5))
    t((t:5))
    s --> a
    a --> b
    b --> t
```

With $k=1$, no single weighted path can explain all node flows exactly, so at least one node is discordant. With a larger $k$, discordance can decrease or remain the same.

## 2. Solving the problem

``` python
import flowpaths as fp
import networkx as nx

G = nx.DiGraph()
G.add_node("s", flow=5)
G.add_node("a", flow=10)
G.add_node("b", flow=5)
G.add_node("t", flow=5)
G.add_edge("s", "a")
G.add_edge("a", "b")
G.add_edge("b", "t")

model = fp.kMinDiscordantNodes(
    G=G,
    flow_attr="flow",
    k=2,
    discordance_tolerance=0.1,
)
model.solve()

if model.is_solved():
    sol = model.get_solution()
    print(sol["paths"])
    print(sol["weights"])
    print(sol["discordant_nodes"])
```

## 3. References

1. Jin Zhao, Haodi Feng, Daming Zhu, Yu Lin,
[**MultiTrans: An Algorithm for Path Extraction Through Mixed Integer Linear Programming for Transcriptome Assembly**](https://doi.org/10.1109/TCBB.2021.3083277),
IEEE/ACM Transactions on Computational Biology and Bioinformatics 19(1), 48-56, 2022.

2. See also flowpaths [References](references.md).

::: flowpaths.kmindiscordantnodes
    options:
      filters:
        - "!^_"