import time
import networkx as nx
import flowpaths.stdigraph as stdigraph
import flowpaths.kflowdecomp as kflowdecomp
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.utils.graphutils as gu
import copy
import math

class MinFlowDecomp(pathmodel.AbstractPathModelDAG): # Note that we inherit from AbstractPathModelDAG to be able to use this class to also compute safe paths, 
    """
    Class to decompose a flow into a minimum number of weighted paths.
    """

    # Storing some default
    subgraph_nodes_increment = 30

    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        weight_type: type = float,
        subpath_constraints: list = [],
        subpath_constraints_coverage: float = 1.0,
        subpath_constraints_coverage_length: float = None,
        edge_length_attr: str = None,
        edges_to_ignore: list = [],
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

            List of edges to ignore when adding constrains on flow explanation by the weighted paths and their slack.
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `optimization_options : dict`, optional
            
            Dictionary with the optimization options. Default is `None`. See [optimization options documentation](solver-options-optimizations.md).
            This class also supports the optimization `"optimize_with_greedy": True` (this is the default value). This
            will use a greedy algorithm to solve the problem, and if the number of paths returned by it equals a lowerbound on the solution size,
            then we know the greedy solution is optimum, and it will use that. The lowerbound used currently is the edge-width of the graph,
            meaning the minimum number of paths needed to cover all edges. This is a correct lowerbound because any flow decomposition must cover all edges, 
            as they have non-zero flow.

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `None`. See [solver options documentation](solver-options-optimizations.md).

        Raises
        ------
        `ValueError`

        - If `weight_type` is not `int` or `float`.
        - If some edge does not have the flow attribute specified as `flow_attr`.
        - If the graph does not satisfy flow conservation on nodes different from source or sink.
        - If the graph contains edges with negative (<0) flow values.
        - If the graph is not acyclic.
        """

        self.G = G
        self.flow_attr = flow_attr
        self.weight_type = weight_type
        self.subpath_constraints = subpath_constraints
        self.subpath_constraints_coverage = subpath_constraints_coverage
        self.subpath_constraints_coverage_length = subpath_constraints_coverage_length
        self.edge_length_attr = edge_length_attr
        self.edges_to_ignore = edges_to_ignore
        self.optimization_options = optimization_options
        self.solver_options = solver_options

        self.solve_statistics = {}
        self.__solution = None
        self.__lowerbound_k = None
        self.__is_solved = None

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
        for i in range(self.get_lowerbound_k(), self.G.number_of_edges()):
            print("Trying with k = ", i)
            fd_model = kflowdecomp.kFlowDecomp(
                G=self.G,
                flow_attr=self.flow_attr,
                k=i,
                weight_type=self.weight_type,
                subpath_constraints=self.subpath_constraints,
                subpath_constraints_coverage=self.subpath_constraints_coverage,
                subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                edge_length_attr=self.edge_length_attr,
                edges_to_ignore=self.edges_to_ignore,
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

    def solve3(self) -> bool:

        start_time = time.time()

        selfG_nx = nx.DiGraph(self.G)
        topo_order = list(nx.topological_sort(selfG_nx))
        # print("topo_order: ", topo_order)
        all_weights = set({int(selfG_nx.edges[e][self.flow_attr]) for e in selfG_nx.edges() if self.flow_attr in selfG_nx.edges[e]})
        all_weights_list = list(all_weights)
        # print("all_weights", all_weights)

        current_lowerbound_k = self.get_lowerbound_k()

        source_flow = 0
        for n in selfG_nx.nodes():
            if selfG_nx.in_degree(n) == 0:
                source_flow += selfG_nx.nodes[n].get(self.flow_attr,0)
        print("source_flow", source_flow)
        print("all_weights", all_weights)
        start_time = time.time()
        k_gen_solver = MinGeneratingSet(a = all_weights_list, total = source_flow, lowerbound=current_lowerbound_k)
        generating_set = k_gen_solver.generating_set
        all_weights.update(generating_set)
        all_weights_list = list(all_weights)
        print(f"{time.time() - start_time} sec")
        
        current_lowerbound_k = max(current_lowerbound_k, len(generating_set))

        print("current_lowerbound_k", current_lowerbound_k)

        right_node_index = 0
        left_subpath_constraints = []        

        while right_node_index < selfG_nx.number_of_nodes() - 1:

            right_node_index = min(right_node_index + MinFlowDecomp.subgraph_nodes_increment, selfG_nx.number_of_nodes() - 1)
            print("right_node_index", right_node_index)
            left_subgraph = gu.get_subgraph_between_topological_nodes(selfG_nx, topo_order=topo_order, left=right_node_index - MinFlowDecomp.subgraph_nodes_increment, right=right_node_index)
            if not gu.check_flow_conservation(left_subgraph, self.flow_attr):
                raise ValueError("Flow conservation not satisfied in subgraph")

            left_subpath_constraints = [c for c in self.subpath_constraints if all(n in left_subgraph.nodes() for n in c)]
            left_edges_to_ignore = [e for e in self.edges_to_ignore if all(n in left_subgraph.nodes() for n in e)]
            self.optimization_options["lowerbound_k"] = current_lowerbound_k

            left_mfd_solver = MinFlowDecomp(
                    G=left_subgraph,
                    flow_attr=self.flow_attr,
                    weight_type=self.weight_type,
                    subpath_constraints=left_subpath_constraints,
                    subpath_constraints_coverage=self.subpath_constraints_coverage,
                    subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                    edge_length_attr=self.edge_length_attr,
                    edges_to_ignore=left_edges_to_ignore,
                    optimization_options=self.optimization_options,
                    solver_options=self.solver_options,
                )
            left_mfd_solver.solve()
            if left_mfd_solver.is_solved():
                left_mfd_solution = left_mfd_solver.get_solution()
            
                current_lowerbound_k = max(current_lowerbound_k,len(left_mfd_solution["weights"]))
                print("left_mfd_solution['weights']", left_mfd_solution["weights"])
                print("current_lowerbound_k", current_lowerbound_k)

                # If we got a better lowerbound, 
                full_graph_optimization_options = copy.deepcopy(self.optimization_options)
                full_graph_optimization_options["optimize_with_greedy"] = False
                full_graph_optimization_options["optimize_with_safe_paths"] = False
                full_graph_optimization_options["optimize_with_safe_sequences"] = False
                full_graph_optimization_options["optimize_with_zero_safe_edges"] = False
                full_graph_optimization_options["allow_empty_paths"] = True
                full_graph_optimization_options["given_weights"] = all_weights_list # + left_mfd_solution["weights"]

                print("Now trying the full graph with weights")
                print(full_graph_optimization_options["given_weights"])

                full_mfd_solver = kflowdecomp.kFlowDecomp(
                    G=self.G,
                    k = len(full_graph_optimization_options["given_weights"]),
                    flow_attr=self.flow_attr,
                    weight_type=self.weight_type,
                    subpath_constraints=self.subpath_constraints,
                    subpath_constraints_coverage=self.subpath_constraints_coverage,
                    subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                    edge_length_attr=self.edge_length_attr,
                    edges_to_ignore=self.edges_to_ignore,
                    optimization_options=full_graph_optimization_options,
                    solver_options=self.solver_options,
                    )
                full_mfd_solver.solve()

                if full_mfd_solver.is_solved():
                    full_mfd_solution = full_mfd_solver.get_solution()
                    non_empty_paths = []
                    non_empty_weights = []
                    for path, weight in zip(full_mfd_solution["paths"], full_mfd_solution["weights"]):
                        if len(path) > 1:
                            non_empty_paths.append(path)
                            non_empty_weights.append(weight)
                    
                    if len(non_empty_weights) == current_lowerbound_k:

                        self.__solution = {"paths": non_empty_paths, "weights": non_empty_weights}
                        self.set_solved()
                        self.solve_statistics = full_mfd_solver.solve_statistics
                        self.solve_statistics["mfd_solve_time"] = time.time() - start_time

                        # storing the fd_model object for further analysis
                        self.fd_model = full_mfd_solver
                        return True
                
                print("Full graph not solved. Continuing.")

    def solve2(self) -> bool:
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
        left_nodes_size = 0
        left_subpath_constraints = []
        selfG_nx = nx.DiGraph(self.G)
        all_weights = set({int(selfG_nx.edges[e][self.flow_attr]) for e in selfG_nx.edges() if self.flow_attr in selfG_nx.edges[e]})

        source_flow = 0
        for n in selfG_nx.nodes():
            if selfG_nx.in_degree(n) == 0:
                source_flow += selfG_nx.nodes[n].get(self.flow_attr,0)
        print("source_flow", source_flow)
        print("all_weights", all_weights)
        # min_gen_set_solver = MinGeneratingSet(values = all_weights, total = int(source_flow))

        # exit()

        self.optimization_options["lowerbound_k"] = self.get_lowerbound_k()

        stG = stdigraph.stDiGraph(self.G)
        weight_function = {e: 1 for e in stG.edges()}
        first_iteration = True
        while left_nodes_size < self.G.number_of_nodes():
            if not first_iteration:
                _, left_most_antichain = stG.compute_max_edge_antichain(get_antichain=True, 
                                                            weight_function=weight_function)
                print("left_most_antichain", left_most_antichain)    
            
                # We get the nodes to the "left" of the heads of the edges in left_most_antichain
                left_nodes = set()
                for e in left_most_antichain:
                    left_nodes.update(stG.reachable_nodes_rev_from[e[1]])
                    weight_function[e] = 0

                # We get those lists from self.subpath_constraints whose all nodes are in left_nodes
                left_subpath_constraints = [c for c in self.subpath_constraints if all(n in left_nodes for n in c)]
                
                left_edges_to_ignore = [e for e in self.edges_to_ignore if all(n in left_nodes for n in e)]
                
                left_nodes_size = len(left_nodes)
                print("left_nodes len: ", left_nodes_size)

                left_subgraph = selfG_nx.subgraph(left_nodes)
                # print(left_subgraph.edges(data=True))
                
                print("self.optimization_options", self.optimization_options)

                left_mfd_solver = MinFlowDecomp(
                    G=left_subgraph,
                    flow_attr=self.flow_attr,
                    weight_type=self.weight_type,
                    subpath_constraints=left_subpath_constraints,
                    subpath_constraints_coverage=self.subpath_constraints_coverage,
                    subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                    edge_length_attr=self.edge_length_attr,
                    edges_to_ignore=left_edges_to_ignore,
                    optimization_options=self.optimization_options,
                    solver_options=self.solver_options,
                )
                left_mfd_solver.solve()
                if left_mfd_solver.is_solved():
                    left_mfd_solution = left_mfd_solver.get_solution()
                
                    self.optimization_options["lowerbound_k"] = len(left_mfd_solution["weights"])
                    print("lowerbound_k", self.optimization_options["lowerbound_k"])
                    print("left_mfd_solution['weights']", left_mfd_solution["weights"])

                    all_weights = all_weights.union(int(weight) for weight in left_mfd_solution["weights"])

            
            if first_iteration or left_mfd_solver.is_solved():
                
                full_graph_optimization_options = copy.deepcopy(self.optimization_options)
                full_graph_optimization_options["optimize_with_greedy"] = False
                full_graph_optimization_options["optimize_with_safe_paths"] = False
                full_graph_optimization_options["optimize_with_safe_sequences"] = False
                full_graph_optimization_options["optimize_with_zero_safe_edges"] = False
                full_graph_optimization_options["allow_empty_paths"] = True
                full_graph_optimization_options["given_weights"] = list(all_weights) * 2 # self.optimization_options["lowerbound_k"]

                print("Now trying the full graph with weights")
                print(full_graph_optimization_options["given_weights"])

                full_mfd_solver = kflowdecomp.kFlowDecomp(
                    G=self.G,
                    k = len(full_graph_optimization_options["given_weights"]),
                    flow_attr=self.flow_attr,
                    weight_type=self.weight_type,
                    subpath_constraints=self.subpath_constraints,
                    subpath_constraints_coverage=self.subpath_constraints_coverage,
                    subpath_constraints_coverage_length=self.subpath_constraints_coverage_length,
                    edge_length_attr=self.edge_length_attr,
                    edges_to_ignore=self.edges_to_ignore,
                    optimization_options=full_graph_optimization_options,
                    solver_options=self.solver_options,
                    )
                full_mfd_solver.solve()

                if full_mfd_solver.is_solved():
                    self.__solution = full_mfd_solver.get_solution()
                    self.set_solved()
                    self.solve_statistics = full_mfd_solver.solve_statistics
                    self.solve_statistics["mfd_solve_time"] = time.time() - start_time

                    # storing the fd_model object for further analysis
                    self.fd_model = full_mfd_solver
                    return True
                else:
                    print("Full graph not solved. Continuing.")

            first_iteration = False

        return True
    

    def get_solution(self):
        """
        Retrieves the solution for the flow decomposition problem.

        Returns
        -------
        - `solution: dict`
        
            A dictionary containing the solution paths (key `"paths"`) and their corresponding weights (key `"weights"`).

        Raises
        -------
        - `exception` If model is not solved.
        """
        self.check_is_solved()
        return self.__solution
    
    def get_objective_value(self):

        self.check_is_solved()

        # Number of paths
        return len(self.__solution["paths"])

    def is_valid_solution(self) -> bool:
        return self.fd_model.is_valid_solution()
    
    def get_lowerbound_k(self):

        if self.__lowerbound_k != None:
            return self.__lowerbound_k
        
        stG = stdigraph.stDiGraph(self.G)

        self.__lowerbound_k = self.optimization_options.get("lowerbound_k", 1) if self.optimization_options != None else 1

        all_weights = set({int(self.G.edges[e][self.flow_attr]) for e in self.G.edges() if self.flow_attr in self.G.edges[e]})
        
        self.__lowerbound_k = max(self.__lowerbound_k, math.ceil(math.log2(len(all_weights))))

        self.__lowerbound_k = max(self.__lowerbound_k, stG.get_width(edges_to_ignore=self.edges_to_ignore))

        # self.__lowerbound_k = max(self.__lowerbound_k, stG.get_flow_width(flow_attr=self.flow_attr, edges_to_ignore=self.edges_to_ignore))

        return self.__lowerbound_k
