import time
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.utils.graphutils as gu
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils.safetyflowdecomp as sfd
import flowpaths.utils as utils

class kPathCover(pathmodel.AbstractPathModelDAG):
    def __init__(
        self,
        G: nx.DiGraph,
        k: int,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        edge_length_attr: str = None,
        edges_to_ignore: list = [],
        optimization_options: dict = {},
        solver_options: dict = {},
    ):
        """
        This class finds, if possible, `k` paths covering the edges of a directed acyclic graph (DAG) -- and generalizations of this problem, see the parameters below.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed acyclic graph, as networkx DiGraph.

        - `k: int`
            
            The number of paths to decompose in.

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

        self.G = stdigraph.stDiGraph(G)
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore)

        self.k = k
        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr

        self.__solution = None
        self.__lowerbound_k = None
        
        self.solve_statistics = {}
        self.optimization_options = optimization_options
        self.optimization_options["trusted_edges_for_safety"] = set(e for e in self.G.edges() if e not in self.edges_to_ignore)

        # Call the constructor of the parent class AbstractPathModelDAG
        super().__init__(
            G=self.G, 
            k=self.k,
            subpath_constraints=self.subpath_constraints, 
            subpath_constraints_coverage=self.subpath_constraints_coverage, 
            subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
            edge_length_attr=self.edge_length_attr, 
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics,
        )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class to encode the path cover
        self.__encode_path_cover()

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def __encode_path_cover(self):
        
        subpath_constraint_edges = set()
        for subpath_constraint in self.subpath_constraints:
            for edge in zip(subpath_constraint[:-1], subpath_constraint[1:]):
                subpath_constraint_edges.add(edge)

        # We encode that for each edge (u,v), the sum of the weights of the paths going through the edge is equal to the flow value of the edge.
        for u, v in self.G.edges():
            if (u, v) in self.edges_to_ignore:
                continue
            if self.subpath_constraints_coverage == 1 and (u, v) in subpath_constraint_edges:
                continue
            
            # We require that  self.edge_vars[(u, v, i)] is 1 for at least one i
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.edge_vars[(u, v, i)]
                    for i in range(self.k)
                ) >= 1,
                name=f"cover_u={u}_v={v}",
            )

    def get_solution(self):
        """
        Retrieves the solution for the k-path cover problem.

        Returns
        -------
        - `solution: dict`
        
            A dictionary containing the solution paths, under key `"paths"`.

        Raises
        ------
        - `exception` If model is not solved.
        """

        if self.__solution is None:
            self.check_is_solved()
            self.__solution = {
                "paths": self.get_solution_paths(),
            }

        return self.__solution

    def is_valid_solution(self, tolerance=0.001):
        """
        Checks if the solution is valid, meaning it covers all required edges.

        Raises
        ------
        - ValueError: If the solution is not available (i.e., self.solution is None).

        Returns
        -------
        - bool: True if the solution is valid, False otherwise.

        Notes
        -------
        - get_solution() must be called before this method.
        """

        if self.__solution is None:
            utils.logger.error(f"{__name__}: Solution is not available. Call get_solution() first.")
            raise ValueError("Solution is not available. Call get_solution() first.")

        solution_paths = self.__solution["paths"]
        solution_paths_of_edges = [
            [(path[i], path[i + 1]) for i in range(len(path) - 1)]
            for path in solution_paths
        ]

        covered_by_paths = {(u, v): 0 for (u, v) in self.G.edges()}
        for path in solution_paths_of_edges:
            for e in path:
                covered_by_paths[e] += 1

        for u, v in self.G.edges():
            if (u,v) not in self.edges_to_ignore:
                if covered_by_paths[(u, v)] == 0: 
                    return False

        return True
    
    def get_objective_value(self):
        
        self.check_is_solved()

        return self.k
    
    def get_lowerbound_k(self):

        if self.__lowerbound_k is None:
            self.__lowerbound_k = self.G.get_width(edges_to_ignore=self.edges_to_ignore)
        
        return self.__lowerbound_k