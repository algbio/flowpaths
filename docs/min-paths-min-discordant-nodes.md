!!! info inline end "See also"

    - [Minimum-Paths Minimum Discordant Nodes in General Graphs](min-paths-min-discordant-nodes-cycles.md)
    - [k-Minimum Discordant Nodes](k-min-discordant-nodes.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)

# Minimum-Paths Minimum Discordant Nodes

This model optimizes the number of paths for the k-Minimum Discordant Nodes objective in DAGs. It wraps `NumPathsOptimization` with:

- `model_type = kMinDiscordantNodes`
- `stop_on_delta_abs = 0`

Thus, the routine iterates over increasing values of $k$ and stops when the objective value no longer improves in absolute value (plateau criterion).

## 1. Definition

Given a DAG with node flow values, this model returns a decomposition minimizing the number of discordant nodes while selecting $k$ automatically.

The search starts at
$$
k_0 = \max\left(\text{min\_num\_paths},\ \text{lowerbound}(k)\right)
$$
and increases $k$ until one of the stopping conditions in `NumPathsOptimization` is met.

## 2. Solving the problem

``` python
import flowpaths as fp
import networkx as nx

G = nx.DiGraph()
G.add_node("s", flow=5)
G.add_node("a", flow=10)
G.add_node("t", flow=5)
G.add_edge("s", "a")
G.add_edge("a", "t")

model = fp.MinPathsMinDiscordantNodes(
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
    print(sol["paths"])
    print(sol["weights"])
    print(sol["discordant_nodes"])
```

Example search flow:

``` mermaid
flowchart LR
    start([Start at k0]) --> solvek[Solve k-MinDiscordantNodes at k]
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

::: flowpaths.minpathsmindiscordantnodes
    options:
      filters:
        - "!^_"