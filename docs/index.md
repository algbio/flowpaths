#  ![](flowpaths-logo.svg){: style="height:30px"} _flowpaths_ Python Package

This package implements solvers for decomposing weighted directed graphs into weighted paths or walks, based on (Mixed) Integer Linear Programming ((M)ILP) formulations. It supports both acyclic graphs (DAGs, decomposed into paths) and general graphs with cycles (decomposed into walks), and makes it easy to create new decomposition models. The current version **{{flowpaths_version_pyproject()}}**.

![Overview](https://raw.githubusercontent.com/algbio/flowpaths/main/docs/overview.png)

### Installation

```bash
pip install flowpaths
```

### Documentation

The documentation is available at [algbio.github.io/flowpaths/](https://algbio.github.io/flowpaths/).

### Requirements

- Python >= 3.8
- Dependencies installed automatically: networkx, highspy, graphviz, numpy
- Optional: gurobipy (to use Gurobi instead of the default HiGHS)

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

# A tiny graph with a cycle and conserved flow
G = nx.DiGraph()
G.add_edge("s", "a", flow=1)
G.add_edge("a", "b", flow=2)  # part of a cycle
G.add_edge("b", "a", flow=2)  # part of a cycle
G.add_edge("a", "t", flow=1)

mfd_cycles = fp.MinFlowDecompCycles(G, flow_attr="flow")
mfd_cycles.solve()
if mfd_cycles.is_solved():
    print(mfd_cycles.get_solution())
    # {'walks': [['s', 'a', 'b', 'a', 'b', 'a', 't']], 'weights': [1]}
```

### Design principles

1. **Easy to use**: You pass a directed graph (as a [networkx](https://networkx.org) [DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html)), and the solvers return optimal weighted paths (or walks for cyclic models). See the [examples](examples/) folder.
 
2. **It just works**: You do not need to install an (M)ILP solver. This is possible thanks to the fast open source solver [HiGHS](https://highs.dev), which gets installed once you install this package. 
    - If you have a [Gurobi](https://www.gurobi.com/solutions/gurobi-optimizer/) license ([free for academic users](https://www.gurobi.com/features/academic-named-user-license/)), you can install the [gurobipy Python package](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python), and then you can run the Gurobi solver instead of the default HiGHS solver by just passing the entry `"external_solver": "gurobi"` in the `solver_options` dictionary.

3. **Easy to implement other decomposition models**: 
    - For DAGs, use the abstract class `AbstractPathModelDAG`, which encodes a given number of paths. See docs: [Abstract Path Model](https://algbio.github.io/flowpaths/abstract-path-model/).
    - For general directed graphs with cycles, use `AbstractWalkModelDiGraph`, which encodes a given number of walks. See docs: [Abstract Walk Model](https://algbio.github.io/flowpaths/abstract-walk-model/).
    
    You can inherit from these classes to add weights and model-specific constraints/objectives. See [a basic example](examples/inexact_flow_solver.py). These abstract classes interface with a wrapper for popular MILP solvers, so you don't need to worry about solver-specific details.

4. **Fast**: Having solvers implemented using `AbstractPathModelDAG` means that any optimization to the path-finding mechanisms benefits **all** solvers that inherit from this class. We implement some "safety optimizations" described in [this paper](https://doi.org/10.48550/arXiv.2411.03871), based on ideas first introduced in [this paper](https://doi.org/10.4230/LIPIcs.SEA.2024.14), which can provide up to **1000x speedups**, depending on the graph instance, while preserving global optimality (under some simple assumptions).

5. **Flexible inputs**: Graphs with flows/weights on either edges or nodes are supported; see [Handling graphs with flows / weights on nodes](node-expanded-digraph.md).

### Models currently implemented
- [**Minimum Flow Decomposition**](minimum-flow-decomposition.md): Given a DAG with flow values on its edges (i.e. at every node different from source or sink the flow enetering the node is equal to the flow exiting the node), find the minimum number of weighted paths such that, for every edge, the sum of the weights of the paths going through the edge equals the flow value of the edge.
    
- [**$k$-Least Absolute Errors**](k-least-absolute-errors.md): Given a DAG with weights on its edges, and a number $k$, find $k$ weighted paths such that the sum of the absolute errors of each edge is minimized. 
    - The *error of an edge* is defined as the weight of the edge minus the sum of the weights of the paths going through it.
- [**$k$-Minimum Path Error**](k-min-path-error.md): Given a DAG with weights on its edges, and a number $k$, find $k$ weighted paths, with associated *slack* values, such that:
    - The error of each edge (defined as in $k$-Least Absolute Errors above) is at most the sum of the slacks of the paths going through the edge, and
    - The sum of path slacks is minimized.

Models for general directed graphs (with cycles), decomposed into walks:

- [**Minimum Flow Decomposition (cycles)**](minimum-flow-decomposition-cycles.md): Given a directed graph with conserved flow on edges and allowed start/end node sets, find the minimum number of weighted walks whose edgewise weights sum to the flow.
- [**$k$-Flow Decomposition (cycles)**](k-flow-decomposition-cycles.md): Given a directed graph with conserved flow and an integer $k$, find a decomposition of the flow into $k$ weighted walks.
- [**$k$-Least Absolute Errors (cycles)**](k-least-absolute-errors-cycles.md): Given a directed graph with arbitrary non-negative edge weights and an integer $k$, find $k$ weighted walks minimizing the sum of absolute edge errors (with options for ignoring/scaling edges and subpath constraints).
- [**$k$-Minimum Path Error (cycles)**](k-min-path-error-cycles.md): Given a directed graph with arbitrary non-negative edge weights and an integer $k$, find $k$ weighted walks with slacks that bound per-edge errors and minimize the sum of slacks.


### Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](contributing.md) guide for how to set up a dev environment, run tests locally, and build/preview the documentation with MkDocs.