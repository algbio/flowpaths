import flowpaths as fp
import networkx as nx
from flowpaths.utils import safetypathcoverscycles as safety

def test1():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=1)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("b", "a", flow=2)
    graph.add_edge("a", "t", flow=1)
    # graph.add_edge("s", "t", flow=1)
    stDiGraph = fp.stDiGraph(graph)

    print(safety.maximal_safe_sequences_via_dominators(stDiGraph, set(graph.edges())))

def test3():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=3)
    graph.add_edge("a", "t", flow=3)
    graph.add_edge("s", "b", flow=6)
    graph.add_edge("b", "a", flow=2)
    graph.add_edge("a", "h", flow=2)
    graph.add_edge("h", "t", flow=6)
    graph.add_edge("b", "c", flow=4)
    graph.add_edge("c", "d", flow=4)
    graph.add_edge("c", "h", flow=4)
    graph.add_edge("d", "h", flow=0)
    graph.add_edge("d", "e", flow=4)
    graph.add_edge("e", "c", flow=5)
    graph.add_edge("e", "f", flow=4)
    graph.add_edge("f", "g", flow=4)
    graph.add_edge("g", "e", flow=4)
    graph.add_edge("s", "t", flow=4)
    stDiGraph = fp.stDiGraph(graph)

    X = set(graph.edges())
    safe_seqs = safety.maximal_safe_sequences_via_dominators(stDiGraph, X)
    for seq in safe_seqs:
        print("Safe sequence:", seq)
    
    # Now remove some edges from X
    print("New sequences")
    X.remove(('e', 'f'))
    X.remove(('f', 'g'))
    X.remove(('g', 'e'))
    safe_seqs = safety.maximal_safe_sequences_via_dominators(stDiGraph, X)
    for seq in safe_seqs:
        print("Safe sequence:", seq)

def test4():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "u", flow=3)
    graph.add_edge("u", "t", flow=3)
    graph.add_edge("u", "v", flow=6)
    graph.add_edge("v", "u", flow=2)
    graph.add_edge("v", "w", flow=2)
    graph.add_edge("w", "v", flow=6)
    graph.add_edge("w", "z", flow=6)
    graph.add_edge("z", "w", flow=6)

    graph.add_edge("z", "v", flow=6)
    stDiGraph = fp.stDiGraph(graph)

    X = set(stDiGraph.edges())
    safe_seqs = safety.maximal_safe_sequences_via_dominators(stDiGraph, X)
    for seq in safe_seqs:
        print("Safe sequence:", seq)
    
def test5():

    filename = "tests/cyclic_graphs/gt3.kmer15.(130000.132000).V23.E32.cyc100.graph"
    graph = fp.graphutils.read_graphs(filename)[0]

    stDiGraph = fp.stDiGraph(graph)
    X = set(stDiGraph.edges())
    X = set(graph.edges())
    safe_seqs = safety.maximal_safe_sequences_via_dominators(stDiGraph, X)
    for seq in safe_seqs:
        print("Safe sequence:", seq)


def test2():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a", flow=3)
    graph.add_edge("a", "t", flow=3)
    graph.add_edge("s", "b", flow=6)
    graph.add_edge("b", "a", flow=2)
    graph.add_edge("a", "h", flow=2)
    graph.add_edge("h", "t", flow=6)
    graph.add_edge("b", "c", flow=4)
    graph.add_edge("c", "d", flow=4)
    graph.add_edge("c", "h", flow=4)
    graph.add_edge("d", "h", flow=0)
    graph.add_edge("d", "e", flow=4)
    graph.add_edge("e", "c", flow=5)
    graph.add_edge("e", "f", flow=4)
    graph.add_edge("f", "g", flow=4)
    graph.add_edge("g", "e", flow=4)

    lae_model = fp.kLeastAbsErrorsCycles(
        G=graph, 
        flow_attr="flow", 
        k=3, 
        weight_type=int,
        )
    lae_model.solve()
    process_solution(graph, lae_model)

def process_solution(graph, model: fp.kLeastAbsErrors):
    if model.is_solved():
        print(model.get_solution())
        print("model.is_valid_solution()", model.is_valid_solution())
        fp.utils.draw(
            G=graph,
            filename=f"least-abs_errors_cycles_example.pdf",
            flow_attr="flow",
            paths=model.get_solution()["walks"],
            weights=model.get_solution()["weights"],
            draw_options={
            "show_graph_edges": True,
            "show_edge_weights": False,
            "show_path_weights": False,
            "show_path_weight_on_first_edge": True,
            "pathwidth": 2,
        })
    else:
        print("Model could not be solved.")

def main():
    test1()
    test3()
    test2()
    test4()
    test5()

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    main()
