[![PyPI - Version](https://img.shields.io/pypi/v/flowpaths)](https://pypi.org/project/flowpaths/)
[![License - MIT](https://img.shields.io/pypi/l/flowpaths)](https://github.com/algbio/flowpaths/blob/main/LICENSE)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/algbio/flowpaths/dx3-tests.yml)](https://github.com/algbio/flowpaths/actions/workflows/dx3-tests.yml)

#  The _flowpaths_ Python Package

This package implements various solvers for decomposing a weighted directed acyclic graph (DAG) into weighted paths, based on (Mixed) Integer Linear Programming ((M)ILP) formulations. It also supports the easy creation of solvers for new decomposition models.

![Overview](https://raw.githubusercontent.com/algbio/flowpaths/main/docs/overview.png)

### Installation

```bash
pip install flowpaths
```

### Documentation

The documentation of this package is currently being written at [algbio.github.io/flowpaths/](https://algbio.github.io/flowpaths/).

### Basic usage example:

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

### Design principles

1. **Easy to use**: You just pass a directed graph to the solvers (as a [networkx](https://networkx.org) [DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html)), and they return optimal weighted paths. See the [examples](examples/) folder for some usage examples.
 
2. **It just works**: You do not need to install an (M)ILP solver. This is possible thanks to the fast open source solver [HiGHS](https://highs.dev), which gets installed once you install this package. 
    - If you have a [Gurobi](https://www.gurobi.com/solutions/gurobi-optimizer/) license ([free for academic users](https://www.gurobi.com/features/academic-named-user-license/)), you can install the [gurobipy Python package](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python), and then you can run the Gurobi solver instead of the default HiGHS solver by just passing the entry `"external_solver": "gurobi"` in the `solver_options` dictionary.

3. **Easy to implement other decomposition models**: We provide an abstract class modeling a generic path-finding MILP (`AbstractPathModelDAG`), which encodes a given number of arbitrary paths in the DAG. You can inherit from this class to add e.g. weights to the paths, and specify various constraints that these weighted paths must satisfy, or the objective function they need to minimize or maximize. See [a basic example](examples/inexact_flow_solver.py) of a solver implemented in this manner. This abstract class interfaces with a wrapper for both MILP solvers, so you do not need to worry about MILP technicalities. The decomposition solvers already implemented in this package use this wrapper.

4. **Fast**: Having solvers implemented using `AbstractPathModelDAG` means that any optimization to the path-finding mechanisms benefits **all** solvers that inherit from this class. We implement some "safety optimizations" described in [this paper](https://doi.org/10.48550/arXiv.2411.03871), based on ideas first introduced in [this paper](https://doi.org/10.4230/LIPIcs.SEA.2024.14), which can provide up to **1000x speedups**, depending on the graph instance, while preserving global optimality (under some simple assumptions).

### Models currently implemented:
- [**Minimum Flow Decomposition**](https://algbio.github.io/flowpaths/minimum-flow-decomposition.html): Given a DAG with flow values on its edges (i.e. at every node different from source or sink the flow enetering the node is equal to the flow exiting the node), find the minimum number of weighted paths such that, for every edge, the sum of the weights of the paths going through the edge equals the flow value of the edge.
- [**$k$-Least Absolute Errors**](https://algbio.github.io/flowpaths/k-least-absolute-errors.html): Given a DAG with weights on its edges, and a number $k$, find $k$ weighted paths such that the sum of the absolute errors of each edge is minimized. 
    - The *error of an edge* is defined as the weight of the edge minus the sum of the weights of the paths going through it.
- [**$k$-Minimum Path Error**](https://algbio.github.io/flowpaths/k-min-path-error.html): Given a DAG with weights on its edges, and a number $k$, find $k$ weighted paths, with associated *slack* values, such that:
    - The error of each edge (defined as in $k$-Least Absolute Errors above) is at most the sum of the slacks of the paths going through the edge, and
    - The sum of path slacks is minimized.
