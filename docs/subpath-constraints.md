# Adding subpath constraints

## 1. Definition

To any of the models that are based on (or inherit from) the [AbstractPathModelDAG](abstract-path-model.md) class you can add *subpath constraints*. This means the following. Say that you have prior knowledge of some (shorter) paths that *must* appear in at least one solution path of you model. These *constrain* the space of possible solution paths.

Let's consider the [Minimum Flow Decomposition](minimum-flow-decomposition.md) problem, and let's take the example graph from there. Let's assume that you want the subpath `[a,c,t]` (which we draw in brown) to appear in at last one solution path. 

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|6| a
    a -->|2| b
    s -->|7| b
    a -->|4| c
    b -->|9| c
    c -->|6| d
    d -->|6| t
    c -->|7| t
    linkStyle 3,7 stroke:brown,stroke-width:3;
```

For example, the following flow decomposition doesn't contain `[a,c,t]`, in the sense that neither red, orange, or blue paths contain it.

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|4| a
    a -->|4| c
    c -->|4| d
    d -->|4| t
    linkStyle 0,1,2,3 stroke:red,stroke-width:3;
    s -->|2| a
    a -->|2| b
    b -->|2| c
    c -->|2| d
    d -->|2| t
    linkStyle 4,5,6,7,8 stroke:orange,stroke-width:3;
    s -->|7| b
    b -->|7| c
    c -->|7| t
    linkStyle 9,10,11 stroke:blue,stroke-width:3;
```

A valid decomposition that contains it, and has the minimum number of paths is the following. Note that `[a,c,t]` now appears in the orange path.

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    c -->|6| d
    d -->|6| t
    s -->|2| a
    a -->|2| b
    b -->|2| c
    c -->|2| t
    linkStyle 2,3,4,5 stroke:red,stroke-width:3;
    s -->|4| a
    a -->|4| c
    c -->|4| t
    linkStyle 6,7,8 stroke:orange,stroke-width:3;
    s -->|1| b
    b -->|1| c
    c -->|1| t
    linkStyle 9,10,11 stroke:blue,stroke-width:3;
    s -->|6| b
    b -->|6| c
    linkStyle 0,1,12,13 stroke:green,stroke-width:3;
```

## 2. Example: Adding subpath constraints to Minimum Flow Decomposition

!!! tip "Note 1"
    Any existing decomposition model based on [AbstractPathModelDAG](abstract-path-model.md) supports subpath constraints.

!!! tip "Note 2" 
    The models support adding non-contiguous subpath constraints. In mathematical terms, they can be sequences of edges that don't necessarily share endpoints. Then, at least one solution path is required to contain this sequence of edges. Since the graph is a DAG, then the edges also appear in the order they are in the sequence.


We create the graph as a [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html).

``` python
import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=6)
graph.add_edge("s", "b", flow=7)
graph.add_edge("a", "b", flow=2)
graph.add_edge("a", "c", flow=4)
graph.add_edge("b", "c", flow=9)
graph.add_edge("c", "d", flow=6)
graph.add_edge("c", "t", flow=7)
graph.add_edge("d", "t", flow=6)
```

We now create a solver by specifying that the flow value of each edge is in the attribute `flow` of the edges, and setting `subpath_constraints` as a list, containing the single constraint `[("a", "c"),("c", "t")]`. Note that we pass the constraint as a list of edges, because of Note 2 above.

``` python
mfd_model = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow", 
        subpath_constraints=[[("a", "c"),("c", "t")]])
        
mfd_model.solve() # We solve it
if mfd_model.is_solved():
    print(mfd_model.get_solution())
    # {'paths': [['s', 'a', 'b', 'c', 't'], ['s', 'a', 'c', 't'], ['s', 'b', 'c', 't'], ['s', 'b', 'c', 'd', 't']], 'weights': [2.0, 4.0, 1.0, 6.0]}
```

## 3. Relaxing the constraint coverage

### 3.1 Edge coverage fraction

Suppose that you have have a subpath constraint, but you're not sure the subpath must appear entirely in a solution path. In this case, you can require that a give fraction of its edges appear in a solution path. For example, say you have the constraint `['s','a','c','t']`. Then, if you require that 50% of its edges appear in a solution path, the red path in the first flow decomposition on top (with 3 paths) contains `['s','a','c']`, thus 66% of its edges appea in the red path, and thus the decomposition satisfies this constraint. You can set this percentage via the parameter `subpath_constraints_coverage` $\in [0,1]$.

``` python
mfd_model = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow", 
        subpath_constraints=[[("s", "a"),("a", "c"),("c","t")]], 
        subpath_constraints_coverage=0.75)
```

### 3.2 Edge length coverage fraction

If for every edge you also have an associated length, then you can specify the coverage constraint as a fraction of the total edge length of the contraint.

For example, suppose we have a graph, where the attribute `length` stores the edge lengths.

``` python
graph2 = nx.DiGraph()
graph2.add_edge("s", "a", flow=6, length=1) #
graph2.add_edge("s", "b", flow=7, length=2)
graph2.add_edge("a", "b", flow=2, length=9)
graph2.add_edge("a", "c", flow=4, length=20) #
graph2.add_edge("b", "c", flow=9, length=9)
graph2.add_edge("c", "d", flow=6, length=29)
graph2.add_edge("c", "t", flow=7, length=15) #
graph2.add_edge("d", "t", flow=6, length=1)
```

When initializing the solver, we pass `length_attr="length"` so that the solver knows from which edge attribute to get the lengths, and set the parameter `subpath_constraints_coverage_length` to say 0.6. The constraint has total length 1+20+15 = 36, and the length coverage fraction requires that 0.6 * 36 = 6 of the subpath length be covered by some solution path. This means that covering the edge `("s", "a")` alone is not enough to satisfy the constraint, as it could cover only length 1.

``` python
mfd_model = fp.MinFlowDecomp(
    graph2, 
    flow_attr="flow", 
    length_attr="length", 
    subpath_constraints=[[("s", "a"),("a", "c"),("c","t")]], 
    subpath_constraints_coverage_length=0.6
    )
```