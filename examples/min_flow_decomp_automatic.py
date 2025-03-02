import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=6)
    graph.add_edge("s", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "t", flow=7)
    graph.add_edge("d", "t", flow=6)

    # We create a Minimum Flow Decomposition solver using the NumPathsOptimization class   
    mfd_model = fp.NumPathsOptimization(
        model_type = fp.kFlowDecomp,
        stop_on_first_feasible=True,
        G=graph, 
        flow_attr="flow",
        subpath_constraints=[[("a", "c"),("c", "t")]], 
        subpath_constraints_coverage=0.5, 
        optimization_options={"optimize_with_greedy": False}
        )
    
    mfd_model.solve()
    process_solution(mfd_model)

def process_solution(model: fp.kMinPathError):
    if model.is_solved():
        print(model.get_solution())
        print(model.solve_statistics)
        print("model.is_valid_solution()", model.is_valid_solution())
    else:
        print("Model could not be solved.")
        print(model.solve_statistics)

if __name__ == "__main__":
    main()