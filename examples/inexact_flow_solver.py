######################
# This is a minimal example of how to use the abstract class AbstractPathModelDAG to 
# decompose an inexact flow (given as intervals [lb,ub] for each edge) into 
# a given number of weighted paths.
# 
# This model was introduced by 
# Williams, Reynolds and Mumey, "RNA Transcript Assembly Using Inexact Flows", 2019 IEEE International Conference on Bioinformatics and Biomedicine (BIBM)
# https://doi.org/10.1109/BIBM47256.2019.8983180
# 
# In addition, to illustrate how to add an objective fuction to the model, we minimize the sum of the path weights.
# 
# NOTE: See kflowdecomp.py or kminpatherror.py for best practices on how to implement a new decomposition model.
######################

import flowpaths as fp
import networkx as nx

class kInexactFlowDecomposition(fp.AbstractPathModelDAG):
    def __init__(self, G: nx.DiGraph, lb:str, ub:str, num_paths:int, threads:int=4):

        self.G = fp.stDAG(G)
        self.lb = lb # We assume all lowerbounds are >= 0
        self.ub = ub # We assume all upperbounds are >= 0
        # self.k = num_paths will be available from the superclass AbstractPathModelDAG, 
        # after calling super().__init__(...), which happens below.

        # We declare the _solution attribute, to be able to cache it.
        # Note that we make it private to this class (with underscore prefix), so that we can access it only with get_solution()
        self._solution = None      
        
        # To be able to apply the safety optimizations, we get the edges that 
        # must appear in some solution path. For this problem, these are the edges 
        # that have a non-zero flow lowerbound, since they appear in at least one source-to-sink path.
        trusted_edges_for_safety = self.G.get_non_zero_flow_edges(flow_attr=self.lb)

        # We initialize the super class with the graph, the number of paths, and the trusted edges.
        super().__init__(
            self.G, 
            num_paths, 
            optimization_options={"trusted_edges_for_safety": trusted_edges_for_safety},
            solver_options={"threads": threads}
            )

        # This method is called from the super class AbstractPathModelDAG
        self.create_solver_and_paths()

        # This method is called from the current class
        self._encode_inexact_flow_decomposition()

        # We encode the objective, from the current class
        self._encode_objective()
            
    def _encode_inexact_flow_decomposition(self):

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
            name_prefix="pi",
            lb=0,
            ub=maximum_allowed_path_weight,
        )

        # We encode that for each edge (u,v), the sum of the weights of the paths 
        # going through the edge is in the flow interval of the edge.
        for u, v, data in self.G.edges(data=True):
            # We ignore edges incident to the artificial global source and sink
            if (u, v) in self.G.source_sink_edges:
                continue

            # We encode that edge_vars[(u,v,i)] * path_weights_vars[(i)] = pi_vars[(u,v,i)]
            # Since this is a non-linear term, we will use the add_product_constraint method that 
            # will introduce additional constraints to linearize it for us, assuming that
            # 0 <= path_weights_vars[(i)] <= maximum_allowed_path_weight, which is the case
            for i in range(self.k):
                self.solver.add_binary_continuous_product_constraint(
                    binary_var=self.edge_vars[(u, v, i)],
                    continuous_var=self.path_weights_vars[(i)],
                    product_var=self.pi_vars[(u, v, i)],
                    lb=0,
                    ub=maximum_allowed_path_weight,
                    name=f"product_u={u}_v={v}_i={i}",
                )

            # We next encode that the sum of the weights of the paths going through the edge 
            # is at least the lowerbound, and at most the upper bound of the edge.
            
            # That is, the sum of the pi_vars for edge (u,v) is at least the lowerbound of the edge,
            self.solver.add_constraint(
                self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k)) >= data[self.lb],
                name=f"lowerbound_u={u}_v={v}",
            )

            # and at most the upperbound of the edge.
            self.solver.add_constraint(
                self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k)) <= data[self.ub],
                name=f"upperbound_u={u}_v={v}",
            )

    def _encode_objective(self):

        # We set the objective to minimize the sum of the path weights
        self.solver.set_objective(
            self.solver.quicksum(self.path_weights_vars[(i)] for i in range(self.k)), 
            sense="minimize",
        )

    def get_solution(self):

        if self._solution is not None:
            return self._solution
    
        solution_weights_dict = self.solver.get_variable_values("w", [int])
        # solution_weights_dict = self.solver.get_values(self.path_weights_vars)
        self._solution = {
            "paths": self.get_solution_paths(),
            "weights": [solution_weights_dict[i] for i in range(self.k)],
        }

        return self._solution
    
    def is_valid_solution(self):
        # AbstractPathModelDAG requires implementing a basic check that the solution is valid, 
        # to make sure there were no errors in the encoding.
        # This could be done by checking that, for each edge, the sum of the path weights going through it
        # is within the flow interval of the edge. self.solver.get_objective_value() could also be checked, 
        # to make sure the sum of the path weights indeed equals the objective value returned by the solver.
        
        return True
    
    def get_objective_value(self):
        # AbstractPathModelDAG requires implementing a method to get the objective value.
        # This could be done by returning the sum of the path weights, as returned by the solver.
        # This is useful if we want to compute the safe paths of any solution to our kInexactFlowDecomposition, 
        # namely those paths that are guaranteed to appear as subpath in some path of any optimal solution.
        
        return self.solver.get_objective_value()
    
    def get_lowerbound_k(self):
        # AbstractPathModelDAG requires implementing a method to get the lowerbound for the number of paths.
        # A possible implementation is as follows.
        # We know that each edge with lb > 0 must be covered by at least one path.
        # Therefore, a lowerbound is the minimum number of paths needed to cover all the edges with lb > 0.

        weight_function = {(u,v): 1 for u, v, data in self.G.edges(data=True) if data.get(self.lb, 0 ) > 0}
        return self.G.compute_max_edge_antichain(weight_function=weight_function)

def main():    
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("0", "a", lb=2, ub=6)
    graph.add_edge("0", "b", lb=7, ub=7)
    graph.add_edge("a", "b", lb=1, ub=2)
    graph.add_edge("a", "c", lb=3, ub=5)
    graph.add_edge("b", "c", lb=5, ub=9)
    graph.add_edge("c", "d", lb=3, ub=6)
    graph.add_edge("c", "1", lb=4, ub=7)
    graph.add_edge("d", "1", lb=2, ub=6)

    # We create a kInexactFlowDecomposition model
    # with the flow lower bounds in the attribute `lb` of the edges,
    # the flow upper bounds in the attribute `ub` of the edges,
    # and the number of paths to consider set to 3
    kifd_model = kInexactFlowDecomposition(graph, lb="lb", ub="ub", num_paths=3)

    # We solve it
    kifd_model.solve()

    # We process its solution
    if kifd_model.is_solved():
        print(kifd_model.get_solution())
        print(kifd_model.solve_statistics)
        print("model.is_valid_solution()", kifd_model.is_valid_solution())
    else:
        print("Model could not be solved.")


if __name__ == "__main__":
    main()