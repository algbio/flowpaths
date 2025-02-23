# The _flowpaths_ Python Package

This package implements various solvers for decomposing a weighted directed acyclic graph (DAG) into weighted paths, based on (Mixed) Integer Linear Programming ((M)ILP) formulations. It also supports the easy creation of solvers for new decomposition models.

### Design principles

1. **Easy to use**: You just pass a [networkx](https://networkx.org) graph to the solvers, and they return optimal weighted paths. See the [examples](examples/) folder for some usage examples. 
2. **It just works**: You do not need to install an (M)ILP solver. This is possible thanks to the open source solver [HiGHS](https://highs.dev), which gets installed once you install this package. 
    - If you have a [Gurobi](https://www.gurobi.com/solutions/gurobi-optimizer/) license ([free for academic users](https://www.gurobi.com/features/academic-named-user-license/)), you can install the [gurobipy Python package](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python), and then you can run the Gurobi solver instead of the default HiGHS solver by just passing a parameter. 

3. **Easy to implement other decomposition models**: We provide an abstract class modeling a generic path-finding MILP (`AbstractPathModelDAG`), which encodes a given number of arbitrary paths in the DAG. You can inherit from this class to add e.g. weights to the paths, and specify various constraints that these weighted paths must satisfy, or the objective function they need to minimize or maximize. See [this basic example solver](examples/inexact_flow_solver.py). This class interfaces with a wrapper for both MILP solvers, so you do not need to worry (much) about MILP technicalities. The decomposition solvers already implemented in this package use this class. See below another reason why. 

4. **Fast**: Having solvers implemented using `AbstractPathModelDAG` means that any optimization to the path-finding mechanisms benefit **all** solvers that ingerit from this class. We implement some "safety optimizations" described in [this paper](https://doi.org/10.48550/arXiv.2411.03871), based on ideas first introduced in [this paper](https://doi.org/10.4230/LIPIcs.SEA.2024.14), which can provide up to **1000x speedups**, depending on the graph instance.

### Models implemented:
- **Minimum Flow Decomposition**: Given a DAG with flow values on its edges (i.e. at every node different from source or sink the flow enetering the node is equal to the flow exiting the node), find the minimum number of weighted paths such that, for every edge, the sum of the weights of the paths going through the edge equals the flow value of the edge.
- **$k$-Least Absolute Errors**: Given a DAG with weights on its edges, and a number $k$, find $k$ weighted paths such that the sum of the absolute errors of each edge is minimized. 
    - The *error of an edge* is defined as the weight of the edge minus the sum of the weights of the paths going through it.
- **$k$-Minimum Path Error**: Given a DAG with weights on its edges, and a number $k$, find $k$ weighted paths, with associated *slack* values, such that:
    - The error of each edge (defined as in $k$-Least Absolute Errors above) is at most the sum of the slacks of the paths going through the edge, and
    - The sum of path slacks is minimized.

### Usage example:

```python
import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("0", "a", flow=6)
    graph.add_edge("0", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "1", flow=7)
    graph.add_edge("d", "1", flow=6)

    # We create a Minimum Flow Decomposition solver with default settings,
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges.
    mfd_model = fp.MinFlowDecomp(graph, flow_attr="flow")

    # We solve it
    mfd_model.solve()

    # We process its solution
    process_solution(mfd_model)

    # We solve again, by deactivating all optimizations, and 
    # setting the weights of the solution paths to int
    mfd_model_slow = fp.MinFlowDecomp(
        graph,
        flow_attr="flow",
        weight_type=int,
        optimize_with_safe_paths=False,
        optimize_with_safe_sequences=False,
        optimize_with_safe_zero_edges=False,
        optimize_with_greedy=False,
    )
    mfd_model_slow.solve()
    process_solution(mfd_model_slow)


def process_solution(model: fp.MinFlowDecomp):
    if model.is_solved:
        solution = model.get_solution()
        print(
            "Solution weights, paths, solve statistics: ",
            solution[1],
            solution[0],
            model.solve_statistics,
        )
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()
```
