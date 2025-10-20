import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.add_edge("s", "a")
    graph.add_edge("s", "b")
    graph.add_edge("a", "b")
    graph.add_edge("a", "c")
    graph.add_edge("b", "c")
    graph.add_edge("c", "d")
    graph.add_edge("c", "t")
    graph.add_edge("d", "t")

    mpc_model = fp.MinPathCover(graph)
    mpc_model.solve()

    subpath_constraints=[[("a", "c"),("c", "t")]]

    mpc_model_sc = fp.MinPathCover(
        graph,
        subpath_constraints=subpath_constraints,
    )
    mpc_model_sc.solve()
    process_solution(mpc_model_sc)

def process_solution(model: fp.MinFlowDecomp):
    if model.is_solved():
        print(model.get_solution())
        print(model.solve_statistics)
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()