!!! info inline end "See also"

    - [k-Flow Decomposition in General Graphs](k-flow-decomposition-cycles.md)
    - [Minimum Flow Decomposition in Acyclic Graphs](minimum-flow-decomposition.md)

# Minimum Flow Decomposition in General Graphs

## 1. Definition

The Minimum Flow Decomposition problem on a directed graph (**possibly with cycles**) is defined as follows:

- **INPUT**: 

    - A directed graph $G = (V,E)$.
    - Node subsets $S \subseteq V$ and $T \subseteq V$, where the walks are allowed to start and allowed to end, respectively.
    - A *flow* on $G$, namely weights $f(u,v)$ for every edge $(u,v)$ of $G$, such that for every node $v$ that is not in $S$ or $T$, it holds that the sum of the flow values entering $v$ equals the sum of the flow values exiting $v$. This property is called *flow conservation*. 
    - Note that for flow conservation to hold, all graph sources (i.e. nodes without incoming edges) must be in $S$, and all graph sinks (i.e. nodes without outgoing edges) must be in $T$.

- **OUTPUT**: A minimum number $k$ of walks $W_1,\dots,W_k$, starting in some node in $S$ and ending in some node in $T$, and a weight $w_i$ associated to each $W_i$, such that for every edge of the graph it holds that its flow value equals the sum of the weights of the walks going through the edge. Formally, 
$$
f(u,v) = \sum_{i \in \\{1,\dots,k\\} : (u,v) \in W_i }w_i, ~~\forall (u,v) \in E.
$$

!!! success "Note"
    - This class support also graphs with **flow values on nodes**. Set the parameter `flow_attr_origin = "node"`. For details on how these are handled internally, see [Handling graphs with flows / weights on nodes](node-expanded-digraph.md).
    - The graph may have more than one source or sink nodes, in which case the solution paths are just required to start in any source node, and end in any sink node.

For example, the directed graph below satisfies the flow conservation property, with $S = \{s\}$ and $T = \{t\}$:
``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    e((e))
    f((f))
    g((g))
    h((h))
    t((t))
    s -->|3| a
    a -->|3| t
    s -->|6| b
    b -->|2| a
    a -->|2| h
    h -->|6| t
    b -->|4| c
    c -->|4| h
    c -->|4| d
    d -->|4| e
    e -->|4| c
    e -->|8| f
    f -->|8| g
    g -->|8| e
```

A decomposition into 3 walks, in red, orange and blue, of weights 4, 3 and 2, respectively is shown below. There is no decomposition into a smaller number of $s$-$t$ walks, and thus this decomposition is also a minimum flow decomposition.

Note that the orange and blue walks do not repeat nodes or edges (they are *paths*), but the red walk $s$, $b$, $c$, $d$, $e$, $f$, $g$, $e$, $f$, $g$, $e$, $c$, $h$, $t$ is a proper walks in the sense that repeats both nodes and edges.
``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    e((e))
    f((f))
    g((g))
    h((h))
    t((t))
    s -->|3| a
    a -->|3| t
    s -->|2| b
    s -->|4| b
    b -->|2| a
    a -->|2| h
    h -->|2| t
    h -->|4| t
    b -->|4| c
    c -->|4| h
    c -->|4| d
    d -->|4| e
    e -->|4| c
    e -->|4| f
    f -->|4| g
    g -->|4| e
    e -->|4| f
    f -->|4| g
    g -->|4| e
    linkStyle 0,1 stroke:orange,stroke-width:3;
    linkStyle 2,4,5,6 stroke:blue,stroke-width:3;
    linkStyle 3,7,8,9,10,11,12,13,14,15,16,17,18 stroke:red,stroke-width:3;
```

## 2. Solving the problem

We create the graph as a [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html). In real project, you will likely have a method that transforms your graph to a DiGraph. We also give an attribute `flow` for every edge storing its flow value.

``` python
import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=3)
graph.add_edge("a", "t", flow=3)
graph.add_edge("s", "b", flow=6)
graph.add_edge("b", "a", flow=2)
graph.add_edge("a", "h", flow=2)
graph.add_edge("h", "t", flow=6)
graph.add_edge("b", "c", flow=4)
graph.add_edge("c", "d", flow=4)
graph.add_edge("c", "h", flow=4)
graph.add_edge("d", "h", flow=0)
graph.add_edge("d", "e", flow=4)
graph.add_edge("e", "c", flow=4)
graph.add_edge("e", "f", flow=8)
graph.add_edge("f", "g", flow=8)
graph.add_edge("g", "e", flow=8)
```
We now create a Minimum Flow Decomposition solver with default settings, by specifying that the flow value of each edge is in the attribute `flow` of the edges. Note that `MinFlowDecompCycles` just creates the model. You need to call `solve()` to solve it.

``` python
mfd_model = fp.MinFlowDecompCycles(G=graph, flow_attr="flow")
mfd_model.solve()
```

The model might not be solved because the MILP solver couldn't do it in the time it had allocated, or other problems. Thus, you need to check if it was solved, and then get its solution. The solution of `MinFlowDecompCycles` is a dictionary, with a key `'walks'`, and a key `'weights'`:

``` python
if mfd_model.is_solved():
    solution = mfd_model.get_solution()
    print(solution)
    # {'walks': [
    #   ['s', 'b', 'c', 'd', 'e', 'f', 'g', 'e', 'f', 'g', 'e', 'c', 'h', 't'], 
    #   ['s', 'a', 't'], 
    #   ['s', 'b', 'a', 'h', 't']]
    # 'weights': [4, 3, 2]}
```

## 3. References

There are several works on this problem, for example.

1. Vatinlen, Benedicte, et al. [**Simple bounds and greedy algorithms for decomposing a flow into a minimal set of paths**](https://fc.isima.fr/~mahey/ejor_2008.pdf). European Journal of Operational Research 185.3 (2008): 1390-1401.

2. Fernando H. C. Dias, Lucia Williams, Brendan Mumey, Alexandru I. Tomescu [**Minimum Flow Decomposition in Graphs with Cycles using Integer Linear Programming**](https://arxiv.org/abs/2209.00042), arXiv, 2022

3. See also flowpaths [References](references.md), and the other papers cited by these works.

::: flowpaths.minflowdecompcycles
    options:
      filters: 
        - "!^_"
        - "!solve_time_elapsed"