from pathlib import Path

import flowpaths.utils.graphutils as graphutils


def test_read_ngraph_parses_nodes_edges_and_constraints():
    block = [
        "# graph number = 0\n",
        "# source = unit-test\n",
        "#S 0 1 2\n",
        "3\n",
        "#NODES id flow\n",
        "0 5.0\n",
        "1 7.0\n",
        "2 11.0\n",
        "#EDGES u v flow\n",
        "0 1 1.0\n",
        "1 2 2.0\n",
    ]

    graph = graphutils.read_ngraph(block)

    assert graph.graph["id"] == "graph number = 0"
    assert graph.graph["n"] == 3
    assert graph.graph["m"] == 2
    assert graph.nodes["0"]["flow"] == 5.0
    assert graph.nodes["1"]["flow"] == 7.0
    assert graph.nodes["2"]["flow"] == 11.0
    assert graph["0"]["1"]["flow"] == 1.0
    assert graph["1"]["2"]["flow"] == 2.0
    assert graph.graph["constraints"] == [[("0", "1"), ("1", "2")]]


def test_read_ngraphs_parses_multiple_blocks(tmp_path: Path):
    ngraph_path = tmp_path / "two_graphs.ngraph"
    ngraph_path.write_text(
        "\n".join(
            [
                "# graph number = 0",
                "#S 0 1",
                "2",
                "#NODES id flow",
                "0 2.0",
                "1 3.0",
                "#EDGES u v flow",
                "0 1 1.0",
                "",
                "# graph number = 1",
                "3",
                "#NODES id flow",
                "0 1.0",
                "1 1.0",
                "2 1.0",
                "#EDGES u v flow",
                "0 1 1.0",
                "1 2 1.0",
            ]
        )
        + "\n"
    )

    graphs = graphutils.read_ngraphs(str(ngraph_path))

    assert len(graphs) == 2
    assert graphs[0].graph["id"] == "graph number = 0"
    assert graphs[0].graph["constraints"] == [[("0", "1")]]
    assert graphs[1].graph["id"] == "graph number = 1"
    assert graphs[1].graph["n"] == 3
    assert graphs[1].graph["m"] == 2
