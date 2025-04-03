import flowpaths as fp
import networkx as nx

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

# We create a graph where weights (or flow values are on the nodes)
# notice that the flow values have some small errors
graph = nx.DiGraph()
graph.add_node("s", flow=15)
graph.add_node("a", flow=6)
graph.add_node("b", ) # flow=9 # Note that we are not adding flow values to this node. This is supported, and the edge for this node will be added to edges_to_ignore
graph.add_node("c", flow=13)
graph.add_node("d", flow=2)
graph.add_node("t", flow=20)

# We add graph edges (notice that we do not add flow values to them)
graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

# We create a node-expanded graph, where the weights are taken from the attribute "flow"
neGraph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")

# We correct the node-expanded graph
correction_model = fp.MinErrorFlow(
    neGraph, 
    flow_attr="flow",
    edges_to_ignore=neGraph.edges_to_ignore,
    )
correction_model.solve()
corrected_neGraph: fp.NodeExpandedDiGraph = correction_model.get_corrected_graph()
# Or just: corrected_neGraph = correction_model.get_corrected_graph()

# This is a constraint in the original graph that we want to enforce in the solution
subpath_constraints=[[('a', 'c'), ('c', 't')]]

# We solve the problem on the corrected_neGraph 
ne_mfd_model_edges = fp.MinFlowDecomp(
    corrected_neGraph,
    flow_attr="flow",
    edges_to_ignore=corrected_neGraph.edges_to_ignore,
    subpath_constraints=corrected_neGraph.get_expanded_subpath_constraints(subpath_constraints),
    )
ne_mfd_model_edges.solve()
process_expanded_solution(neGraph, ne_mfd_model_edges)