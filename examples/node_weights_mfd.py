import flowpaths as fp
import networkx as nx

def main():
    graph = nx.DiGraph()
    graph.add_node("s", flow=13, length=3)
    graph.add_node("a", flow=6,  length=4)
    graph.add_node("b", flow=9,  length=10)
    graph.add_node("c", flow=13, length=16)
    graph.add_node("d", flow=6,  length=9)
    graph.add_node("t", flow=13, length=12)

    # Adding edges
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

    neGraph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")

    subpath_constraints_nodes=[['s', 'b', 'c', 'd']]
    ne_subpath_constraints_nodes = neGraph.get_expanded_subpath_constraints_nodes(subpath_constraints_nodes)
    

    ne_mfd_model_nodes = fp.MinFlowDecomp(
        neGraph, 
        flow_attr="flow",
        edges_to_ignore=neGraph.edges_to_ignore,
        subpath_constraints=ne_subpath_constraints_nodes,
        subpath_constraints_coverage=1.0,
        subpath_constraints_coverage_length=0.7,
        edge_length_attr="length",
        )
    ne_mfd_model_nodes.solve()
    process_expanded_solution(neGraph, ne_mfd_model_nodes)

    subpath_constraints_edges=[[('a', 'c'), ('c', 't')]]
    ne_subpath_constraints_edges = neGraph.get_expanded_subpath_constraints_edges(subpath_constraints_edges)

    print("ne_subpath_constraints_edges", ne_subpath_constraints_edges)
    ne_mfd_model_edges = fp.MinFlowDecomp(
        neGraph, 
        flow_attr="flow",
        edges_to_ignore=neGraph.edges_to_ignore,
        subpath_constraints=ne_subpath_constraints_edges,
        subpath_constraints_coverage=1.0,
        subpath_constraints_coverage_length=0.7,
        edge_length_attr="length",
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
        # fp.utils.graphutils.draw_solution_basic(model.G, flow_attr="flow", paths = solution["paths"], weights = solution["weights"], id = model.G.graph["id"])
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()