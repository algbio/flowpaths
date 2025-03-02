import flowpaths as fp
import networkx as nx

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=6)
graph.add_edge("a", "b", flow=22)
graph.add_edge("s", "b", flow=7)
graph.add_edge("a", "c", flow=4)
graph.add_edge("b", "c", flow=29)
graph.add_edge("c", "d", flow=26)
graph.add_edge("d", "t", flow=6)
graph.add_edge("c", "t", flow=7)

mpe_model = fp.kMinPathError(graph, flow_attr="flow", k=4, weight_type=int)
mpe_model.solve()
if mpe_model.is_solved():
    print(mpe_model.get_solution())

mpe_model_2 = fp.kMinPathError(
    graph, 
    flow_attr="flow", 
    k=4, 
    weight_type=int,
    additional_starts=['a'],
    additional_ends=['d'])
mpe_model_2.solve()
if mpe_model_2.is_solved():
    print(mpe_model_2.get_solution())

graph10 = nx.DiGraph()
graph10.add_edge("s", "a", flow=6)
graph10.add_edge("a", "b", flow=12)
graph10.add_edge("s", "b", flow=7)
graph10.add_edge("a", "c", flow=4)
graph10.add_edge("b", "c", flow=19)
graph10.add_edge("c", "d", flow=16)
graph10.add_edge("d", "t", flow=6)
graph10.add_edge("c", "t", flow=7)

mpe_model_10 = fp.kMinPathError(
    graph10, 
    flow_attr="flow", 
    k=4, 
    weight_type=int,
    additional_starts=['a'],
    additional_ends=['d'])
mpe_model_10.solve()
if mpe_model_10.is_solved():
    print(mpe_model_10.get_solution())