!!! info inline end "See also"

    - [Minimum-Paths Minimum Discordant Nodes](min-paths-min-discordant-nodes.md)
    - [k-Minimum Discordant Nodes in General Graphs](k-min-discordant-nodes-cycles.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)

# Minimum-Paths Minimum Discordant Nodes in General Graphs

This model optimizes the number of walks for the k-Minimum Discordant Nodes objective in directed graphs with cycles. It wraps `NumPathsOptimization` with:

- `model_type = kMinDiscordantNodesCycles`
- `stop_on_delta_abs = 0`

Thus, it iterates over increasing values of $k$ and stops when the discordant-node objective reaches a plateau.

## 1. Definition

Given a directed graph (possibly cyclic) with node flow values, this model returns weighted walks minimizing discordant nodes while selecting $k$ automatically.

The search starts from a valid lower bound and increases $k$ up to `max_num_paths` (or until time limit), stopping at the first non-improving objective value under the absolute-delta rule.

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

model = fp.MinPathsMinDiscordantNodesCycles(
    G=G,
    flow_attr="flow",
    discordance_tolerance=0.1,
    min_num_paths=1,
    max_num_paths=10,
)
model.solve()

if model.is_solved():
    sol = model.get_solution(remove_empty_paths=True)
    print(model.model.k)  # selected k
    print(sol["walks"])
    print(sol["weights"])
    print(sol["discordant_nodes"])
```

Example search flow:

``` mermaid
flowchart LR
    start([Start at k0]) --> solvek[Solve k-MinDiscordantNodesCycles at k]
    solvek --> feasible{Solved?}
    feasible -- no --> nextk[Increase k]
    feasible -- yes --> plateau{Objective plateau?}
    plateau -- no --> nextk
    plateau -- yes --> stop([Return previous feasible model])
    nextk --> solvek
```

## 3. References

1. Jin Zhao, Haodi Feng, Daming Zhu, Yu Lin,
[**MultiTrans: An Algorithm for Path Extraction Through Mixed Integer Linear Programming for Transcriptome Assembly**](https://doi.org/10.1109/TCBB.2021.3083277),
IEEE/ACM Transactions on Computational Biology and Bioinformatics 19(1), 48-56, 2022.

2. See also flowpaths [References](references.md).

::: flowpaths.minpathsmindiscordantnodescycles
    options:
      filters:
        - "!^_"