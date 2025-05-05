import time
import copy
import networkx as nx
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils as utils
import flowpaths.utils.solverwrapper as sw
import flowpaths.stdigraph as stdigraph
import flowpaths.kpathcover as kpathcover

class MinPathCover(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        edge_length_attr: str = None,
        edges_to_ignore: list = [],
        optimization_options: dict = {},
        solver_options: dict = {},
    ):
        """
        This class finds a minimum number of paths covering the edges of a directed acyclic graph (DAG) -- and generalizations of this problem, see the parameters below.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed acyclic graph, as networkx DiGraph.

        - `subpath_constraints : list`, optional
            
            List of subpath constraints. Default is an empty list. 
            Each subpath constraint is a list of edges that must be covered by some solution path, according 
            to the `subpath_constraints_coverage` or `subpath_constraints_coverage_length` parameters (see below).

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

        - `edges_to_ignore : list`, optional

            List of edges to ignore when adding constrains on flow explanation by the weighted paths.
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `optimization_options : dict`, optional
            
            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

        """

        self.G = G

        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr
        self.edges_to_ignore = edges_to_ignore
        

        self.__solution = None
        self.__lowerbound_k = None
        self.__is_solved = None
        self.model = None
        
        self.solve_statistics = {}
        self.optimization_options = optimization_options
        self.solver_options = solver_options
        self.time_limit = self.solver_options.get("time_limit", sw.SolverWrapper.time_limit)
        self.solve_time_start = None

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}")

    def solve(self) -> bool:

        self.solve_time_start = time.perf_counter()
        
        for i in range(self.get_lowerbound_k(), self.G.number_of_edges()):
            utils.logger.info(f"{__name__}: iteration with k = {i}")

            i_solver_options = copy.deepcopy(self.solver_options)
            if "time_limit" in i_solver_options:
                i_solver_options["time_limit"] = self.time_limit - self.solve_time_elapsed

            model = kpathcover.kPathCover(
                        G=self.G,
                        k=i,
                        subpath_constraints=self.subpath_constraints,
                        subpath_constraints_coverage=self.subpath_constraints_coverage,
                        subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                        edge_length_attr=self.edge_length_attr,
                        edges_to_ignore=self.edges_to_ignore,
                        optimization_options=self.optimization_options,
                        solver_options=i_solver_options,
                    )
            model.solve()

            if model.is_solved():
                self.__solution = model.get_solution()
                self.set_solved()
                self.solve_statistics = model.solve_statistics
                self.solve_statistics["mpc_solve_time"] = time.perf_counter() - self.solve_time_start
                self.model = model
                return True
            elif model.solver.get_model_status() != sw.SolverWrapper.infeasible_status:
                # If the model is not solved and the status is not infeasible,
                # it means that the solver stopped because of an unexpected termination,
                # thus we cannot conclude that the model is infeasible.
                # In this case, we stop the search.
                return False
            
        return False
    
    @property
    def solve_time_elapsed(self):
        """
        Returns the elapsed time since the start of the solve process.

        Returns
        -------
        - `float`
        
            The elapsed time in seconds.
        """
        return time.perf_counter() - self.solve_time_start if self.solve_time_start is not None else None

    def get_solution(self):
        """
        Get the solution of the Min Path Cover model, as dict with unique key `"paths"`.
        """
        self.check_is_solved()
        return self.__solution
    
    def get_objective_value(self):

        self.check_is_solved()

        # Number of paths
        return len(self.__solution["paths"])

    def is_valid_solution(self) -> bool:
        return self.model.is_valid_solution()
    
    def get_lowerbound_k(self):

        if self.__lowerbound_k is None:
            stG = stdigraph.stDiGraph(self.G)
            self.__lowerbound_k = stG.get_width(edges_to_ignore=self.edges_to_ignore)

        return self.__lowerbound_k