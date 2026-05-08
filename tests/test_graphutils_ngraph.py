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
    assert graph.graph["constraints"] == [["0", "1", "2"]]


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
    assert graphs[0].graph["constraints"] == [["0", "1"]]
    assert graphs[1].graph["id"] == "graph number = 1"
    assert graphs[1].graph["n"] == 3
    assert graphs[1].graph["m"] == 2


def test_read_intron_graph_parses_real_folder_constraints_as_node_lists():
    graph_dir = Path(__file__).parent / "acyclic_graphs" / "SIRV.ONT_R10.real_exp_downsample" / "SIRV1.1.SIRV1"

    graph = graphutils.read_intron_graph(graph_dir)

    assert graph.graph["id"] == "SIRV1.1.SIRV1"
    assert graph.nodes["0"]["flow"] == 60.0
    assert graph.nodes["0"]["type"] == "intron"
    assert graph.has_edge("10", "5")
    assert graph.graph["constraints"][0] == ["11", "3", "4", "13"]
    assert ["1"] in graph.graph["constraints"]
    assert graph.graph["groundtruth_paths_nodes"][0] == ["9", "7", "1", "0"]
    assert graph.graph["groundtruth_paths_edges"][0] == [("9", "7"), ("7", "1"), ("1", "0")]
    assert graph.graph["groundtruth_weights"] == [5, 64, 54, 6]
    assert graph.graph["reference_edges"][0] == ("7", "1")
    assert graph.graph["additional_edges"] == [("7", "5"), ("4", "14")]


def test_read_intron_graph_parses_reference_edges_and_additional_subset(tmp_path: Path):
    graph_dir = tmp_path / "toy_graph"
    graph_dir.mkdir()

    (graph_dir / "vertices.tsv").write_text(
        "\n".join(
            [
                "vertex_id\ttype\tchr\tstart\tend\tweight",
                "0\tintron\tchr1\t10\t20\t5",
                "1\tintron\tchr1\t30\t40\t7",
                "2\tpolya\tchr1\t50\t50\t3",
            ]
        )
        + "\n"
    )
    (graph_dir / "edges.tsv").write_text(
        "\n".join(
            [
                "u\tv",
                "0\t1",
            ]
        )
        + "\n"
    )
    (graph_dir / "read_subpaths.tsv").write_text(
        "\n".join(
            [
                "read_count\tis_fl\tstatus\tpath\tpath_simple\tmissing_vertices\tmissing_edges",
                "4\t1\tok\t0-1-2\t0,1,2\t0\t0",
                "2\t0\tok\t1\t1\t0\t0",
            ]
        )
        + "\n"
    )
    (graph_dir / "paths.tsv").write_text(
        "\n".join(
            [
                "transcript_id\tcount\tcount_scaled\tstatus\tpath\tpath_simple\tmissing_vertices\tmissing_edges",
                "tx1\t11\t4\tok\t0-1-2\t0,1,2\t0\t0",
                "tx2\t5\t2\tok\t1\t1\t0\t0",
            ]
        )
        + "\n"
    )
    (graph_dir / "ref_edges.tsv").write_text(
        "\n".join(
            [
                "kind\tu_start\tu_end\tv_start\tv_end\tstatus\tu_id\tv_id",
                "intron\t10\t20\t30\t40\tin_graph\t0\t1",
                "terminal\t30\t40\t50\t50\tmissing_edge\t1\t2",
                "terminal\t30\t40\t60\t60\tmissing_vertex\t1\t*",
            ]
        )
        + "\n"
    )

    graph = graphutils.read_intron_graph(graph_dir)

    assert graph.graph["constraints"] == [["0", "1", "2"], ["1"]]
    assert graph.graph["groundtruth_paths_nodes"] == [["0", "1", "2"], ["1"]]
    assert graph.graph["groundtruth_paths_edges"] == [[("0", "1"), ("1", "2")], []]
    assert graph.graph["groundtruth_weights"] == [4, 2]
    assert graph.graph["reference_edges"] == [("0", "1")]
    assert graph.graph["additional_edges"] == [("1", "2")]


def test_read_intron_graphs_reads_all_graph_subfolders():
    graphs_root = Path(__file__).parent / "acyclic_graphs" / "SIRV.ONT_R10.real_exp_downsample"

    graphs = graphutils.read_intron_graphs(graphs_root)

    assert len(graphs) == 8
    assert graphs[0].graph["id"] == "SIRV1.1.SIRV1"
    assert graphs[-1].graph["id"] == "SIRV7.3.region_147969_148930"
