import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=60)
graph.add_edge("a", "b", flow=20)
graph.add_edge("s", "b", flow=70)
graph.add_edge("a", "c", flow=40)
graph.add_edge("b", "c", flow=90)
graph.add_edge("c", "d", flow=60)
graph.add_edge("d", "t", flow=60)
graph.add_edge("c", "t", flow=70)

graph.add_edge("a", "d", flow=1)

mpe_model = fp.kMinPathError(graph, flow_attr="flow", k=4, weight_type=int)
mpe_model.solve()
if mpe_model.is_solved():
    print(mpe_model.get_solution())

mpe_model_2 = fp.kMinPathError(
    graph, 
    flow_attr="flow", 
    k=3, 
    weight_type=int,
    elements_to_ignore=[("a", "d")])
mpe_model_2.solve()
if mpe_model_2.is_solved():
    print(mpe_model_2.get_solution())
