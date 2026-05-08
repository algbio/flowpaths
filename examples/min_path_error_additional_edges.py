import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=4)
graph.add_edge("s", "b", flow=6)
graph.add_edge("a", "t", flow=3)
graph.add_edge("b", "t", flow=7)

mpe_model = fp.kMinPathError(graph, 
                flow_attr="flow", 
                k=3, 
                weight_type=int)
mpe_model.solve()
if mpe_model.is_solved():
    print(mpe_model.get_solution())
    assert mpe_model.get_objective_value() == 2, "Expected objective value of 0 when no additional edges are used and all flow can be explained by paths in the original graph."


mpe_model_2 = fp.kMinPathError(graph, 
                flow_attr="flow", 
                k=3, 
                additional_edges=[("a", "b")],
                weight_type=int)
mpe_model_2.solve()
if mpe_model_2.is_solved():
    print(mpe_model_2.get_solution())
    assert mpe_model_2.get_objective_value() == 1, "Expected objective value of 1 when additional edges are used and some flow cannot be explained by paths in the original graph."

ngraph = nx.DiGraph()
ngraph.add_node("s", flow=10)
ngraph.add_node("a", flow=3)
ngraph.add_node("b", flow=6)
ngraph.add_node("t", flow=11)

# We edges (notice that we do not add flow values to them)
ngraph.add_edges_from([("s", "a"), ("s", "b"), ("a", "t"), ("b", "t")])

subpath_constraints = [["s", "a", "b", "t"]]
mpe_model_3 = fp.kMinPathError(ngraph, 
                flow_attr="flow", 
                k=2, 
                flow_attr_origin="node",
                subpath_constraints=subpath_constraints,
                additional_edges=[("a", "b")],
                weight_type=int)
mpe_model_3.solve()
if mpe_model_3.is_solved():
    print(mpe_model_3.get_solution())
    print(mpe_model_3.get_objective_value())
    assert mpe_model_3.get_objective_value() == 4, "Expected objective value of 4 when additional edges are used and some flow cannot be explained by paths in the original graph."
