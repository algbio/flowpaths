!!! info inline end "See also"

    - [k-Flow Decomposition](k-flow-decomposition.md)
    - [An Optimization Routine for the Number k of Paths](numpathsoptimization.md)

# Minimum Flow Decomposition

## 1. Definition

The Minimum Flow Decomposition problem on a directed **acyclic** graph (*DAG*) is defined as follows:

- **INPUT**: A directed graph $G = (V,E)$, and a *flow* on $G$, namely weights $f(u,v)$ for every edge $(u,v)$ of $G$, such that for every node $v$ that is not a source or sink of $G$, it holds that the sum of the flow values entering $v$ equals the sum of the flow values exiting $v$. This property is called *flow conservation*. 

- **OUTPUT**: A minimum number $k$ of source-to-sink paths, $P_1,\dots,P_k$, with a weight $w_i$ associated to each $P_i$, such that for every edge it holds that its flow value equals the sum of the weights of the paths going through the edge. Formally, 
$$
f(u,v) = \sum_{i \in \\{1,\dots,k\\} : (u,v) \in P_i }w_i, ~~\forall (u,v) \in E.
$$

!!! info "Note"
    The graph may have more than one source or sink nodes. The solution paths are required to start in some source node, and end in some sink node.

For example, the directed graph below satisfies the flow conservation property:
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
```

A decomposition into 3 paths, in red, orange and blue, of weights 4, 2 and 7, respectively is shown below. There is no decomposition into a smaller number of paths, and thus this decomposition is also a minimum flow decomposition.
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

## 2. Solving the problem

We create the graph as a [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html). In real project, you will likely have a method that transforms your graph to a DiGraph. We also give an attribute `flow` for every edge storing its flow value.

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
We now create a Minimum Flow Decomposition solver with default settings, by specifying that the flow value of each edge is in the attribute `flow` of the edges. Note that `MinFlowDecomp` just creates the model. You need to call `solve()` to solve it.

``` python
mfd_model = fp.MinFlowDecomp(graph, flow_attr="flow")
mfd_model.solve()
```

The model might not be solved because the MILP solver couldn't do it in the time it had allocated, or other problems. Thus, you need to check if it was solved, and then get its solution. The solution of `MinFlowDecomp` is a dictionary, with an key `'paths'`, and a key `'weights'`:

``` python
if mfd_model.is_solved():
    solution = mfd_model.get_solution()
    print(solution)
    # {'paths': [
    #   ['s', 'b', 'c', 't'], 
    #   ['s', 'a', 'c', 'd', 't'], 
    #   ['s', 'a', 'b', 'c', 'd', 't']], 
    # 'weights': [7, 4, 2]} 
```

## 3. References

There are several works on this problem, for example.

1. Vatinlen, Benedicte, et al. [**Simple bounds and greedy algorithms for decomposing a flow into a minimal set of paths**](https://fc.isima.fr/~mahey/ejor_2008.pdf). European Journal of Operational Research 185.3 (2008): 1390-1401.

2. Shao, Mingfu, and Carl Kingsford. [**Theory and a heuristic for the minimum path flow decomposition problem**](https://ieeexplore.ieee.org/iel7/8857/4359833/08126870.pdf). IEEE/ACM Transactions on Computational Biology and Bioinformatics 16.2 (2017): 658-670.

3. Kloster, Kyle, et al. [**A practical fpt algorithm for flow decomposition and transcript assembly**](https://epubs.siam.org/doi/pdf/10.1137/1.9781611975055.7) 2018 Proceedings of the Twentieth Workshop on Algorithm Engineering and Experiments (ALENEX). Society for Industrial and Applied Mathematics, 2018.

4. See also flowpaths [References](references.md), and the other papers cited by these works.

::: flowpaths.minflowdecomp