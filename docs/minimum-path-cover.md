# Minimum Path Cover

## 1. Definition

The Minimum Path Cover problem on a directed **acyclic** graph (*DAG*) is defined as follows:

- **INPUT**: A directed graph $G = (V,E)$.

- **OUTPUT**: A minimum number $k$ of source-to-sink paths, $P_1,\dots,P_k$ such that every edge $e \in E$ appears in at least one $P_i$.

!!! success "Note"
    - This class support also **covers of nodes**. Set the parameter `cover_type = "node"`. For details on how these are handled internally, see [Handling graphs with flows / weights on nodes](node-expanded-digraph.md).
    - The graph may have more than one source or sink nodes, in which case the solution paths are just required to start in any source node, and end in any sink node.

## 2. Solving the problem

We create the graph as a [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html). In real project, you will likely have a method that transforms your graph to a DiGraph. We also give an attribute `flow` for every edge storing its flow value.

``` python
import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a")
graph.add_edge("s", "b")
graph.add_edge("a", "b")
graph.add_edge("a", "c")
graph.add_edge("b", "c")
graph.add_edge("c", "d")
graph.add_edge("c", "t")
graph.add_edge("d", "t")

mpc_model = fp.MinPathCover(graph)
mpc_model.solve()
```

The solution of `MinPathCover` is a dictionary, with an key `'paths'` containing the solution paths:

``` python
if mpc_model.is_solved():
    solution = mpc_model.get_solution()
    print(solution)
    # {'paths': [
    #   ['s', 'b', 'c', 't'], 
    #   ['s', 'a', 'b', 'c', 'd', 't'], 
    #   ['s', 'a', 'c', 't']]} 
```

We can also support subpath constraints:

``` python
subpath_constraints=[[("a", "c"),("c", "t")]]
mpc_model_sc = fp.MinPathCover(
    graph,
    subpath_constraints=subpath_constraints,
)
mpc_model_sc.solve()
```

::: flowpaths.minpathcover
    options:
      filters: 
        - "!^_"
        - "!^solve_time_elapsed"

::: flowpaths.kpathcover
    options:
      filters: 
        - "!^_"