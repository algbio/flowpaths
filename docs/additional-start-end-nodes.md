# Additional start/end nodes

By default, solution paths must start in a source node of the graph (i.e. a node with no in-coming edges) and end in a sink node of the graph (i.e. a node with no out-going edges). However, in some use cases, solution paths can start/end "in the middle" of other solution paths, which means that they start in a non-source node/end in non-sink node. 

## 1. Implementation

To allow for such scenarios, all decomposition models (except [Minimum Flow Decomposition](minimum-flow-decomposition.md)) offer the possibility of passing also:

- `additional_starts`: a list of nodes where paths are allowed to start; paths are still allowed to start in source nodes;
- `additional_ends`: a list of nodes where paths are allowed to end; paths are still allowed to end in sink nodes.

!!! note "See also"

    For more details, see [k-Least Absolute Values](k-least-absolute-errors.md#2-generalizations), [k-Minimum Path Error](k-min-path-error.md#2-generalizations)

## 2. Example

Suppose we have the example graph from [Minimum Flow Decomposition](minimum-flow-decomposition.md), where on the edges shown in brown we have added a path of weight 20; that is, if we were to remove the path `('a', 'b', 'c', 'd')` with weight 10, the graph would satisfy flow conservation.

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|6| a
    a -->|22| b
    s -->|7| b
    a -->|4| c
    b -->|29| c
    c -->|26| d
    d -->|6| t
    c -->|7| t

    linkStyle 1,4,5 stroke:brown,stroke-width:3;
```

If we solve the k-Minimum Path Error model on it for $k=4$ paths, by default, paths must start in a source (`'s'` is the unique source) and end in a sink (`'t'` is the unique sink). We thus get total solution slack 10.

``` python
import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=6)
graph.add_edge("a", "b", flow=22) #
graph.add_edge("s", "b", flow=7)
graph.add_edge("a", "c", flow=4)
graph.add_edge("b", "c", flow=29) #
graph.add_edge("c", "d", flow=26) #
graph.add_edge("d", "t", flow=6)
graph.add_edge("c", "t", flow=7)

mpe_model = fp.kMinPathError(graph, flow_attr="flow", num_paths=4, weight_type=int)
mpe_model.solve()
if mpe_model.is_solved():
    print(mpe_model.get_solution())
    # {'paths': [
    #   ['s', 'a', 'b', 'c', 'd', 't'], 
    #   ['s', 'a', 'c', 'd', 't'], 
    #   ['s', 'b', 'c', 't'], 
    #   ['s', 'a', 'c', 'd', 't']], 
    # 'weights': [12, 1, 7, 3], 
    # 'slacks': [10, 0, 0, 0]}
```

If we set `additional_starts=['a']`, and `additional_ends=['d']`, we recover indeed the path `['a', 'b', 'c', 'd']` with weight 20, and the total solution slack is 0.

``` python
mpe_model_2 = fp.kMinPathError(
    graph, 
    flow_attr="flow", 
    num_paths=4, 
    weight_type=int,
    additional_starts=['a'],
    additional_ends=['d'])
mpe_model_2.solve()
if mpe_model_2.is_solved():
    print(mpe_model_2.get_solution())
    # {'paths': [
    #   ['s', 'b', 'c', 't'], 
    #   ['s', 'a', 'b', 'c', 'd', 't'], 
    #   ['s', 'a', 'c', 'd', 't'], 
    #   ['a', 'b', 'c', 'd']], 
    # 'weights': [7, 2, 4, 20], 
    # 'slacks': [0, 0, 0, 0]}
```


## 3. Pitfalls

Notice that the above paths of total slack 0 the same as the ones in [Minimum Flow Decomposition](minimum-flow-decomposition.md) plus the brown path of weight 20, which looks like a good solution.

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
    a -->|20| b
    b -->|20| c
    c -->|20| d
    linkStyle 12,13,14 stroke:brown,stroke-width:3;
```
However, allowing additional starts and ends naturally makes the solution less constrained and allowed for solutions that might not be intended. For example, if we had the same example graph as above, but the brown path has weight 10 instead of 20, the paths of minimum slack are different. In fact, we obtain two paths from `'a'` to `'d'`. One needs to make sure this is indended behavior, or otherwise firther constrain the problem.

``` python
graph10 = nx.DiGraph()
graph10.add_edge("s", "a", flow=6)
graph10.add_edge("a", "b", flow=12) #
graph10.add_edge("s", "b", flow=7)
graph10.add_edge("a", "c", flow=4)
graph10.add_edge("b", "c", flow=19) #
graph10.add_edge("c", "d", flow=16) #
graph10.add_edge("d", "t", flow=6)
graph10.add_edge("c", "t", flow=7)

mpe_model_10 = fp.kMinPathError(
    graph10, 
    flow_attr="flow", 
    num_paths=4, 
    weight_type=int,
    additional_starts=['a'],
    additional_ends=['d'])
mpe_model_10.solve()
if mpe_model_10.is_solved():
    print(mpe_model_10.get_solution())
    # {'paths': [
    # ['s', 'b', 'c', 't'], 
    # ['s', 'a', 'b', 'c', 'd', 't'], 
    # ['a', 'c', 'd'], 
    # ['a', 'b', 'c', 'd']], 
    # 'weights': [7, 6, 4, 6], 
    # 'slacks': [0, 0, 0, 0]}
```