######################
# This is a minimal example of how to use the GenericPathModelDAG class to 
# decompose an inexact flow (given as intervals [lb,ub] for each edge) into 
# a given number of weighted paths, # while minimizing the sum of the weights of the paths.
# 
# NOTE: See kflowdecomp.py or kminpatherror.py for best practices on how to implement a new decomposition model.
######################

import flowpaths as fp
import networkx as nx

class kInexactFlowDecomposition(fp.GenericPathModelDAG):
    def __init__(self, G: nx.DiGraph, lb:str, ub:str, num_paths:int):

        self.G = fp.stDiGraph(G)
        self.lb = lb # We assume all lowerbounds are >= 0
        self.ub = ub # We assume all upperbounds are >= 0
        # self.k = num_paths will be available from the superclass GenericPathModelDAG, 
        # after calling super().__init__(...), which happens below.

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

        # Get the maximum data in an edge indexed under self.lb.
        # This will be used to set the upper bound of the path weights, since a path weight larger than this
        # would not "fit" inside the flow interval of an edge.
        maximum_allowed_path_weight = max(data.get(self.ub,0) for u, v, data in self.G.edges(data=True))

        # From the super class, we already have the edge_vars, such that
        # edge_vars[(u,v,i)] = 1 if path i goes through edge (u,v), 0 otherwise
        
        # We now declare the path_weights_vars, such that
        # path_weights_vars[(i)] = the weight of path i
        # Note that the weights are non-negative, and we set the upper bound to the maximum allowed path weight
        self.path_weights_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="w",
            lb=0,
            ub=maximum_allowed_path_weight,
        )

        # The pi_vars will be used to encode the product of edge_vars and path_weights_vars
        # Specifically, pi_vars[(u,v,i)] = edge_vars[(u,v,i)] * path_weights_vars[(i)]
        # This means pi_vars[(u,v,i)] equals path_weights_vars[(i)] if path i goes through edge (u,v), otherwise it is 0
        self.pi_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="p",
            lb=0,
            ub=maximum_allowed_path_weight,
        )

        # We encode that for each edge (u,v), the sum of the weights of the paths 
        # going through the edge is in the flow interval of the edge.
        for u, v, data in self.G.edges(data=True):
            # We ignore edges incident to the artificial global source and sink
            if (u, v) in self.G.source_sink_edges:
                continue

            # We encode that edge_vars[(u,v,i)] * self.path_weights_vars[(i)] = self.pi_vars[(u,v,i)]
            # Since this is a non-linear term, we will use the add_product_constraint method that 
            # will introduce additional constraints to linearize it for us, assuming that
            # 0 <= path_weights_vars[(i)] <= maximum_allowed_path_weight, which is the case
            for i in range(self.k):
                self.solver.add_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    product_var=self.path_weights_vars[(i)],
                    equal_var=self.pi_vars[(u, v, i)],
                    bound=maximum_allowed_path_weight,
                    name=f"product_u={u}_v={v}_i={i}",
                )

            # We next encode that the sum of the weights of the paths going through the edge 
            # is at least the lowerbound, and at most the upper bound of the edge.
            
            # That is, the sum of the pi_vars for edge (u,v) is at least the lowerbound of the edge,
            self.solver.add_constraint(
                sum(self.pi_vars[(u, v, i)] for i in range(self.k)) >= data[self.lb],
                name=f"lowerbound_u={u}_v={v}_i={i}",
            )

            # and at most the upperbound of the edge.
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