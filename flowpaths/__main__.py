import minflowdecomp as mfd
from utils import graphutils

# Run as `python __main__.py` in the `flowpaths` directory

def main():
    # Example usage of the MinFlowDecomp class
    graphs = graphutils.read_graphs("./tests/tests.graph")
    for graph in graphs:
        print("Testing graph: ", graph.graph['id'])
        mfd_model = mfd.MinFlowDecomp(graph, flow_attr='flow', weight_type=float, 
                                    optimize_with_safe_paths=True, 
                                    optimize_with_safe_sequences=False, 
                                    optimize_with_safe_zero_edges=False, 
                                    optimize_with_greedy=False, 
                                    external_solver="gurobi")
        mfd_model.solve()
        if mfd_model.solved:
            print("Model solved successfully!")
            # print("Solution: ", mfd_model.get_solution())
            print("Solution: ", mfd_model.solve_statistics)
        else:
            print("Model could not be solved.")

if __name__ == "__main__":
    main()