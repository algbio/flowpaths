from itertools import count
import networkx as nx

bigNumber = 1 << 32


def read_graph(graph_raw) -> nx.DiGraph:
    # Input format is: ['#Graph id\n', 'n\n', 'u_1 v_1 w_1\n', ..., 'u_k v_k w_k\n']
    id = graph_raw[0].strip("# ").strip()
    n = int(graph_raw[1])

    G = nx.DiGraph()
    G.graph["id"] = id

    if n == 0:
        print("Graph %s has 0 vertices.", id)
        return G

    for edge in graph_raw[2:]:
        u, v, w = list(map(lambda x: int(x), edge.split(" ")))
        G.add_edge(u, v, flow=w)

    return G


def read_graphs(filename):
    f = open(filename, "r")
    lines = f.readlines()
    f.close()
    graphs = []

    # Assume: every file contains at least one graph
    i, j = 0, 1
    while True:
        if lines[j].startswith("#"):
            graphs.append(read_graph(lines[i:j]))
            i = j
        j += 1
        if j == len(lines):
            graphs.append(read_graph(lines[i:j]))
            break

    return graphs


def min_cost_flow(G: nx.DiGraph, s, t):

    flowNetwork = nx.DiGraph()

    flowNetwork.add_node(s, demand=-bigNumber)
    flowNetwork.add_node(t, demand=bigNumber)

    for v in G.nodes():
        if v != s and v != t:
            flowNetwork.add_node(v, demand=0)

    flowNetwork.add_edge(s, t, weight=0)

    counter = count(1)  # Start an iterator given increasing integers starting from 1
    edgeMap = dict()

    for x, y in G.edges():
        z1 = str(next(counter))
        z2 = str(next(counter))
        edgeMap[(x, y)] = z1
        l = G[x][y]["l"]
        u = G[x][y]["u"]
        c = G[x][y]["c"]
        flowNetwork.add_node(z1, demand=l)
        flowNetwork.add_node(z2, demand=-l)
        flowNetwork.add_edge(x, z1, weight=c, capacity=u)
        flowNetwork.add_edge(z1, z2, weight=0, capacity=u)
        flowNetwork.add_edge(z2, y, weight=0, capacity=u)

    flowCost, flowDictNet = nx.network_simplex(flowNetwork)

    flowDict = dict()
    for x in G.nodes():
        flowDict[x] = dict()

    for x, y in G.edges():
        flowDict[x][y] = flowDictNet[x][edgeMap[(x, y)]]

    return flowCost, flowDict


def maxBottleckPath(G: nx.DiGraph, flow_attr) -> tuple:
    """
    Computes the maximum bottleneck path in a directed graph.

    Parameters
    ----------
    - G (nx.DiGraph): A directed graph where each edge has a flow attribute.
    - flow_attr (str): The flow attribute from where to get the flow values.

    Returns
    ----------
    - tuple: A tuple containing:
        - The value of the maximum bottleneck.
        - The path corresponding to the maximum bottleneck (list of nodes).
            If no s-t flow exists in the network, returns (None, None).
    """
    B = dict()
    maxInNeighbor = dict()
    maxBottleneckSink = None

    # Computing the B values with DP
    for v in nx.topological_sort(G):
        if G.in_degree(v) == 0:
            B[v] = float("inf")
        else:
            B[v] = float("-inf")
            for u in G.predecessors(v):
                uBottleneck = min(B[u], G.edges[u, v][flow_attr])
                if uBottleneck > B[v]:
                    B[v] = uBottleneck
                    maxInNeighbor[v] = u
            if G.out_degree(v) == 0:
                if maxBottleneckSink is None or B[v] > B[maxBottleneckSink]:
                    maxBottleneckSink = v

    # If no s-t flow exists in the network
    if B[maxBottleneckSink] == 0:
        return None, None

    # Recovering the path of maximum bottleneck
    reverse_path = [maxBottleneckSink]
    while G.in_degree(reverse_path[-1]) > 0:
        reverse_path.append(maxInNeighbor[reverse_path[-1]])

    return B[maxBottleneckSink], list(reversed(reverse_path))


def check_flow_conservation(G: nx.DiGraph, flow_attr) -> bool:
    """
    Check if the flow conservation property holds for the given graph.

    Parameters
    ----------
    - G (nx.DiGraph): The input directed acyclic graph, as networkx DiGraph.
    - flow_attr (str): The attribute name from where to get the flow values on the edges.

    Returns
    -------
    - bool: True if the flow conservation property holds, False otherwise.
    """

    for v in G.nodes():
        if G.out_degree(v) == 0 or G.in_degree(v) == 0:
            continue
        out_flow = sum(flow for _, _, flow in G.out_edges(v, data=flow_attr))
        in_flow = sum(flow for _, _, flow in G.in_edges(v, data=flow_attr))

        if out_flow != in_flow:
            return False

    return True

def max_occurrence(seq, paths_in_DAG, edge_lengths: dict = {}) -> int:
    """
    Check what is the maximum number of edges of seq that appear in some path in the list paths_in_DAG. 

    This assumes paths_in_DAG are paths in a directed acyclic graph. 

    Parameters
    ----------
    - seq (list): The sequence of edges to check.
    - paths (list): The list of paths to check against, as lists of nodes.

    Returns
    -------
    - int: the largest number of seq edges that appear in some path in paths_in_DAG
    """
    max_occurence = 0
    for path in paths_in_DAG:
        path_edges = set([(path[i], path[i + 1]) for i in range(len(path) - 1)])
        # Check how many seq edges are in path_edges
        occurence = 0
        for edge in seq:
            if edge in path_edges:
                occurence += edge_lengths.get(edge, 1)
        if occurence > max_occurence:
            max_occurence = occurence
            
    return max_occurence

def draw_graph(graph: nx.DiGraph):

    import matplotlib.pyplot as plt
    import pydot

    pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
    pydot_graph.set_graph_defaults(rankdir='LR')
    pydot_graph.set_graph_defaults(shape='rectangle')
    pydot_graph.write_dot("output_pydot.dot")
    pydot_graph.write_png("output_pydot.png")

    # pydot_graph.get_node("0").

    tmp_G = graph # pydot.Dot(pydot_graph)

    pydotg2 = pydot.Dot(pydot_graph)

    print(pydotg2.get_node(0)[0].get_attributes())

    pos = nx.nx_pydot.pydot_layout(tmp_G, prog="dot")

    print(pos)

    plt.figure()

    # nodes
    options = {"edgecolors": "tab:gray", "node_size": 800, "alpha": 0.9}
    # nx.draw_networkx_nodes(G, pos, nodelist=[0, 1, 2, 3], node_color="tab:red", **options)
    # nx.draw_networkx_nodes(G, pos, nodelist=[4, 5, 6, 7], node_color="tab:blue", **options)
    nx.draw_networkx_nodes(tmp_G, pos, nodelist=tmp_G.nodes(), node_color="tab:blue", **options)

    # edges
    nx.draw_networkx_edges(tmp_G, pos, width=1.0, alpha=0.5)
    # nx.draw_networkx_edges(
    #     G,
    #     pos,
    #     edgelist=[(0, 1), (1, 2), (2, 3), (3, 0)],
    #     width=15,
    #     alpha=0.5,
    #     edge_color="tab:red",
    # )
    # nx.draw_networkx_edges(
    #     G,
    #     pos,
    #     edgelist=[(0, 1), (1, 2), (2, 3), (3, 0)],
    #     width=5,
    #     alpha=0.5,
    #     edge_color="tab:blue",
    # )
    # nx.draw_networkx_edges(
    #     G,
    #     pos,
    #     edgelist=[(4, 5), (5, 6), (6, 7), (7, 4)],
    #     width=8,
    #     alpha=0.5,
    #     edge_color="tab:blue",
    # )


    # # some math labels
    # labels = {}
    # labels[0] = r"$a$"
    # labels[1] = r"$b$"
    # labels[2] = r"$c$"
    # labels[3] = r"$d$"
    # labels[4] = r"$\alpha$"
    # labels[5] = r"$\beta$"
    # labels[6] = r"$\gamma$"
    # labels[7] = r"$\delta$"
    # nx.draw_networkx_labels(G, pos, labels, font_size=22, font_color="whitesmoke")

    plt.tight_layout()
    plt.axis("off")
    plt.savefig("output_pydot_nx.pdf")
