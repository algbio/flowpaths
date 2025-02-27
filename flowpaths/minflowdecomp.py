import time
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.kflowdecomp as kflowdecomp
import flowpaths.abstractpathmodeldag as pathmodel

class MinFlowDecomp(pathmodel.AbstractPathModelDAG): # Note that we inherit from AbstractPathModelDAG to be able to use this class to also compute safe paths, 
    """
    Class to decompose a flow into a minimum number of weighted paths.
    """
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        weight_type: type = float,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        edge_length_attr: str = None,
        optimization_options: dict = None,
        solver_options: dict = None,
    ):
        """
        Initialize the Minimum Flow Decomposition model, minimizing the number of paths.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed acyclic graph, as networkx DiGraph.

        - `flow_attr : str`
            
            The attribute name from where to get the flow values on the edges.

        - `weight_type : type`, optional
            
            The type of weights (`int` or `float`). Default is `float`.

        - `subpath_constraints : list`, optional
            
            List of subpath constraints. Default is an empty list. See [subpath constraints documentation](subpath-constraints.md)

        - `subpath_constraints_coverage : float`, optional
            
            Coverage fraction of the subpath constraints that must be covered by some solution paths. 
            
            Defaults to `1.0` (meaning that 100% of the edges of the constraint need to be covered by some solution path). See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `subpath_constraints_coverage_length : float`, optional
            
            Coverage length of the subpath constraints. Default is `None`. If set, this overrides `subpath_constraints_coverage`, 
            and the coverage constraint is expressed in terms of the subpath constraint length. 
            `subpath_constraints_coverage_length` is then the fraction of the total length of the constraint (specified via `edge_length_attr`) needs to appear in some solution path.
            See [subpath constraints documentation](subpath-constraints.md#3-relaxing-the-constraint-coverage)

        - `edge_length_attr : str`, optional
            
            Attribute name for edge lengths. Default is `None`.

        - `**kwargs : dict`
            
            Additional keyword arguments.

        Raises
        ------
        `ValueError`

        - If `weight_type` is not `int` or `float`.
        - If some edge does not have the flow attribute specified as `flow_attr`.
        - If the graph does not satisfy flow conservation on nodes different from source or sink.
        - If the graph contains edges with negative (<0) flow values.
        - If the graph is not acyclic.
        """

        stG = stdigraph.stDiGraph(G)
        self.lowerbound = stG.get_width()

        self.G = G
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr
        self.optimization_options = optimization_options
        self.solver_options = solver_options

        self.solve_statistics = {}
        self.__solution = None

    def solve(self) -> bool:
        """
        Attempts to solve the flow distribution problem using a model with varying number of paths.

        This method iterates over a range of possible path counts, creating and solving a flow decompostion model for each count.
        If a solution is found, it stores the solution and relevant statistics, and returns True. If no solution is found after
        iterating through all possible path counts, it returns False.

        Returns:
            bool: True if a solution is found, False otherwise.

        Note:
            This overloads the `solve()` method from `AbstractPathModelDAG` class.
        """
        start_time = time.time()
        for i in range(self.lowerbound, self.G.number_of_edges()):
            fd_model = kflowdecomp.kFlowDecomp(
                G=self.G,
                flow_attr=self.flow_attr,
                num_paths=i,
                weight_type=self.weight_type,
                subpath_constraints=self.subpath_constraints,
                subpath_constraints_coverage=self.subpath_constraints_coverage,
                subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                edge_length_attr=self.edge_length_attr,
                optimization_options=self.optimization_options,
                solver_options=self.solver_options,
            )

            fd_model.solve()

            if fd_model.is_solved():
                self.__solution = fd_model.get_solution()
                self.set_solved()
                self.solve_statistics = fd_model.solve_statistics
                self.solve_statistics["mfd_solve_time"] = time.time() - start_time

                # storing the fd_model object for further analysis
                self.fd_model = fd_model
                return True
        return False

    def get_solution(self):

        self.check_is_solved()
        return self.__solution
    
    def get_objective_value(self):

        self.check_is_solved()

        # Number of paths
        return len(self.__solution[0])

    def is_valid_solution(self) -> bool:
        return self.fd_model.is_valid_solution()

    def draw_solution(self, show_flow_attr=True):
        self.fd_model.draw_solution(show_flow_attr)
