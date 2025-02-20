# Flow Paths Python Package

Usage example:

```python
import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge(0, "a", flow=6)
    graph.add_edge(0, "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", 1, flow=7)
    graph.add_edge("d", 1, flow=6)

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
    if model.solved:
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
