import flowpaths.utils.solverwrapper as sw
import flowpaths.stdag as stdag
import flowpaths.utils as utils
import flowpaths.nodeexpandeddigraph as nedg
import networkx as nx
from copy import deepcopy
import time

class MinErrorFlow():
    def __init__(
            self, 
            G: nx.DiGraph,
            flow_attr: str,
            flow_attr_origin: str = "edge",
            weight_type: type = float,
            sparsity_lambda: float = 0,
            few_flow_values_epsilon: float = None,
            elements_to_ignore: list = [],
            error_scaling: dict = {},
            additional_starts: list = [],
            additional_ends: list = [],
            solver_options: dict = {},
            ):
        """
        This class implements a method to optimally correct the weights of a directed acyclic graph, so that:

        - The resulting weights become a flow, i.e. they become a non-negative flow, namely they satisfy the flow conservation constraints.
        - The resulting weights are as close as possible to the original weights, i.e. the sum of the absolute difference between an edge weight and the corrected flow value of the edge, for all edges, is minimized.

        Parameters
        ----------

        - `G: networkx.DiGraph`

            The directed graph to be corrected (which does not need to be acyclic).

        - `flow_attr: str`

            The name of the attribute in the edges of the graph that contains the weight of the edge.

        - `flow_attr_origin : str`, optional

            The origin of the flow attribute. Default is `"edge"`. Options:
            
            - `"edge"`: the flow attribute is assumed to be on the edges of the graph.
            - `"node"`: the flow attribute is assumed to be on the nodes of the graph. See [the documentation](node-expanded-digraph.md) on how node-weighted graphs are handled.

        - `weight_type: type`, optional

            The type of the weights of the edges. It can be either `int` or `float`. Default is `float`.

        - `sparsity_lambda: float`, optional

            The sparsity parameter, used to control the trade-off between the sparsity of the solution and the closeness to the original weights. Default is `0`.
            If `sparsity_lambda` is set to `0`, then the solution will be as close as possible to the original weights. If `sparsity_lambda` is set to a positive value, then the solution will be sparser, i.e. it will have less flow going out of the source.
            The higher the value of `sparsity_lambda`, the sparser the solution will be. **You can use a value different than `0` only for acyclic graphs.** If you set it to a value different than `0` for a cyclic graph, the class will raise an error.

        - `few_flow_values_epsilon: float`, optional
            
            The epsilon value (at least zero) used to control the number of distinct values in the corrected flow. If `few_flow_values_epsilon` is set to `None`, then the solution will be as close as possible to the original weights,
            and there is no bound on the number of distinct values in the corrected flow.
            If `few_flow_values_epsilon` is set to a positive value, then the solution will have fewer distinct flow values in the corrected flow, while ensuring that the objective value of the resulting problem is within $(1+\varepsilon)$ of the optimal solution (with this parameter set to `None`).
            The higher the value of `few_flow_values_epsilon`, the smaller the number of flow values in the corrected flow, but possibly higher the sum of edge errors in the corrected flow. Default is `None`.

            !!! warning "Warning"

                Setting this can be slow on larger graphs.

        - `elements_to_ignore : list`, optional

            List of edges (or nodes, if `flow_attr_origin` is `"node"`) to ignore when adding constrains on flow explanation by the weighted paths. 
            Default is an empty list. See [ignoring edges documentation](ignoring-edges.md)

        - `error_scaling: dict`, optional
            
            Dictionary `edge: factor` (or `node: factor`, if `flow_attr_origin` is `"node"`)) storing the error scale factor (in [0,1]) of every edge, which scale the allowed difference between edge/node weight and path weights.
            Default is an empty dict. If an edge/node has a missing error scale factor, it is assumed to be 1. The factors are used to scale the 
            difference between the flow value of the edge/node and the sum of the weights of the paths going through the edge/node. See [ignoring edges documentation](ignoring-edges.md)

        - `additional_starts: list`, optional

            A list of nodes to be added as additional sources. **This applies only to acyclic graphs.** Flow is allowed to start start at these nodes, meaning that their out going flow can be greater than their incoming flow. Default is `[]`. See also [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `additional_ends: list`, optional

            A list of nodes to be added as additional sinks. **This applies only to acyclic graphs.** Flow is allowed to end at these nodes, meaning that their incoming flow can be greater than their outgoing flow. Default is `[]`. See also [additional start/end nodes documentation](additional-start-end-nodes.md).

        - `solver_options: dict`, optional

            A dictionary containing the options for the solver. The options are passed to the solver wrapper. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).
        """

        # Handling node-weighted graphs
        self.flow_attr_origin = flow_attr_origin
        if self.flow_attr_origin == "node":
            if G.number_of_nodes() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no nodes. Please provide a graph with at least one node.")
                raise ValueError(f"The input graph G has no nodes. Please provide a graph with at least one node.")
            
            self.G_internal = nedg.NodeExpandedDiGraph(G, node_flow_attr=flow_attr)
            additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
            additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)

            edges_to_ignore_internal = self.G_internal.edges_to_ignore
            if not all(isinstance(node, str) for node in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of nodes, i.e. strings, not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of nodes, i.e. strings, not {elements_to_ignore}")
            edges_to_ignore_internal += [self.G_internal.get_expanded_edge(node) for node in elements_to_ignore]
            edges_to_ignore_internal = list(set(edges_to_ignore_internal))

            error_scaling_internal = {self.G_internal.get_expanded_edge(node): error_scaling[node] for node in error_scaling}

        elif self.flow_attr_origin == "edge":
            if G.number_of_edges() == 0:
                utils.logger.error(f"{__name__}: The input graph G has no edges. Please provide a graph with at least one edge.")
                raise ValueError(f"The input graph G has no edges. Please provide a graph with at least one edge.")
            
            self.G_internal = G
            additional_starts_internal = additional_starts
            additional_ends_internal = additional_ends

            if not all(isinstance(edge, tuple) and len(edge) == 2 for edge in elements_to_ignore):
                utils.logger.error(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
                raise ValueError(f"elements_to_ignore must be a list of edges (i.e. tuples of nodes), not {elements_to_ignore}")
            edges_to_ignore_internal = elements_to_ignore

            error_scaling_internal = error_scaling
        else:
            utils.logger.error(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")
            raise ValueError(f"flow_attr_origin must be either 'node' or 'edge', not {self.flow_attr_origin}")

        self.original_graph_copy = deepcopy(self.G_internal)
        self.sparsity_lambda = sparsity_lambda
        
        if nx.is_directed_acyclic_graph(self.G_internal):
            self.is_acyclic = True
            self.G = stdag.stDAG(self.G_internal, additional_starts=additional_starts_internal, additional_ends=additional_ends_internal)
            self.edges_to_ignore = set(edges_to_ignore_internal).union(self.G.source_sink_edges)
        else:
            self.G = self.G_internal
            self.is_acyclic = False
            self.edges_to_ignore = set(edges_to_ignore_internal)
            if self.sparsity_lambda != 0:
                utils.logger.error(f"{__name__}: You cannot set sparsity_lambda != 0 for a graph with cycles.")
                raise ValueError(f"You cannot set sparsity_lambda != 0 for a graph with cycles.")
        self.edge_error_scaling = error_scaling_internal
        # If the error scaling factor is 0, we ignore the edge
        self.edges_to_ignore |= {edge for edge, factor in self.edge_error_scaling.items() if factor == 0}
        
        # Checking that every entry in self.error_scaling is between 0 and 1
        for key, value in error_scaling.items():
            if value < 0 or value > 1:
                utils.logger.error(f"{__name__}: Error scaling factor for {key} must be between 0 and 1.")
                raise ValueError(f"Error scaling factor for {key} must be between 0 and 1.")

        self.flow_attr = flow_attr
        if weight_type not in [int, float]:
            utils.logger.error(f"{__name__}: weight_type must be either int or float, not {weight_type}")
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type
        self.solver_options = solver_options

        # Checking that every entry in self.edge_error_scaling is between 0 and 1
        for key, value in self.edge_error_scaling.items():
            if value < 0 or value > 1:
                utils.logger.error(f"{__name__}: Error scaling factor for {key} must be between 0 and 1.")
                raise ValueError(f"Error scaling factor for {key} must be between 0 and 1.")


        self.different_flow_values_epsilon = few_flow_values_epsilon
        if few_flow_values_epsilon is not None:
            if few_flow_values_epsilon < 0:
                utils.logger.error(f"{__name__}: different_flow_values_epsilon must be greater than or equal to 0, not {few_flow_values_epsilon}")
                raise ValueError(f"different_flow_values_epsilon must be greater than or equal to 0, not {few_flow_values_epsilon}")
            if few_flow_values_epsilon == 0:
                self.different_flow_values_epsilon = None        

        self._solution = None
        self._is_solved = None
        self.solve_statistics = dict()

        self.edge_vars = {}
        self.edge_error_vars = {}
        self.edge_sol = {}

        self.w_max = max(
            [
                self.G[u][v].get(self.flow_attr, 0)
                for (u, v) in self.G.edges() 
            ]
        )
        self.ub = self.w_max * self.G.number_of_edges()

        self._create_solver()

        self._encode_flow()

        self._encode_min_sum_errors_objective()  

        utils.logger.info(f"{__name__}: initialized with graph id = {utils.fpid(G)}")  

    def _create_solver(self):
        
        self.solver = sw.SolverWrapper(**self.solver_options)

    def _encode_flow(self):

        # Creating the edge variables
        self.edge_indexes = [(u, v) for (u, v) in self.G.edges()]
        self.edge_vars = self.solver.add_variables(
            self.edge_indexes, 
            name_prefix="edge_vars", 
            lb=0, 
            ub=self.ub, 
            var_type="integer" if self.weight_type == int else "continuous",
        )
        self.edge_error_vars = self.solver.add_variables(
            self.edge_indexes, 
            name_prefix="edge_error_vars", 
            lb=0, 
            ub=self.ub, 
            var_type="integer" if self.weight_type == int else "continuous",
        )

        # Adding flow conservation constraints
        for node in self.G.nodes():
            if self.G.in_degree(node) == 0 or self.G.out_degree(node) == 0:
                continue
            # Flow conservation constraint
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.edge_vars[(u, v)]
                    for (u, v) in self.G.in_edges(node)
                )
                - self.solver.quicksum(
                    self.edge_vars[(u, v)]
                    for (u, v) in self.G.out_edges(node)
                )
                == 0,
                name=f"flow_conservation_{node}",
            )
        
        # Encoding the edge error variables
        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                # Making sure the error of the edges to ignore gets set to 0
                self.solver.add_constraint(
                    self.edge_error_vars[(u, v)] == 0,
                    name=f"edge_error_u={u}_v={v}",
                )
                continue
            
            # If the edge is not in the edges_to_ignore list, we need to check if it has a flow attribute
            if self.flow_attr not in data:
                utils.logger.error(f"{__name__}: Flow attribute '{self.flow_attr}' not found in edge data for edge {str((u, v))}, and this edge is not in the edges_to_ignore list.")
                raise ValueError(f"Flow attribute '{self.flow_attr}' not found in edge data for edge {str((u, v))}, and this edge is not in the edges_to_ignore list.")
            
            # Getting the flow value of the edge            
            f_u_v = data[self.flow_attr]
            
            # Encoding the error on the edge (u, v) as the difference between 
            # the flow value of the edge and the sum of the weights of the paths that go through it (pi variables)
            # If we minimize the sum of edge_error_vars, then we are minimizing the sum of the absolute errors.
            self.solver.add_constraint(
                f_u_v - self.edge_vars[(u, v)] <= self.edge_error_vars[(u, v)],
                name=f"edge_error_u={u}_v={v}",
            )

            self.solver.add_constraint(
                self.edge_vars[(u, v)] - f_u_v <= self.edge_error_vars[(u, v)],
                name=f"edge_error_u={u}_v={v}",
            )

    def _encode_min_sum_errors_objective(self):
        
        # Objective function: minimize the sum of the edge error variables
        # plus the sparsity of the solution (i.e. sparsity_lambda * sum of the corrected flow going out of the source)
        self.solver.set_objective(
            self.solver.quicksum(
                self.edge_error_vars[(u, v)] * self.edge_error_scaling.get((u, v), 1)
                for (u, v) in self.G.edges()
                if (u, v) not in self.edges_to_ignore
            ) + (self.sparsity_lambda * self.solver.quicksum(
                self.edge_vars[(u, v)]
                for (u, v) in self.G.out_edges(self.G.source)) if self.sparsity_lambda > 0 else 0
            ),
            sense="minimize",
        )

    def _encode_different_flow_values_and_objective(
            self, 
            edge_subset: list,
            objective_value: float, 
            ub_different_flow_values: int):

        utils.logger.debug(f"{__name__}: ub_diff_flow_values = {ub_different_flow_values}")
        utils.logger.debug(f"{__name__}: objective_value = {objective_value}, ub_diff_flow_values = {ub_different_flow_values}")

        self.all_flow_values_indexes = [i for i in range(ub_different_flow_values)]
        self.flow_value_map_indexes = [(u, v, i) for (u,v) in edge_subset for i in range(ub_different_flow_values)]

        self.all_flow_values_vars = self.solver.add_variables(
            self.all_flow_values_indexes, 
            name_prefix="all_flow_values_vars", 
            lb=0, 
            ub=self.ub, 
            var_type="integer" if self.weight_type == int else "continuous",
        )
        self.all_flow_values_used_indicator_vars = self.solver.add_variables(
            self.all_flow_values_indexes, 
            name_prefix="all_flow_values_used_indicator_vars",
            lb=0, 
            ub=1, 
            var_type="integer",
        )
        # flow_value_map_vars[(u, v, i)] = 1 if the flow value of edge (u, v) is equal to all_flow_values_vars[i], 0 otherwise
        self.flow_value_map_vars = self.solver.add_variables(
            self.flow_value_map_indexes, 
            name_prefix="flow_values_map_vars", 
            lb=0, 
            ub=1, 
            var_type="integer",
        )
        
        for (u, v) in edge_subset:
            # flow_value_map_vars[(u, v, i)] is 1 for exactly one i, for all (u, v) in G.edges()
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.flow_value_map_vars[(u, v, i)]
                    for i in self.all_flow_values_indexes
                ) == 1,
                name=f"flow_value_map_sum_equal_1_{u}_{v}",
            )
            for i in self.all_flow_values_indexes:
                # self.edge_vars[(u, v)] = sum(flow_value_product_vars[(u, v, i)] for i in all_flow_values_indexes)
                self.solver.add_constraint(
                    self.edge_vars[(u, v)] <= self.all_flow_values_vars[i] + self.ub * (1 - self.flow_value_map_vars[(u, v, i)]),
                    name=f"flow_value_product_sum_{u}_{v}_{i}_a",
                )
                self.solver.add_constraint(
                    self.edge_vars[(u, v)] >= self.all_flow_values_vars[i] - self.ub * (1 - self.flow_value_map_vars[(u, v, i)]),
                    name=f"flow_value_product_sum_{u}_{v}_{i}_b",
                )
                # all_flow_values_used_indicator_vars[i] = 1 if flow_value_map_vars[(u, v, i)] is 1 for some edge (u, v)
                self.solver.add_constraint(
                    self.all_flow_values_used_indicator_vars[i] >= self.flow_value_map_vars[(u, v, i)],
                    name=f"all_flow_values_used_indicator_{u}_{v}_{i}",
                )

        utils.logger.debug(f"{__name__}: adding epsilon constraint, with bound = {(1 + self.different_flow_values_epsilon) * objective_value}")
        # The sum of errors is at most 1+epsilon times the objective value
        self.solver.add_constraint(
            self.solver.quicksum(
                self.edge_error_vars[(u, v)] * self.edge_error_scaling.get((u, v), 1)
                for (u, v) in self.G.edges()
                if (u, v) not in self.edges_to_ignore
            ) + (self.sparsity_lambda * self.solver.quicksum(
                self.edge_vars[(u, v)]
                for (u, v) in self.G.out_edges(self.G.source)) if self.sparsity_lambda > 0 else 0
            ) <= (1 + self.different_flow_values_epsilon) * objective_value,
            name="epsilon_constraint",
        )

        # We minimize the number of used flow values
        self.solver.set_objective(
            self.solver.quicksum(
                self.all_flow_values_used_indicator_vars[i]
                for i in self.all_flow_values_indexes),
            sense="minimize",
        )

    def solve(self):
        """
        Solves the problem. Returns `True` if the model was solved, `False` otherwise.
        """
        utils.logger.info(f"{__name__}: solving with graph id = {utils.fpid(self.G)}")
        start_time = time.perf_counter()
        self.solver.optimize()
        self.solve_statistics[f"milp_solve_time"] = (time.perf_counter() - start_time)

        self.solve_statistics[f"milp_solver_status"] = self.solver.get_model_status()

        if self.solver.get_model_status() == "kOptimal":
            if self.different_flow_values_epsilon is None:
                self._is_solved = True
                utils.logger.info(f"{__name__}: model solved with objective value = {self.solver.get_objective_value()}")
                return True
            else:
                # We need to encode the different flow values variant
                objective_value = self.solver.get_objective_value()
                
                # If the objective value is 0, then we can stop here
                # because we cannot get a different solution
                if objective_value == 0:
                    self._is_solved = True
                    utils.logger.info(f"{__name__}: model solved with objective value = {objective_value}. We could not find change the flow values because the objective function was 0.")
                    return True

                self._is_solved = True # START hack to get the corrected graph                
                corrected_graph = self.get_corrected_graph()
                self._is_solved = False # END hack to get the corrected graph

                # Pick 30 random edges of G.edges()
                edge_subset = [e for e in self.original_graph_copy.edges()]
                # edge_subset = edge_subset[:30]        

                # Getting all the different 'flow_attr' values in the corrected graph
                ub_different_flow_values = len(set(
                    corrected_graph[u][v].get(self.flow_attr, 0)
                    for (u, v) in edge_subset
                ))

                utils.logger.info(f"{__name__}: re-solving now by minimizing the number of different flow values within 1 + epsilon tolerance to the objective value, i.e. <=(1+{self.different_flow_values_epsilon})*{objective_value}")
                self._create_solver()
                self._encode_flow()
                self._encode_different_flow_values_and_objective(
                    edge_subset=edge_subset,
                    objective_value=objective_value,
                    ub_different_flow_values=ub_different_flow_values,
                )
                self.solver.optimize()
                self.solve_statistics[f"milp_solve_time"] += (time.perf_counter() - start_time)
                self.solve_statistics[f"milp_solver_status"] = self.solver.get_model_status()
                
                if self.solver.get_model_status() == "kOptimal":
                    self._is_solved = True
                    utils.logger.info(f"{__name__}: model solved with objective value = {objective_value}")
                    return True
                else:
                    utils.logger.warning(f"{__name__}: model not solved, status = {self.solver.get_model_status()}")
                
        self._is_solved = False
        return False

    def is_solved(self):
        """
        Returns `True` if the model was solved, `False` otherwise.
        """
        return self._is_solved
    
    def _check_is_solved(self):
        if not self.is_solved():
            raise Exception(
                "Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit."
            )

    def get_solution(self):
        """
        Returns the solution to the problem, if the model was solved, as a dictionary containing the following keys:

        - `graph`: the corrected graph, as a networkx DiGraph.
        - `error`: the error of the solution, i.e. the sum of the absolute differences between the original weights and the corrected weights.
        - `objective_value`: the value of the objective function.
        
        !!! warning "Warning"
            Call the `solve` method first.
        """
        if self._solution is not None:
            return self._solution
        
        self._check_is_solved()

        edge_sol_dict = self.solver.get_values(self.edge_vars)
        for edge in edge_sol_dict.keys():
            self.edge_sol[edge] = (
                round(edge_sol_dict[edge])
                if self.weight_type == int
                else float(edge_sol_dict[edge])
            )

        edge_error_sol_dict = self.solver.get_values(self.edge_error_vars)
        error = sum(edge_error_sol_dict.values())

        corrected_graph = deepcopy(self.original_graph_copy)
        for u, v in corrected_graph.edges():
            if self.flow_attr in corrected_graph[u][v]:
                corrected_graph[u][v][self.flow_attr] = self.edge_sol[(u, v)]

        if self.flow_attr_origin == "edge":
            self._solution = {
                "graph": corrected_graph,
                "error": error,
                "objective_value": self.solver.get_objective_value(),
            }
        elif self.flow_attr_origin == "node":
            self._solution = {
                "graph": corrected_graph.get_condensed_graph(),
                "error": error,
                "objective_value": self.solver.get_objective_value(),
            }
        
        return self._solution  
    
    def get_corrected_graph(self):
        """
        Returns the corrected graph, as a networkx DiGraph. This is a deep copy of the original graph, but having the corrected weights.
        
        !!! warning "Warning"
            Call the `solve` method first.
        """
        solution = self.get_solution()
        return solution["graph"]
    

    def get_objective_value(self):
        """
        Returns the sum of the errors of the optimum solution.
        
        !!! warning "Warning"
            Call the `solve` method first.
        """

        solution = self.get_solution()
        return solution["error"]
        