# Minimum Correction of Weights to a Flow

Often, the edge weights of a graph are not a flow (i.e. do not satisfy flow conservation for non- source/sink nodes). While the models [k-Minimum Path Error](k-min-path-error.md) or [k-Least Absolute Errors](k-least-absolute-errors.md) can decompose such graphs, as a less principled approach, one can first minimally correct the graph weights to become a flow, and then optimally decompose the resulting flow flow using the [Minimum Flow Decomposition](minimum-flow-decomposition.md) model. 

This is faster in practice, because the Minimum Flow Decomposition solver is faster than the ones decomposing graphs without flow conservation. In some sense, we are delegating error correction to a pre-processing step, and then remove the error-resolution when decomposing the resulting graph.

## 1. Definition

This class solves the following problem.

- **INPUT**: A directed graph $G = (V,E)$ with unique source $s$ and unique sink $t$, and a weight $w(u,v)$ for every edge $(u,v)$ of $G$. Weights do not necessarily satisfy flow conservation. 

- **OUTPUT**: A flow value $f(u,v)$ for every edge $(u,v) \in E$ satisfying the flow conservation property for all non- source/sink nodes:
$$
\sum_{(u,v) \in E} f(u,v) = \sum_{(v,u) \in E} f(v,u),~~\forall v \in (V \setminus \{ s,t\}),
$$
minimizing the sum of absolute errors:
$$
\sum_{(u,v) \in E}\Big|f(u,v) - w(u,v)\Big|.
$$

## 2. Examples

Let's consider the following weighted graph, whose weights do not satisfy flow conservation, because the edges shown in brown are erroneous.

``` mermaid
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|7| a
    a -->|2| b
    s -->|7| b
    a -->|4| c
    b -->|9| c
    c -->|7| d
    d -->|6| t
    c -->|7| t

    linkStyle 0,5 stroke:brown,stroke-width:3;
```

Let's then minimally correct its weights with default settings.

```python hl_lines="15 16"
import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=7)
graph.add_edge("s", "b", flow=7)
graph.add_edge("a", "b", flow=2)
graph.add_edge("a", "c", flow=4)
graph.add_edge("b", "c", flow=9)
graph.add_edge("c", "d", flow=7)
graph.add_edge("c", "t", flow=7)
graph.add_edge("d", "t", flow=6)

# We create a the Minimum Error Flow solver with default settings
correction_model = fp.MinErrorFlow(graph, flow_attr="flow")
correction_model.solve()
```

The resulting graph is below. The edges whose weights have been corrected are in green.

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

    linkStyle 0,5 stroke:green,stroke-width:3;
```

Once we have corrected the weights, we can get the corrected graph and e.g. apply the minimum flow decomposition model on it.

```python hl_lines="2 3"
if correction_model.is_solved():
    corrected_graph = correction_model.get_solution()["graph"]
    mfd_model = fp.MinFlowDecomp(corrected_graph, flow_attr="flow")
    mfd_model.solve()
    if mfd_model.is_solved():
        print(mfd_model.get_solution())
        # {'paths': [
        #   ['s', 'b', 'c', 't'], 
        #   ['s', 'a', 'c', 'd', 't'], 
        #   ['s', 'a', 'b', 'c', 'd', 't']], 
        # 'weights': [7.0, 4.0, 2.0]}
```

This gives the following paths.

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

## 3. Generalizations

This class implements a more general version, as follows:

1. The corrected flow can start/end not only in source/sink nodes, but also in given sets of start/end nodes (set parameters `additional_starts` and `additional_ends`). See also [Additional start/end nodes](additional-start-end-nodes.md).
2. The error can count only for a given subset $E' \subseteq E$ of the edges (set parameter `edges_to_ignore` to be $E \setminus E'$), 
3. One can also ensure some "sparsity" in the solution, meaning the total corrected flow exiting the source node is counts also in the minimization function, with a given multiplier $\lambda$ (see ref. [2]). If $\lambda = 0$, this has no effect.

!!! info "Generalized objective function"
    Formally, the objective function generalized as in 2. and 3. above is:
    $$
    \sum_{(u,v) \in E'}\Big|f(u,v) - w(u,v)\Big| + \lambda \sum_{(s,v) \in E} f(s,v).
    $$

## 4. References

1. Alexandru I. Tomescu, Anna Kuosmanen, Romeo Rizzi, Veli Mäkinen
[**A novel min-cost flow method for estimating transcript expression with RNA-Seq**](http://www.biomedcentral.com/1471-2105/14/S5/S15) BMC Bioinformatics 14(S-5), S15, 2013 [(preprint)](http://cs.helsinki.fi/u/tomescu/papers/RECOMB-Seq-2013.pdf)
2. Elsa Bernard, Laurent Jacob, Julien Mairal, Jean-Philippe Vert
[**Efficient RNA isoform identification and quantification from RNA-Seq data with network flows**](https://doi.org/10.1093/bioinformatics/btu317), Bioinformatics, Volume 30, Issue 17, September 2014, Pages 2447–2455

::: flowpaths.minerrorflow
