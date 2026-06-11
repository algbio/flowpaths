import flowpaths as fp
import networkx as nx

def example1():

    ##############
    # Example 1  #
    ##############

    # We create a graph where weights are on the nodes, in the attribute called "flow" (the don't need to satisfy any flow conservation constraints, they are just weights). We want to find a flow decomposition of this graph into paths, such that the sum of the weights of the paths going through each node is as close as possible to the "flow" value on that node. We also want to enforce that there is a path in the solution that goes through the nodes s, b, c, d (not necessarily consecutively).
    graph = nx.DiGraph()
    graph.add_node("s", flow=13)
    graph.add_node("a", flow=6)
    graph.add_node("b", ) # flow=9 # It's supported to skip the flow value on some nodes, in which case they will be ignored in the objective function (i.e. they will not contribute to the error, but they might still be covered by the paths in the solution)
    graph.add_node("c", flow=13)
    graph.add_node("d", flow=6)
    graph.add_node("t", flow=13)

    # We edges (notice that we do not add flow values to them)
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

    # This is a constraint that we want to enforce in the solution,
    # in terms of nodes. Notice that the nodes are not enforced to appear consecutively in a solution path.
    subpath_constraints_nodes=[['s', 'b', 'c', 'd']]

    # We create the model and solve it.
    model = fp.kLeastAbsErrors(
        G=graph, 
        k=None, # this sets k (the number of paths) as the smallest for which there exists such paths); change to a given integer to enforce a specific number of paths
        flow_attr="flow", # This means take the weights from the "flow" attribute on the nodes
        flow_attr_origin="node", # This means weights on nodes
        weight_type=int, # This means that the weights of the solution paths are integers (change to float if they are not)
        subpath_constraints=subpath_constraints_nodes, # Remove if you don't have subpath constraints to enforce
        )
    model.solve()
    
    # We get the solution 
    assert model.is_solved(), "kLeastAbsErrors did not solve the instance"
    assert model.is_valid_solution(), "Solution should be a valid flow decomposition"
    solution = model.get_solution()
    print("Paths:", solution["paths"])
    print("Weights:", solution["weights"])
    objective_value = model.get_objective_value()
    print("Objective value:", objective_value)

def main():
    example1()

if __name__ == "__main__":
    main()