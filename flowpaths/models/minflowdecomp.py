import time
import networkx as nx
import stdigraph
from . import genericdagmodel as dagmodel
from . import kflowdecomp as kflowdecomp    

class MinFlowDecomp:
    def __init__(self, G: nx.DiGraph, flow_attr: str, weight_type: type = int, \
                subpath_constraints: list = [], \
                optimize_with_safe_paths: bool = True, \
                optimize_with_safe_sequences: bool = False, \
                optimize_with_safe_zero_edges: bool = False, \
                optimize_with_greedy: bool = True, \
                threads: int = 4, \
                time_limit: int = 300, \
                presolve = "on", \
                log_to_console = "false", \
                external_solver = "highs"):
        """
        Initialize the Minimum Flow Decompostion model, minimizing the number of paths.

        Parameters
        ----------
        - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
        - flow_attr (str): The attribute name from where to get the flow values on the edges.
        - weight_type (type, optional): The type of weights (int or float). Default is int.
        - subpath_constraints (list, optional): List of subpath constraints. Default is an empty list.
        - optimize_with_safe_paths (bool, optional): Whether to optimize with safe paths. Default is True.
        - optimize_with_safe_sequences (bool, optional): Whether to optimize with safe sequences. Default is False.
        - optimize_with_safe_zero_edges (bool, optional): Whether to optimize with safe zero edges. Default is False.
        - optimize_with_greedy (bool, optional): Whether to optimize with a greedy algorithm. Default is True. 
            If set to True, the model will first try to solve the problem with a greedy algorithm based on 
            always removing the path of maximum bottleneck. If the size of such greedy decomposition matches the width of the graph,
            the greedy decomposition is optimal, and the model will return the greedy decomposition as the solution. 
            If the greedy decomposition does not match the width, then the model will proceed to solve the problem with the MILP model.
        - threads (int, optional): Number of threads to use. Default is 4.
        - time_limit (int, optional): Time limit for the solver in seconds. Default is 300.
        - presolve (str, optional): Presolve option for the solver. Default is "on".
        - log_to_console (str, optional): Whether to log solver output to console. Default is "false".
        - external_solver (str, optional): External solver to use. Default is "highs".
        
        Raises
        ----------
        - ValueError: If weight_type is not int or float.
        - ValueError: If some edge does not have the flow attribute specified as "flow_attr".
        - ValueError: If the graph does not satisfy flow conservation on nodes different from source or sink.
        - ValueError: If the graph contains edges with negative (<0) flow values.
        - ValueError: If the graph is not acyclic.
        """
        
        stG = stdigraph.stDiGraph(G)
        self.lowerbound = stG.get_width()

        self.G = G
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.subpath_constraints = subpath_constraints
        self.optimize_with_safe_paths = optimize_with_safe_paths
        self.optimize_with_safe_sequences = optimize_with_safe_sequences
        self.optimize_with_safe_zero_edges = optimize_with_safe_zero_edges
        self.optimize_with_greedy = optimize_with_greedy
        self.threads = threads
        self.time_limit = time_limit
        self.presolve = presolve
        self.log_to_console = log_to_console
        self.solve_statistics = {}
        self.solution = None
        self.solved = False
        self.external_solver = external_solver

    def solve(self) -> bool:
        """
        Attempts to solve the flow distribution problem using a model with varying number of paths.

        This method iterates over a range of possible path counts, creating and solving a flow decompostion model for each count.
        If a solution is found, it stores the solution and relevant statistics, and returns True. If no solution is found after
        iterating through all possible path counts, it returns False.

        Returns:
            bool: True if a solution is found, False otherwise.
        """
        start_time = time.time()
        for i in range(self.lowerbound, self.G.number_of_edges()):
            fd_model = kflowdecomp.kFlowDecomp(G = self.G, flow_attr = self.flow_attr, num_paths = i, weight_type = self.weight_type, \
                subpath_constraints = self.subpath_constraints, \
                optimize_with_safe_paths = self.optimize_with_safe_paths, \
                optimize_with_safe_sequences = self.optimize_with_safe_sequences, \
                optimize_with_safe_zero_edges = self.optimize_with_safe_zero_edges, \
                optimize_with_greedy = self.optimize_with_greedy, \
                threads = self.threads, \
                time_limit = self.time_limit, \
                presolve = self.presolve, \
                log_to_console = self.log_to_console, \
                external_solver = self.external_solver)
            
            fd_model.solve()

            if fd_model.solved:
                self.solution = fd_model.get_solution()
                self.solved = True
                self.solve_statistics = fd_model.solve_statistics
                self.solve_statistics["mfd_solve_time"] = time.time() - start_time
                return True
        return False
    
    def get_solution(self):
        
        self.check_solved()
        return self.solution
    
    def check_solved(self):       
        if not self.solved or self.solution is None:
            raise Exception("Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit.")



