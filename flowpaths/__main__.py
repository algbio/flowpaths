import networkx as nx
from enum import Enum
import stDiGraph as graph
import safety
import graphutils
import mfd

class PathModel(Enum):
    FlowDecomposition = "FlowDecomposition"
    InexactFlowDecomposition = "InexactFlowDecomposition"
    MinPathError = "MinPathError"
    LeastSquares = "LeastSquares"

class ILPSolver(Enum):
    HiGHS = "HiGHS"
    Gurobi = "Gurobi"

class ILPSolver(Enum):
    HiGHS = "HiGHS"
    Gurobi = "Gurobi"

class SolveMode(Enum):
    ''' 
    For FlowDecomposition and InexactFlowDecomposition, this is the MFD size,
    For MinPathError, this is the edge width of the graph
    '''
    MinNumber = "MinNumber"
    GivenNumber = "GivenNumber"

class PathSolver:
    def __init__(self, graph: nx.DiGraph, model: PathModel, **kwargs):
        self.graph = graph
        self.model = model
        self.params = {}
        self.set_parameters(**kwargs)

    def solve(self):
        # Implement the main algorithm here
        # pass
        print("Solving using the {} model".format(self.model.value))

    def set_parameters(self, **kwargs):
        self.params.update(kwargs)
        self.model      = self.params.get('model', PathModel.MinPathError)
        self.threads    = self.params.get('threads', 4)
        self.timeout    = self.params.get('timeout', 180)
        self.ilp_solver = self.params.get('ilp_solver', ILPSolver.HiGHS)
        self.solve_mode = self.params.get('solve_mode', SolveMode.MinNumber)
        
        if self.solve_mode == SolveMode.GivenNumber:
            if 'k' not in self.params:
                raise ValueError("k must be specified for SolveMode.GivenNumber")
            else:    
                self.k = self.params['k']

    def get_solution(self):
        # Return the solution in the desired format
        return self.graph.nodes

# # Example usage
# if __name__ == "__main__":
#     G = nx.gnp_random_graph(10, 0.15, directed=True)
#     solver = PathSolver(G, model=PathModel.FlowDecomposition, solve_mode=SolveMode.MinNumber)
#     solver.solve()
#     solution = solver.get_solution()
#     print(solution)
#     solver.set_parameters(model=PathModel.LeastSquares)
#     solver.solve()

# Example usage
if __name__ == "__main__":
    # base_graph = nx.DiGraph()
    # base_graph.add_edge(1, 2, flow=10)
    # base_graph.add_edge(2, 3, flow=5)
    # base_graph.add_edge(2, 2.5, flow=5)
    # base_graph.add_edge(2.5, 3, flow=5)
    # base_graph.add_edge(3, 4, flow=15)

    graphs = graphutils.read_graphs("./flowpaths/tests.graph")

    for base_graph in graphs:
        G = graph.stDiGraph(base_graph)
        
        print("Nodes:", G.nodes())
        print("Edges:", G.edges(data=True))
        print("Width:", G.width)
        # print("Source edges:", G.source_edges)
        # print("Sink edges:", G.sink_edges)
        # print("Edge antichain:", G.edge_antichain)

        # print("Safe paths of G:", safety.safe_paths_of_base_edges(G, no_duplicates=True))
        # print("Safe seqeunces of G:", safety.safe_sequences_of_base_edges(G, no_duplicates=True))

        mfd_model_G = mfd.modelMFD(base_graph, num_paths=15, flow_attr='flow', weight_type=float, \
                                   optimize_with_safe_paths=False, \
                                   optimize_with_safe_sequences=True, \
                                   presolve = "on")
        mfd_model_G.solve()
        if mfd_model_G.solved:
            (paths, weights) = mfd_model_G.get_solution()
            print("MFD solution:")
            print(weights)
            print(paths)
            print(mfd_model_G.solve_statistics)
            print("Is correct solution", mfd_model_G.check_solution())
            print("Max bottleneck decomposition size: ", len(mfd_model_G.decompose_using_max_bottleck()[1]))
        else:
            print("Model not solved")



        
        