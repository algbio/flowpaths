import flowpaths as fp
import networkx as nx

def test_decomposition_models():

    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
        log_file="log_internal_node_weights.log",
    )

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
    # in terms of edges. Notice that because of acyclicty the edges are now enforced 
    # to appear consecutively in a solution path
    subpath_constraints_edges=[[('a', 'c'), ('c', 't')]]

    # We transform the constraints into constraints in the node expanded graph
    ne_subpath_constraints_edges = neGraph.get_expanded_subpath_constraints(subpath_constraints_edges)

    for model_type in [fp.kFlowDecomp, fp.kLeastAbsErrors, fp.kMinPathError]:
            

        # We solve the problem on the node expanded graph  
        ne_model = model_type(
            neGraph, 
            k=3,
            flow_attr="flow",
            elements_to_ignore=neGraph.edges_to_ignore,
            subpath_constraints=ne_subpath_constraints_edges,
            )
        ne_model.solve()

        # We also use the built-in handling of node-weighted graphs, via the `flow_attr_origin` parameter
        model = model_type(
            graph, 
            k=3,
            flow_attr="flow",
            flow_attr_origin="node",
            subpath_constraints=subpath_constraints_edges,
            )
        model.solve()

        fp.utils.logger.debug(f"Model type: {model_type.__name__}")
        fp.utils.logger.debug(f"Objective value: {ne_model.get_objective_value()}")
        fp.utils.logger.debug(f"Objective value ne: {model.get_objective_value()}")
        assert(ne_model.get_objective_value() == model.get_objective_value())
        assert(sum(ne_model.get_solution()["weights"]) == sum(model.get_solution()["weights"]))
        assert(len(ne_model.get_solution()["paths"]) == len(model.get_solution()["paths"]))

def test_min_error_flow():

    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
        log_file="log_internal_node_weights.log",
    )

    ##############
    # Example 2  #
    ##############

    # We create a graph where weights (or flow values are on the nodes)
    graph = nx.DiGraph()
    graph.add_node("s", flow=13)
    graph.add_node("a", flow=9)
    graph.add_node("b", ) # flow=9 # Note that we are not adding flow values to this node
    graph.add_node("c", flow=13)
    graph.add_node("d", flow=3)
    graph.add_node("t", flow=18)

    # We edges (notice that we do not add flow values to them)
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

    model = fp.MinErrorFlow(
        graph,
        flow_attr="flow",
        flow_attr_origin="node",
    )
    model.solve()

    # We create a node expanded graph, where the weights are taken from the attribute "flow"
    neGraph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")

    ne_model = fp.MinErrorFlow(
        neGraph,
        flow_attr="flow",
        elements_to_ignore=neGraph.edges_to_ignore,
    )
    ne_model.solve()

    fp.utils.logger.debug(f"Objective value (node expanded): {ne_model.get_objective_value()}")
    fp.utils.logger.debug(f"Objective value (expanded internally): {model.get_objective_value()}")
    assert(ne_model.get_objective_value() == model.get_objective_value())

def test_min_path_cover():

    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
        log_file="log_internal_node_weights.log",
    )

    ##############
    # Example 3  #
    ##############

    # We create a graph where weights (or flow values are on the nodes)
    graph = nx.DiGraph()
    graph.add_node("s", flow=13)
    graph.add_node("a", flow=6)
    graph.add_node("b", flow=9)
    graph.add_node("c", flow=13)
    graph.add_node("d", flow=6)
    graph.add_node("t", flow=13)

    # We edges (notice that we do not add flow values to them)
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

    model = fp.MinPathCover(
        graph,
        cover_type="node",
    )
    model.solve()

    # We create a node expanded graph, where the weights are taken from the attribute "flow"
    neGraph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")
    ne_model = fp.MinPathCover(
        neGraph,
        elements_to_ignore=neGraph.edges_to_ignore,
    )
    ne_model.solve()

    fp.utils.logger.debug(f"Objective value (node expanded): {ne_model.get_objective_value()}")
    fp.utils.logger.debug(f"Objective value (expanded internally): {model.get_objective_value()}")
    assert(ne_model.get_objective_value() == model.get_objective_value())
    

def main():
    test_decomposition_models()
    test_min_error_flow()
    test_min_path_cover()

if __name__ == "__main__":
    main()