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

def main():
    test1()

if __name__ == "__main__":
    # Configure logging
    fp.utils.configure_logging(
        level=fp.utils.logging.DEBUG,
        log_to_console=True,
    )
    main()
