######################
# This is a minimal example of how to use the GenericPathModelDAG class to 
# decompose an inexact flow (given as intervals [lb,ub] for each edge) into 
# a given number of weighted paths, # while minimizing the sum of the weights of the paths.
# 
# NOTE: See kflowdecomp.py for best practices on how to implement a new decomposition model.
######################

import flowpaths as fp
import networkx as nx

class kInexactFlowDecomposition(fp.GenericPathModelDAG):
    def __init__(self, G: nx.DiGraph, lb:str, ub:str, num_paths:int):

        self.G = fp.stDiGraph(G)
        self.lb = lb
        self.ub = ub  

        # We declare the solution attribute, to be able to cache it.
        self.solution = None      
        
        # To be able to apply the safety optimizations, we get the edges that 
        # must appear in some solution path. For this problem, these are the edges 
        # that have a non-zero flow lowerbound.
        trusted_edges_for_safety = self.G.get_non_zero_flow_edges(flow_attr=self.lb)

        # We initialize the super class with the graph, the number of paths, and the trusted edges.
        super().__init__(self.G, num_paths, trusted_edges_for_safety=trusted_edges_for_safety)

        # This method is called from the super class GenericPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class
        self.encode_inexact_flow_decomposition()

        # We encode the objective
        self.encode_objective()
            
    def encode_inexact_flow_decomposition(self):

        # Get the maximum data in an edge indexed under self.lb
        maximum_allowed_path_weight = max(data.get(self.ub,0) for u, v, data in self.G.edges(data=True))

        # pi vars from https://arxiv.org/pdf/2201.10923 page 14
        self.pi_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="p",
            lb=0,
            ub=maximum_allowed_path_weight,
        )
        self.path_weights_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="w",
            lb=0,
            ub=maximum_allowed_path_weight,
        )

        # We encode that for each edge (u,v), the sum of the weights of the paths going through the edge is equal to the flow value of the edge.
        for u, v, data in self.G.edges(data=True):
            # We ignore edges incident to the artificial global source and sink
            if (u, v) in self.G.source_sink_edges:
                continue

            # We encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)],
            # assuming self.w_max is a bound for self.path_weights_vars[(i)]
            for i in range(self.k):
                self.solver.add_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    product_var=self.path_weights_vars[(i)],
                    equal_var=self.pi_vars[(u, v, i)],
                    bound=maximum_allowed_path_weight,
                    name=f"product_u={u}_v={v}_i={i}",
                )

            self.solver.add_constraint(
                sum(self.pi_vars[(u, v, i)] for i in range(self.k)) >= data[self.lb],
                name=f"lowerbound_u={u}_v={v}_i={i}",
            )

            self.solver.add_constraint(
                sum(self.pi_vars[(u, v, i)] for i in range(self.k)) <= data[self.ub],
                name=f"upperbound_u={u}_v={v}_i={i}",
            )

    def encode_objective(self):

        self.solver.set_objective(
            sum(self.path_weights_vars[(i)] for i in range(self.k)), 
            sense="minimize",
        )

    def get_solution(self):

        if self.solution is not None:
            return self.solution
    
        solution_weights_dict = self.solver.get_variable_values("w", [int])
        self.solution = (
            self.get_solution_paths(), 
            [round(solution_weights_dict[i]) for i in range(self.k)]
        )

        return self.solution

if __name__ == "__main__":
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge(0, "a", lb=2, ub=6)
    graph.add_edge(0, "b", lb=7, ub=7)
    graph.add_edge("a", "b", lb=1, ub=2)
    graph.add_edge("a", "c", lb=3, ub=5)
    graph.add_edge("b", "c", lb=5, ub=9)
    graph.add_edge("c", "d", lb=3, ub=6)
    graph.add_edge("c", 1, lb=4, ub=7)
    graph.add_edge("d", 1, lb=2, ub=6)

    # We create a kInexactFlowDecomposition model
    # with the flow lower bounds in the attribute `lb` of the edges,
    # the flow upper bounds in the attribute `ub` of the edges,
    # and the number of paths to consider set to 3
    kifd_model = kInexactFlowDecomposition(graph, lb="lb", ub="ub", num_paths=3)

    # We solve it
    kifd_model.solve()

    # We process its solution
    if kifd_model.solved:
        solution = kifd_model.get_solution()
        print(
            "Solution paths, weights, solve statistics: ",
            solution[0],
            solution[1],
            kifd_model.solve_statistics,
        )
    else:
        print("Model could not be solved.")