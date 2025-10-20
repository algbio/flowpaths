import flowpaths as fp
import networkx as nx

def example1():

    ##############
    # Example 1  #
    ##############

    # We create a graph where weights (or flow values are on the nodes)
    graph = nx.DiGraph()
    graph.add_node("s", flow=13)
    graph.add_node("a", flow=6)
    graph.add_node("b", ) # flow=9 # Note that we are not adding flow values to this node
    graph.add_node("c", flow=13)
    graph.add_node("d", flow=6)
    graph.add_node("t", flow=13)

    # We edges (notice that we do not add flow values to them)
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

    # We create a node expanded graph, where the weights are taken from the attribute "flow"
    neGraph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")

    # This is a constraint that we want to enforce in the solution,
    # in terms of nodes. Notice that the nodes are not enforced to appear consecutively in a solution path.
    subpath_constraints_nodes=[['s', 'b', 'c', 'd']]

    # We transform the constraints into constraints in the node expanded graph
    ne_subpath_constraints_nodes = neGraph.get_expanded_subpath_constraints(subpath_constraints_nodes)    

    # We solve the problem on the node expanded graph
    # To play with, we also set the subpath constraint coverage to 0.75, meaning that only 75% of the nodes in the constraint need to be covered by some solution path
    ne_mfd_model_nodes = fp.MinFlowDecomp(
        neGraph, 
        flow_attr="flow",
        elements_to_ignore=neGraph.edges_to_ignore,
        subpath_constraints_coverage=0.75,
        subpath_constraints=ne_subpath_constraints_nodes,
        )
    ne_mfd_model_nodes.solve()
    process_expanded_solution(neGraph, ne_mfd_model_nodes)

    # This is a constraint that we want to enforce in the solution,
    # in terms of edges. Notice that because of acyclicty the edges are now enforced 
    # to appear consecutively in a solution path
    subpath_constraints_edges=[[('a', 'c'), ('c', 't')]]

    # We transform the constraints into constraints in the node expanded graph
    ne_subpath_constraints_edges = neGraph.get_expanded_subpath_constraints(subpath_constraints_edges)

    # We solve the problem on the node expanded graph  
    ne_mfd_model_edges = fp.MinFlowDecomp(
        neGraph, 
        flow_attr="flow",
        elements_to_ignore=neGraph.edges_to_ignore,
        subpath_constraints=ne_subpath_constraints_edges,
        )
    ne_mfd_model_edges.solve()
    process_expanded_solution(neGraph, ne_mfd_model_edges)

    # We also use the built-in handling of node-weighted graphs, via the `flow_attr_origin` parameter
    mfd_model_edges = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow",
        flow_attr_origin="node",
        subpath_constraints=subpath_constraints_edges,
        )
    mfd_model_edges.solve()

    assert(mfd_model_edges.get_objective_value() == ne_mfd_model_edges.get_objective_value())

def example2():

    ##############
    # Example 2  #
    ############## 

    # We now also add lengths to the nodes (in addition to flow values)
    graph = nx.DiGraph()
    graph.add_node("s", flow=13, length=3)
    graph.add_node("a", flow=6,  length=4)
    graph.add_node("b", flow=9,  length=10)
    graph.add_node("c", flow=13, length=16)
    graph.add_node("d", flow=6,  length=9)
    graph.add_node("t", flow=13, length=12)

    # We edges (notice that we do not add flow values to them)
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

    # We create a node expanded graph, where the weights are taken from the attribute "flow"
    neGraph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow", node_length_attr="length")

    # This is a constraint that we want to enforce in the solution,
    # in terms of edges. Notice that because of acyclicity the edges are now enforced 
    # to appear consecutively in a solution path
    subpath_constraints_edges=[[('a', 'c'), ('c', 't')]]

    # We transform the constraints into constraints in the node expanded graph
    ne_subpath_constraints_edges = neGraph.get_expanded_subpath_constraints(subpath_constraints_edges)

    # We solve the problem on the node expanded graph
    # We also set the subpath constraint coverage to 0.7 in terms of length, because we pass
    # `length_attr="length"`. This means that only 70% of the length of the edges in the constraint need to be covered by some solution path
    ne_mfd_model_edges = fp.MinFlowDecomp(
        neGraph, 
        flow_attr="flow",
        elements_to_ignore=neGraph.edges_to_ignore,
        subpath_constraints=ne_subpath_constraints_edges,
        subpath_constraints_coverage_length=0.7,
        length_attr="length",
        )

    ne_mfd_model_edges.solve()
    process_expanded_solution(neGraph, ne_mfd_model_edges)

def process_expanded_solution(neGraph: fp.NodeExpandedDiGraph, model: fp.MinFlowDecomp):
    if model.is_solved():
        solution = model.get_solution()
        expanded_paths = solution["paths"]
        original_paths = neGraph.get_condensed_paths(expanded_paths)
        print("Expanded paths:", expanded_paths)
        print("Original paths:", original_paths)
        print("Weights:", solution["weights"])
    else:
        print("Model could not be solved.")

def main():
    example1()
    example2()

if __name__ == "__main__":
    main()