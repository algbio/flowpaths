#  ![](flowpaths-logo.svg){: style="height:30px"} _flowpaths_ Python Package

This package implements solvers for decomposing weighted directed graphs into weighted paths or walks, based on (Mixed) Integer Linear Programming ((M)ILP) formulations. It supports both acyclic graphs (DAGs, decomposed into paths) and general graphs with cycles (decomposed into walks), and makes it easy to create new decomposition models.

![Overview](https://raw.githubusercontent.com/algbio/flowpaths/main/docs/overview.png)

### Installation

```bash
pip install flowpaths
```

### Basic usage example

```python
import flowpaths as fp
import networkx as nx

# Create a simple graph
graph = nx.DiGraph()
graph.add_edge("s", "a", flow=2)
graph.add_edge("a", "t", flow=2)
graph.add_edge("s", "b", flow=5)
graph.add_edge("b", "t", flow=5)
# ...

# Create a Minimum Flow Decomposition solver
mfd_solver = fp.MinFlowDecomp(graph, flow_attr="flow") 

mfd_solver.solve() # We solve it

if mfd_solver.is_solved(): # We get the solution
    print(mfd_solver.get_solution())
    # {'paths': [['s', 'b', 't'], ['s', 'a', 't']], 'weights': [5, 2]}
```

For graphs with cycles, use the cyclic variants which return walks rather than simple paths:

```python
import flowpaths as fp
import networkx as nx

G = nx.DiGraph()
G.add_edge("s", "a", flow=1)
G.add_edge("a", "b", flow=2)  # part of a cycle
G.add_edge("b", "a", flow=2)  # part of a cycle
G.add_edge("a", "t", flow=1)

mfd_solver = fp.MinFlowDecompCycles(G, flow_attr="flow")
mfd_solver.solve()
if mfd_solver.is_solved():
    print(mfd_solver.get_solution())
    # {'walks': [['s', 'a', 'b', 'a', 'b', 'a', 't']], 'weights': [1]}
```

### Design principles

1. **Easy to use**: You pass a directed graph (as a [networkx](https://networkx.org) [DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html)), and the solvers return optimal weighted paths (or walks for cyclic models). See the [examples](examples/) folder.
 
2. **It just works**: You do not need to install an (M)ILP solver. This is possible thanks to the fast open source solver [HiGHS](https://highs.dev), which gets installed once you install this package. 
    - If you have a [Gurobi](https://www.gurobi.com/solutions/gurobi-optimizer/) license ([free for academic users](https://www.gurobi.com/features/academic-named-user-license/)), you can install the [gurobipy Python package](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python), and then you can run the Gurobi solver instead of the default HiGHS solver by just passing the entry `"external_solver": "gurobi"` in the `solver_options` dictionary.

3. **Easy to implement other decomposition models**: 
    - For DAGs, use the abstract class `AbstractPathModelDAG`, which encodes a given number of paths. See docs: [Abstract Path Model](https://algbio.github.io/flowpaths/abstract-path-model/).
    - For general directed graphs with cycles, use `AbstractWalkModelDiGraph`, which encodes a given number of walks. See docs: [Abstract Walk Model](https://algbio.github.io/flowpaths/abstract-walk-model/).
    
    You can inherit from these classes to add weights and model-specific constraints/objectives. See [a basic example](https://github.com/algbio/flowpaths/blob/main/examples/inexact_flow_solver.py). These abstract classes interface with a wrapper for popular MILP solvers, so you don't need to worry about solver-specific details.

4. **Fast**: Having solvers implemented using `AbstractPathModelDAG` means that any optimization to the path-finding mechanisms benefits **all** solvers that inherit from this class. We implement some "safety optimizations" described in [this paper](https://doi.org/10.48550/arXiv.2411.03871), based on ideas first introduced in [this paper](https://doi.org/10.4230/LIPIcs.SEA.2024.14), which can provide up to **1000x speedups**, depending on the graph instance, while preserving global optimality (under some simple assumptions).

5. **Flexible inputs**: The models support graphs with flows/weights on either edges or nodes, and additional real use-case input features, such as subpath or subset constraints.

### Models currently implemented
- [**Minimum Flow Decomposition**](https://algbio.github.io/flowpaths/minimum-flow-decomposition.html): Given a graph with flow values on its edges (i.e. at every node different from source or sink the flow entering the node is equal to the flow exiting the node), find the minimum number of weighted paths / walks such that, for every edge, the sum of the weights of the paths going through the edge equals the flow value of the edge.
    
- [**$k$-Least Absolute Errors**](https://algbio.github.io/flowpaths/k-least-absolute-errors.html): Given a graph with weights on its edges, and a number $k$, find $k$ weighted paths / walks such that the sum of the absolute errors of each edge is minimized. 
    - The *error of an edge* is defined as the weight of the edge minus the sum of the weights of the paths / walks going through it.
- [**$k$-Minimum Path Error**](https://algbio.github.io/flowpaths/k-min-path-error.html): Given a graph with weights on its edges, and a number $k$, find $k$ weighted paths / walks, with associated *slack* values, such that:
    - The error of each edge (defined as in $k$-Least Absolute Errors above) is at most the sum of the slacks of the paths / walks going through the edge, and
    - The sum of path / walk slacks is minimized.

### Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](contributing.md) guide for how to set up a dev environment, run tests locally, and build/preview the documentation with MkDocs.