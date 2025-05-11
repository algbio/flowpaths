# Ignoring edges or nodes

All decomposition models (except `MinFlowDecomp`) offer the option of ignoring some edges from the constraints that the solution paths need to satisfy, or dampening their effect on the constraints or on the objective value of the model. 

The indented use-case is when some edges, or their weights, are not fully trusted. Intuitively, we want to keep them in the graph to e.g. allow the solution paths to go through them, but we do not want them to penalize the solution.

## 1. Implementation

This is achieved via:

1. Passing a list  of edges as `elements_to_ignore`. 
2. Passing a dict `error_scaling` that associates to some edges `(u,v)` a scaling factor `error_scaling[(u,v,)]` in the interval [0,1]. If this factor is 0, then edges are completely ignored, if it is 1 they are fully trusted. Adding an edge to `elements_to_ignore` overrides the value it could be assigned via this dictionary (i.e. it is equivalent to setting its scaling factor to 0). 

!!! note "See also"

    For more details, see [k-Least Absolute Values](k-least-absolute-errors.md#2-generalizations), [k-Minimum Path Error](k-min-path-error.md#2-generalizations)

## 2. Example

Suppose we have the graph from [Minimum Flow Decomposition](minimum-flow-decomposition.md), where we multiplied all original edge weights by 10, and in addition we added the edge `('a','d')` with weight 1.

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|60| a
    a -->|20| b
    s -->|70| b
    a -->|40| c
    b -->|90| c

    a -->|1| d

    c -->|60| d
    d -->|60| t
    c -->|70| t
    
    linkStyle 5 stroke:brown,stroke-width:3;
```

Notice that we now need at least 4 paths to have a feasible solution, and indeed we get the `['s', 'a', 'd', 't']` of weight 0 and slack 1, giving a total solution slack of 1.

``` python
import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=60)
graph.add_edge("a", "b", flow=20)
graph.add_edge("s", "b", flow=70)
graph.add_edge("a", "c", flow=40)
graph.add_edge("b", "c", flow=90)
graph.add_edge("c", "d", flow=60)
graph.add_edge("d", "t", flow=60)
graph.add_edge("c", "t", flow=70)

graph.add_edge("a", "d", flow=1)

mpe_model = fp.kMinPathError(graph, flow_attr="flow", k=4, weight_type=int)
mpe_model.solve()
if mpe_model.is_solved():
    print(mpe_model.get_solution())
    # {'paths': [
    #   ['s', 'a', 'b', 'c', 'd', 't'], 
    #   ['s', 'a', 'c', 'd', 't'], 
    #   ['s', 'a', 'd', 't'], 
    #   ['s', 'b', 'c', 't']], 
    # 'weights': [20, 40, 0, 70], 
    # 'slacks': [0, 0, 1, 0]}
```

Such a high difference in weights (or any other domain knowledge) might raise some red flags, so we can set `elements_to_ignore = [('a','d')]`. Noteice that in this case 3 paths are enough to cover all the edges except `('a','d')`.

``` python
mpe_model_2 = fp.kMinPathError(
    graph, 
    flow_attr="flow", 
    k=3, 
    weight_type=int,
    elements_to_ignore=[("a", "d")])
mpe_model_2.solve()
if mpe_model_2.is_solved():
    print(mpe_model_2.get_solution())
    # {'paths': [
    #   ['s', 'a', 'b', 'c', 'd', 't'], 
    #   ['s', 'a', 'c', 'd', 't'], 
    #   ['s', 'b', 'c', 't']], 
    # 'weights': [20, 40, 70], 
    # 'slacks': [0, 0, 0]}
```

These paths are as follows, and notice that in this example they do not even pass through the edge `('a','d')`.

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|40| a
    a -->|40| c
    c -->|40| d
    d -->|40| t
    linkStyle 0,1,2,3 stroke:red,stroke-width:3;
    s -->|20| a
    a -->|20| b
    b -->|20| c

    a -->|1| d

    c -->|20| d
    d -->|20| t
    linkStyle 4,5,6,8,9 stroke:orange,stroke-width:3;
    s -->|70| b
    b -->|70| c
    c -->|70| t
    linkStyle 10,11,12 stroke:blue,stroke-width:3;
```