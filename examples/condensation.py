import flowpaths as fp
import networkx as nx
from flowpaths.utils import safetypathcoverscycles as safety

def test1():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "t")

    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    graph.add_edge("s", "c")
    graph.add_edge("c", "d")
    graph.add_edge("d", "c")
    graph.add_edge("d", "t")

    graph.add_edge("s", "e")
    graph.add_edge("e", "f")
    graph.add_edge("f", "g")
    graph.add_edge("g", "e")
    graph.add_edge("g", "t")

    graph.add_edge("f", "d")
    
    stDiGraph = fp.stDiGraph(graph)
    assert stDiGraph.get_width() == 5

    edges_to_ignore = [ ("f", "d") ]
    assert stDiGraph.get_width(edges_to_ignore=edges_to_ignore) == 4

    edges_to_ignore = [ ("f", "d"), ("s", "t") ]
    assert stDiGraph.get_width(edges_to_ignore=edges_to_ignore) == 3

    edges_to_ignore = [ ("f", "d"), ("s", "t"), ("c", "d") ]
    assert stDiGraph.get_width(edges_to_ignore=edges_to_ignore) == 3

    sequences = [ 
        [('d', 'c'), ('c', 'd'), ('d', 't')],
        [('s', 'c')],
        [('a', 't')],
        [('s', 'a')],
        [('g', 'e'), ('e', 'f')],
    ]
    incompatible_sequences = stDiGraph.get_longest_incompatible_sequences(sequences)
    print(f"Incompatible sequences: {incompatible_sequences}")
    assert len(incompatible_sequences) == 3

def test2():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("s", "a")
    graph.add_edge("a", "t")

    graph.add_edge("a", "a")

    graph.add_edge("s", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", "b")

    graph.add_edge("b", "t")
    graph.add_edge("c", "t")

    graph.add_edge("b", "a")
    graph.add_edge("c", "a")
    
    stDiGraph = fp.stDiGraph(graph)
    assert stDiGraph.get_width() == 5

    edges_to_ignore = [ ("s", "a"), ("a", "t") ]
    assert stDiGraph.get_width(edges_to_ignore=edges_to_ignore) == 4

    sequences = [ 
        [('s', 'a'), ('a', 'a'), ('a', 't')],
    ]
    incompatible_sequences = stDiGraph.get_longest_incompatible_sequences(sequences)
    print(f"Incompatible sequences: {incompatible_sequences}")
    assert len(incompatible_sequences) == 1

    sequences = [ 
        [('s', 'a'), ('a', 'a'), ('a', 't')],
        [('b','a'), ('a', 't')],
        [('b','a'), ('a','a'), ('a', 't')],
        [('c','a'), ('a', 't')],
        [('b', 'c'), ('c', 'b')]
    ]
    incompatible_sequences = stDiGraph.get_longest_incompatible_sequences(sequences)
    print(f"Incompatible sequences: {incompatible_sequences}")
    assert len(incompatible_sequences) == 3

def test3():
    graph = fp.graphutils.read_graphs("tests/cyclic_graphs/gt4.kmer15.(0.10000).V1096.E1622.mincyc100.e1.0.graph")[0]
    print("graph id", graph.graph["id"])
    stDiGraph = fp.stDiGraph(graph)
    print("Graph width", stDiGraph.get_width())
    print("Is acyclic", nx.is_directed_acyclic_graph(graph))
    print("get_number_of_nontrivial_SCCs", stDiGraph.get_number_of_nontrivial_SCCs())
    print("get_size_of_largest_SCC", stDiGraph.get_size_of_largest_SCC())

def main():
    test1()
    test2()
    test3()
    




if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    main()
