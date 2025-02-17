# Flow Papths Python Package

Usage example:

```python
def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.add_edge(0, 'a', flow=6)
    graph.add_edge(0, 'b', flow=7)
    graph.add_edge('a', 'b', flow=2)
    graph.add_edge('a', 'c', flow=4)
    graph.add_edge('b', 'c', flow=9)
    graph.add_edge('c', 'd', flow=6)
    graph.add_edge('c', 1, flow=7)
    graph.add_edge('d', 1, flow=6)
    
    # We create a Minimum Flow Decomposition solver with default settings
    mfd_model = mfd.MinFlowDecomp(graph, flow_attr='flow')
    
    # We solve it
    mfd_model.solve()

    # We process its solution
    process_solution(mfd_model)

    # We now set the weights of the solution paths to int
    mfd_model_int = mfd.MinFlowDecomp(graph, flow_attr='flow', weight_type=int)
    mfd_model_int.solve()
    process_solution(mfd_model_int)

    # We solver again, but using the `gurobi` solver, instead of the default `highs`. 
    # This requires the `gurobipy` package and a Gurobi license
    mfd_model_int_gurobi = mfd.MinFlowDecomp(graph, flow_attr='flow', weight_type=int)
    mfd_model_int_gurobi.solve()
    process_solution(mfd_model_int_gurobi)

    # We deactivate all optimizations
    mfd_model_slow = mfd.MinFlowDecomp(graph, flow_attr='flow', weight_type=int,
                                        optimize_with_safe_paths=False, 
                                        optimize_with_safe_sequences=False, 
                                        optimize_with_safe_zero_edges=False, 
                                        optimize_with_greedy=False)
    mfd_model_slow.solve()
    process_solution(mfd_model_slow)

def process_solution(model: mfd.MinFlowDecomp):
    if model.solved:
        solution = model.get_solution()
        print("Solution weights, paths, solve statistics: ", solution[1], solution[0], model.solve_statistics)
    else:
        print("Model could not be solved.")
```
