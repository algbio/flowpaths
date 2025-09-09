import time
import math
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.kflowdecomp as kflowdecomp
import flowpaths.abstractpathmodeldag as pathmodel
import numpy as np

class SparseFlowDecomp(pathmodel.AbstractPathModelDAG): # Note that we inherit from AbstractPathModelDAG to be able to use this class to also compute safe paths,
    """
    Class to decompose an exact or inexact flow into a small number of weighted paths
    """
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        weight_type: type = float,
        edge_length_attr: str = None,
        optimization_options: dict = None,
        solver_options: dict = None,
    ):
        """
        Initialize the Sparse Flow Decomposition model, minimizing the reconstruction error.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed acyclic graph, as networkx DiGraph.

        - `flow_attr : str`
            
            The attribute name from where to get the flow values on the edges.

        - `weight_type : type`, optional
            
            The type of weights (`int` or `float`). Default is `float`.

        - `optimization_options : dict`, optional
            
            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

        Raises
        ------
        `ValueError`

        - If `weight_type` is not `int` or `float`.
        - If some edge does not have the flow attribute specified as `flow_attr`.
        - If the graph contains edges with negative (<0) flow values.
        - If the graph is not acyclic.
        """

        self.G = G
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.solver_options = solver_options

        self.solve_statistics = {}
        self.__solution = None
        self.__lowerbound = None

    def solve(self) -> bool:
        """
        Attempts to solve the sparse flow decomposition problem using a model with a varying number of paths, using the blended pairwise conditional gradients (BPCG) algorithm.

        This method iterates over a range of possible path counts, creating and solving a flow decompostion model for each count.
        If a solution is found, it stores the solution and relevant statistics, and returns True. If no solution is found after
        iterating through all possible path counts, it returns False.

        Returns:
            bool: True if a solution is found, False otherwise.

        Note:
            This overloads the `solve()` method from `AbstractPathModelDAG` class.
        """
        start_time = time.time()
        
        v0 = nx SHORTEST PATH
        path_set = [v0]
        path_weights = [1.0]
        x = ... sparse copy of v0
        flow_squared_norm = dot(flow_vector, flow_vector)
        for t in range(self.solver_options["max_iteration"]):
            # checking time limit
            time_iter = time.time()
            if time_iter - start_time > get(self.solver_options, "timeout", math.inf):
                break
            dot_x_flow = dot(x, flow)
            grad = x - dot_x_flow * flow_vector / flow_squared_norm
            v = nx SHORTEST PATH
            fw_gap = dot(grad, x - v)
            if fw_gap <= self.solver_options["epsilon"]:
                break
            vmin, weight_min, idx_min, dot_min, vmax, weight_max, idx_max, dot_max = find_min_max_vertices(path_weights, path_set, grad)
            local_gap = dot_max - dot_min
            if 2 * local_gap >= fw_gap:
                # local step
                descent_direction = vmax - vmin
                gamma_max = weight_max
                gamma = self._compute_step_size(descent_direction, gamma_max)
                x = x - gamma * descent_direction
                path_weights[idx_min] += gamma
                if gamma >= gamma_max:
                    # drop vertex
                else:
                    path_weights[idx_max] -= gamma
            else:
                # FW step
                descent_direction = x - v
                gamma_max = 1.0
                gamma = self._compute_step_size(descent_direction, gamma_max)
                x = x - gamma * descent_direction
                v_idx = None
                for i in range(len(path_set)):
                    if path_set[i] == v:
                        v_idx = i
                        break
                if v_idx != None:
                    path_weights[v_idx] += gamma
                    if path_weights[v_idx] >= 1.0:
                        # drop all vertices except the current one
                        path_weights = [path_weights[v_idx]]
                        path_set = [path_set[v_idx]]
                        x = 1.0 * v
                else:
                    if gamma < 1:
                        # add new vertex
                        for i in range(len(path_weights)):
                            path_weights[i] = (1 - gamma) * path_weights[i]
                        path_set.append(v)
                        path_weights.append(gamma)
                    else:
                        path_weights = [1.0]
                        path_set = [v]
                        x = 1.0 * v
            # avoid accumulation of numerical errors
            sw = sum(path_weights)
            if sw > 1 + FLOAT_EPSILON or sw < 1 - FLOAT_EPSILON:
                print(sum(path_weights))
                for i in range(len(path_weights)):
                    path_weights[i] /= sw
                    if path_weights[i] < 0:
                        path_weights[i] = 0
                x = sum(path_weights[i] * path_set[i] for i in range(len(path_weights)))
            






        return True

    def get_solution(self):
        """
        Retrieves the solution for the flow decomposition problem.

        Returns
        -------
        - `solution: dict`
        
            A dictionary containing the solution paths (key `"paths"`), their corresponding weights (key `"weights"`), and the reconstruction error (key `"loss"`).

        Raises
        -------
        - `exception` If model is not solved.
        """
        self.check_is_solved()
        return self.__solution
    
    def get_objective_value(self):

        self.check_is_solved()

        # Number of paths
        return self.__solution["loss"]

    def is_valid_solution(self) -> bool:
        return self.fd_model.is_valid_solution()
    
    def get_lowerbound_k(self):

        if self.__lowerbound != None:
            return self.__lowerbound
        
        stG = stdigraph.stDiGraph(self.G)
        self.__lowerbound = stG.get_width()

        return self.__lowerbound

    def draw_solution(self, show_flow_attr=True):
        # TODO necessary?
        # self.fd_model.draw_solution(show_flow_attr)

    # constructs a sparse incidence vector from the list of vector indices produced by nx    
    def _pathindex_to_sparsevec(G, path_index):
        nedges = G.number_of_edges()
        assert sorted(path_index) == path_index
        v = scipy.sparse.dok_array((nedges,), dtype=int)
        for (e_idx, e) in enumerate(G.edges):
            if e[0] in path_index:
                idx = path_index.index(e[0])
                if idx < len(path_index) - 1 and path_index[idx + 1] == e[1]:
                    v[e_idx] = 1
        return v
    
    def _compute_extreme_point(G, direction, src, dst):
        # TODO set edge weights in an attribute or define a weight function
        path_index = nx.shortest_paths.bellman_ford_path(G, src, dst)
        return _pathindex_to_sparsevec(G, path_index)


