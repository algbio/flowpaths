import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=6)
    graph.add_edge("s", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "t", flow=7)
    graph.add_edge("d", "t", flow=6)

    # We create a Minimum Flow Decomposition solver with default settings,
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges,
    # and requiring that the subpath (a,c,e) is present in the solution. 
    # NOTE: We pass this as a list made up of a single list of edges ("a", "c"),("c", "e")
    # NOTE: The edges in the subpath do not need to form a contiguous path.
    mfd_model = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow", 
        subpath_constraints=[[("a", "c"),("c", "t")]]
        )
    mfd_model.solve() # We solve it
    process_solution(mfd_model) # We process its solution

    # We now create another solver, but require only half of the edges of each subpath to appear in the some solution path.
    mfd_model2 = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow", 
        subpath_constraints=[[("a", "c"),("c", "t")]], 
        subpath_constraints_coverage=0.5, 
        optimize_with_greedy=False
        )
    mfd_model2.solve()
    process_solution(mfd_model2) # We process its solution

    # We now let greedy try to solve it first
    mfd_model3 = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow", 
        subpath_constraints=[[("a", "c"),("c", "t")]], 
        subpath_constraints_coverage=0.5
        )
    mfd_model3.solve()
    process_solution(mfd_model3) # We process its solution

    # We now pass a non-contiguous subpath constraint
    mfd_model4 = fp.MinFlowDecomp(
        graph, 
        flow_attr="flow", 
        subpath_constraints=[[("s", "a"), ("c", "t")]]
        )
    mfd_model4.solve()
    process_solution(mfd_model4) # We process its solution


    # We now create another graph, where the edges also have lengths
    # and we express the subpath coverage fraction in terms of the edge lengths
    graph2 = nx.DiGraph()
    graph2.graph["id"] = "simple_graph"
    graph2.add_edge("s", "a", flow=3, length=2)
    graph2.add_edge("a", "c", flow=3, length=4) # in [("a", "c"),("c", "e")]
    graph2.add_edge("s", "b", flow=2, length=3)
    graph2.add_edge("b", "c", flow=2, length=7)
    graph2.add_edge("c", "d", flow=3, length=2)
    graph2.add_edge("d", "t", flow=3, length=1)
    graph2.add_edge("c", "e", flow=2, length=16) # in [("a", "c"),("c", "e")]
    graph2.add_edge("e", "t", flow=2, length=2)

    mfd_model5 = fp.MinFlowDecomp(
        graph2, 
        flow_attr="flow", 
        edge_length_attr="length", 
        subpath_constraints=[[("a", "c"),("c", "e")]], 
        subpath_constraints_coverage_length=0.7
        )
    mfd_model5.solve()
    process_solution(mfd_model5)

    mfd_model6 = fp.MinFlowDecomp(
        graph2, 
        flow_attr="flow", 
        edge_length_attr="length", 
        subpath_constraints=[[("a", "c"),("c", "e")]], 
        subpath_constraints_coverage_length=0.7, 
        optimize_with_greedy=False
        )
    # Note that edge ("c", "e") has length 16, which is 0.8 * subpath length (4 + 16). 
    # Thus already covering the edge ("c", "e") with a coverage_length = 0.7 is enough to satisfy the constraint.
    mfd_model6.solve()
    process_solution(mfd_model6)

def process_solution(model: fp.MinFlowDecomp):
    if model.is_solved():
        solution = model.get_solution()
        print(
            "Solution paths, weights, solve statistics: ",
            solution[0],
            solution[1],
            model.solve_statistics,
        )
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()