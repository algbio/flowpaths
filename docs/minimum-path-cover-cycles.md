!!! info inline end "See also"

    - [Minimum Path Cover in DAGs](minimum-path-cover.md)

# Minimum Path Cover in General Graphs

## 1. Definition

The Minimum Path Cover problem on a directed graph, possibly with cycles, is defined as follows:

- **INPUT**: 

    - A directed graph $G = (V,E)$.
    - Node subsets $S \subseteq V$ and $T \subseteq V$, where the walks are allowed to start and allowed to end, respectively.
    
- **OUTPUT**: A minimum number $k$ of walks $W_1,\dots,W_k$, starting in some node in $S$ and ending in some node in $T$, such that every edge appears in at least one $W_i$.

!!! success "Note"
    - This class support also **covers of nodes**. Set the parameter `cover_type = "node"`. For details on how these are handled internally, see [Handling graphs with flows / weights on nodes](node-expanded-digraph.md).
    - The graph may have more than one source or sink nodes, in which case the solution paths are just required to start in any source node, and end in any sink node.

## 2. Solving the problem

We create the graph as a [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html). In real project, you will likely have a method that transforms your graph to a DiGraph.

``` python
import flowpaths as fp
import networkx as nx

def test():
  graph = nx.DiGraph()
  graph.add_edge("s", "a")
  graph.add_edge("a", "t")
  graph.add_edge("s", "b")
  graph.add_edge("b", "a")
  graph.add_edge("a", "h")
  graph.add_edge("h", "t")
  graph.add_edge("b", "c")
  graph.add_edge("c", "d")
  graph.add_edge("c", "h")
  graph.add_edge("d", "h")
  graph.add_edge("d", "e")
  graph.add_edge("e", "c")
  graph.add_edge("e", "f")
  graph.add_edge("f", "g")
  graph.add_edge("g", "e")

  mpc_model = fp.MinPathCoverCycles(G=graph)
  mpc_model.solve()
```

The solution of `MinPathCoverCycles` is a dictionary, with a key `'walks'` containing the solution walks:

``` python
if mpc_model.is_solved():
    solution = mpc_model.get_solution()
    print(solution)
    # {'walks': [
    #   ['s', 'a', 't'], 
    #   ['s', 'b', 'a', 'h', 't'], 
    #   ['s', 'b', 'c', 'd', 'e', 'f', 'g', 'e', 'c', 'h', 't'], 
    #   ['s', 'b', 'c', 'd', 'h', 't']]}
```

We can also support [subset constraints](subset-constraints.md):

``` python
subset_constraints=[[("b", "a"),("a", "t")]]
mpc_model_sc = fp.MinPathCover(
    graph,
    subset_constraints=subset_constraints,
)
mpc_model_sc.solve()
```

::: flowpaths.minpathcovercycles
    options:
      filters: 
        - "!^_"
        - "!^solve_time_elapsed"

::: flowpaths.kpathcovercycles
    options:
      filters: 
        - "!^_"