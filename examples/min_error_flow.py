import flowpaths as fp
import networkx as nx

def process_solution(graph: nx.DiGraph, model: fp.MinErrorFlow):
    if model.is_solved():
        solution = model.get_solution()
        print(solution["graph"].edges(data=True))
        print("error", solution["error"])
        print("objective_value", solution["objective_value"])
        fp.utils.draw_solution(graph, filename="uncorrected_graph.pdf", flow_attr="flow", draw_options={"show_edge_weights": True})
        fp.utils.draw_solution(solution["graph"], filename="corrected_graph.pdf", flow_attr="flow", draw_options={"show_edge_weights": True})
    else:
        print("Model could not be solved.")

graph = nx.DiGraph()
graph.add_edge("s", "a", flow=7)
graph.add_edge("s", "b", flow=7)
graph.add_edge("a", "b", flow=2)
graph.add_edge("a", "c", flow=4)
graph.add_edge("b", "c", flow=9)
graph.add_edge("c", "d", flow=7)
graph.add_edge("c", "t", flow=7)
graph.add_edge("d", "t", flow=6)

# We create a the Minimum Error Flow solver with default settings
correction_model = fp.MinErrorFlow(graph, flow_attr="flow")
correction_model.solve()

if correction_model.is_solved():
    corrected_graph = correction_model.get_corrected_graph()
    mfd_model = fp.MinFlowDecomp(corrected_graph, flow_attr="flow")
    mfd_model.solve()
    if mfd_model.is_solved():
        print(mfd_model.get_solution())

# We create a the Minimum Error Flow solver, by also requiring that 
# the number of different flow values used in the correction is small
# (parameter different_flow_values_epsilon)
correction_model_diff_flow_values = fp.MinErrorFlow(
    graph, 
    flow_attr="flow",
    weight_type=int,
    few_flow_values_epsilon = 0.25,
    )
correction_model_diff_flow_values.solve()

# We process its solution
process_solution(graph, correction_model_diff_flow_values)

