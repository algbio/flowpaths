import networkx as nx
import graphutils
import mfd

# Example usage
if __name__ == "__main__":

    graphs = graphutils.read_graphs("./flowpaths/tests.graph")

    for base_graph in graphs:

        mfd_model_G = mfd.modelMFD(base_graph, flow_attr='flow', weight_type=float, \
                                   optimize_with_safe_paths=False, \
                                   optimize_with_safe_sequences=True, \
                                   optimize_with_safe_zero_edges=True, \
                                   optimize_with_greedy=False, \
                                   presolve = "on", \
                                   external_solver = "highs")
        mfd_model_G.solve()
        if mfd_model_G.solved:
            (paths, weights) = mfd_model_G.get_solution()
            print("MFD solution:")
            # print(weights)
            # print(paths)
            print(mfd_model_G.solve_statistics)
        else:
            print("Model not solved")



        
        