import flowpaths.utils.solverwrapper as sw
import flowpaths.stdigraph as stdigraph
import networkx as nx
from copy import deepcopy
import time

class MinErrorFlow():
    def __init__(
            self, 
            G: nx.DiGraph,
            flow_attr: str,
            weight_type: type = float,
            sparsity_lambda: float = 0,
            edges_to_ignore: list = [],
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

            The directed acyclic graph to be corrected.

        - `flow_attr: str`

            The name of the attribute in the edges of the graph that contains the weight of the edge.

        - `weight_type: type`

            The type of the weights of the edges. It can be either `int` or `float`. Default is `float`.

        - `sparsity_lambda: float`

            The sparsity parameter. It is used to control the trade-off between the sparsity of the solution and the closeness to the original weights. Default is `0`.
            If `sparsity_lambda` is set to `0`, then the solution will be as close as possible to the original weights. If `sparsity_lambda` is set to a positive value, then the solution will be sparser, i.e. it will have less flow going out of the source.
            The higher the value of `sparsity_lambda`, the sparser the solution will be.

        - `edges_to_ignore: list`

            A list of edges to ignore. The weights of these edges will still be corrected, but their error will not count in the objective function that is being minimized. Default is `[]`.

        - `additional_starts: list`

            A list of nodes to be added as additional sources. Flow is allowed to start start at these nodes, meaning that their out going flow can be greater than their incoming flow. Default is `[]`.

        - `additional_ends: list`

            A list of nodes to be added as additional sinks. Flow is allowed to end at these nodes, meaning that their incoming flow can be greater than their outgoing flow. Default is `[]`.

        - `solver_options: dict`

            A dictionary containing the options for the solver. The options are passed to the solver wrapper. Default is `{}`.
        """
        
        self.original_graph_copy = deepcopy(G)
        self.G = stdigraph.stDiGraph(G, additional_starts=additional_starts, additional_ends=additional_ends)
        self.flow_attr = flow_attr
        if weight_type not in [int, float]:
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type
        self.sparsity_lambda = sparsity_lambda
        self.edges_to_ignore = set(edges_to_ignore).union(self.G.source_sink_edges)
        self.solver_options = solver_options

        self.__solution = None
        self.__is_solved = None
        self.solve_statistics = dict()

        self.edge_vars = {}
        self.edge_error_vars = {}
        self.edge_sol = {}


        self.__create_solver()

        self.__encode_flow()

        self.__encode_objective()    

    def __create_solver(self):
        
        self.solver = sw.SolverWrapper(**self.solver_options)

    def __encode_flow(self):
        
        self.solver = sw.SolverWrapper()

        w_max = max(
            [
                self.G[u][v].get(self.flow_attr, 0)
                for (u, v) in self.G.edges() 
                if (u, v) not in self.edges_to_ignore
            ]
        )
        ub = w_max * self.G.number_of_edges()

        # Creating the edge variables
        self.edge_indexes = [(u, v) for (u, v) in self.G.edges()]
        self.edge_vars = self.solver.add_variables(
            self.edge_indexes, 
            name_prefix="edge_vars", 
            lb=0, 
            ub=ub, 
            var_type="integer" if self.weight_type == int else "continuous",
        )
        self.edge_error_vars = self.solver.add_variables(
            self.edge_indexes, 
            name_prefix="edge_error_vars", 
            lb=0, 
            ub=ub, 
            var_type="integer" if self.weight_type == int else "continuous",
        )

        # Adding flow conservation constraints
        for node in self.G.nodes():
            if node in [self.G.source, self.G.sink]:
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

    def __encode_objective(self):
        
        # Objective function: minimize the sum of the edge error variables
        # plus the sparsity of the solution (i.e. sparsity_lambda * sum of the corrected flow going out of the source)
        self.solver.set_objective(
            self.solver.quicksum(
                self.edge_error_vars[(u, v)]
                for (u, v) in self.G.edges()
                if (u, v) not in self.edges_to_ignore
            ) + self.sparsity_lambda * self.solver.quicksum(
                self.edge_vars[(u, v)]
                for (u, v) in self.G.out_edges(self.G.source)
            ),
            sense="minimize",
        )

    def solve(self):
        """
        Solves the problem. Returns `True` if the model was solved, `False` otherwise.
        """
        start_time = time.time()
        self.solver.optimize()
        self.solve_statistics[f"milp_solve_time"] = (time.time() - start_time)

        self.solve_statistics[f"milp_solver_status"] = self.solver.get_model_status()

        if self.solver.get_model_status() == "kOptimal":
            self.__is_solved = True
            return True

        self.__is_solved = False
        return False

    def is_solved(self):
        """
        Returns `True` if the model was solved, `False` otherwise.
        """
        if self.__is_solved is None:
            raise Exception("Model not yet solved. If you want to solve it, call the `solve` method first.")
        
        return self.__is_solved
    
    def __check_is_solved(self):
        if not self.is_solved():
            raise Exception(
                "Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit."
            )

    def get_solution(self):
        """
        Returns the solution to the problem, if the model was solved. 

        Returns
        -------

        -  `dict`

            A dictionary containing the following keys:

            - `graph`: the corrected graph, as a networkx DiGraph.
            - `error`: the error of the solution, i.e. the sum of the absolute differences between the original weights and the corrected weights.
            - `objective_value`: the value of the objective function.
        
        !!! warning "Warning"
            Call the `solve` method first.
        """
        if self.__solution is not None:
            return self.__solution
        
        self.__check_is_solved()

        edge_sol_dict = self.solver.get_variable_values("edge_vars", [str, str])
        for edge in edge_sol_dict.keys():
            self.edge_sol[edge] = (
                round(edge_sol_dict[edge])
                if self.weight_type == int
                else float(edge_sol_dict[edge])
            )
        
        edge_error_sol_dict = self.solver.get_variable_values("edge_error_vars", [str, str])
        error = sum(edge_error_sol_dict.values())

        for u, v in self.original_graph_copy.edges():
            self.original_graph_copy[u][v][self.flow_attr] = self.edge_sol[(u, v)]

        self.__solution = {
            "graph": self.original_graph_copy,
            "error": error,
            "objective_value": self.solver.get_objective_value(),
        }
        
        return self.__solution  

        