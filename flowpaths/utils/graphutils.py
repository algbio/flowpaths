from itertools import count
import networkx as nx
import flowpaths.utils as utils

bigNumber = 1 << 32

def fpid(G) -> str:
    """
    Returns a unique identifier for the given graph.
    """
    if isinstance(G, nx.DiGraph):
        if "id" in G.graph:
            return G.graph["id"]

    return str(id(G))

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
        elements = edge.split(" ")
        if len(elements) != 3:
            utils.logger.error(f"{__name__}: Invalid edge format: %s", edge)
            raise ValueError("Invalid edge format: %s", edge)
        # print(elements)
        u = elements[0].strip()
        v = elements[1].strip()
        w = float(elements[2].strip(" \n"))
        # print(u, v, w)
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


def min_cost_flow(G: nx.DiGraph, s, t, demands_attr = 'l', capacities_attr = 'u', costs_attr = 'c') -> tuple:

    flowNetwork = nx.DiGraph()

    flowNetwork.add_node(s, demand=-bigNumber)
    flowNetwork.add_node(t, demand=bigNumber)

    for v in G.nodes():
        if v != s and v != t:
            flowNetwork.add_node(v, demand=0)

    flowNetwork.add_edge(s, t, weight=0)

    counter = count(1)  # Start an iterator given increasing integers starting from 1
    edgeMap = dict()
    uid = "z" + str(id(G))

    for x, y in G.edges():
        z1 = uid + str(next(counter))
        z2 = uid + str(next(counter))
        edgeMap[(x, y)] = z1
        l = G[x][y][demands_attr]
        u = G[x][y][capacities_attr]
        c = G[x][y][costs_attr]
        flowNetwork.add_node(z1, demand=l)
        flowNetwork.add_node(z2, demand=-l)
        flowNetwork.add_edge(x, z1, weight=c, capacity=u)
        flowNetwork.add_edge(z1, z2, weight=0, capacity=u)
        flowNetwork.add_edge(z2, y, weight=0, capacity=u)

    
    try:
        flowCost, flowDictNet = nx.network_simplex(flowNetwork)

        flowDict = {node: dict() for node in G.nodes()}

        for x, y in G.edges():
            flowDict[x][y] = flowDictNet[x][edgeMap[(x, y)]]

        return flowCost, flowDict
    
    except Exception as e:
        # If there was no feasible flow, return None    
        return None, None


def max_bottleneck_path(G: nx.DiGraph, flow_attr) -> tuple:
    """
    Computes the maximum bottleneck path in a directed graph.

    Parameters
    ----------
    - `G`: nx.DiGraph
    
        A directed graph where each edge has a flow attribute.

    - `flow_attr`: str
    
        The flow attribute from where to get the flow values.

    Returns
    --------

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
    - `G`: nx.DiGraph
    
        The input directed acyclic graph, as networkx DiGraph.

    - `flow_attr`: str
    
        The attribute name from where to get the flow values on the edges.

    Returns
    -------
    
    - bool: 
    
        True if the flow conservation property holds, False otherwise.
    """

    for v in G.nodes():
        if G.out_degree(v) == 0 or G.in_degree(v) == 0:
            continue

        out_flow = 0
        for x, y, data in G.out_edges(v, data=True):
            if data.get(flow_attr) is None:
                return False
            out_flow += data[flow_attr]

        in_flow = 0
        for x, y, data in G.in_edges(v, data=True):
            if data.get(flow_attr) is None:
                return False
            in_flow += data[flow_attr]

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

def draw_solution(
        G: nx.DiGraph, 
        filename: str,
        flow_attr: str = None,
        paths: list = [], 
        weights: list = [], 
        additional_starts: list = [],
        additional_ends: list = [],
        subpath_constraints: list = [],
        draw_options: dict = {
            "show_graph_edges": True,
            "show_edge_weights": False,
            "show_node_weights": False,
            "show_path_weights": False,
            "show_path_weight_on_first_edge": True,
            "pathwidth": 3.0
        },
        ):
        """
        Draw the graph with the paths and their weights highlighted.

        Parameters
        ----------

        - `G`: nx.DiGraph 
        
            The input directed acyclic graph, as networkx DiGraph. 

        - `filename`: str
        
            The name of the file to save the drawing. The file type is inferred from the extension. Supported extensions are '.bmp', '.canon', '.cgimage', '.cmap', '.cmapx', '.cmapx_np', '.dot', '.dot_json', '.eps', '.exr', '.fig', '.gd', '.gd2', '.gif', '.gtk', '.gv', '.ico', '.imap', '.imap_np', '.ismap', '.jp2', '.jpe', '.jpeg', '.jpg', '.json', '.json0', '.pct', '.pdf', '.pic', '.pict', '.plain', '.plain-ext', '.png', '.pov', '.ps', '.ps2', '.psd', '.sgi', '.svg', '.svgz', '.tga', '.tif', '.tiff', '.tk', '.vml', '.vmlz', '.vrml', '.wbmp', '.webp', '.x11', '.xdot', '.xdot1.2', '.xdot1.4', '.xdot_json', '.xlib'

        - `flow_attr`: str
        
            The attribute name from where to get the flow values on the edges. Default is an empty string, in which case no edge weights are shown.

        - `paths`: list
        
            The list of paths to highlight, as lists of nodes. Default is an empty list, in which case no path is drawn. Default is an empty list.

        - `weights`: list
        
            The list of weights corresponding to the paths, of various colors. Default is an empty list, in which case no path is drawn.

        - `additional_starts`: list

                A list of additional nodes to highlight in green as starting nodes. Default is an empty list.

        - `additional_ends`: list

                A list of additional nodes to highlight in red as ending nodes. Default is an empty list.
        
        - `subpath_constraints`: list

            A list of subpaths to highlight in the graph as dashed edges, of various colors. Each subpath is a list of edges. Default is an empty list. There is no association between the subpath colors and the path colors.
        
        - `draw_options`: dict

            A dictionary with the following keys:

            - `show_graph_edges`: bool

                Whether to show the edges of the graph. Default is `True`.
            
            - `show_edge_weights`: bool

                Whether to show the edge weights in the graph from the `flow_attr`. Default is `False`.

            - `show_node_weights`: bool

                Whether to show the node weights in the graph from the `flow_attr`. Default is `False`.

            - `show_path_weights`: bool

                Whether to show the path weights in the graph on every edge. Default is `False`.

            - `show_path_weight_on_first_edge`: bool

                Whether to show the path weight on the first edge of the path. Default is `True`.

            - `pathwidth`: float
            
                The width of the path to be drawn. Default is `3.0`.

        """

        if len(paths) != len(weights):
            raise ValueError(f"{__name__}: Paths and weights must have the same length.")
            raise ValueError("Paths and weights must have the same length, if provided.")

        try:
            import graphviz as gv
        
            dot = gv.Digraph(format="pdf")
            dot.graph_attr["rankdir"] = "LR"  # Display the graph in landscape mode
            dot.node_attr["shape"] = "rectangle"  # Rectangle nodes
            dot.node_attr["style"] = "rounded"  # Rounded rectangle nodes

            colors = [
                "red",
                "blue",
                "green",
                "purple",
                "brown",
                "cyan",
                "yellow",
                "pink",
                "grey",
                "chocolate",
                "darkblue",
                "darkolivegreen",
                "darkslategray",
                "deepskyblue2",
                "cadetblue3",
                "darkmagenta",
                "goldenrod1"
            ]

            dot.attr('node', fontname='Arial')

            if draw_options.get("show_graph_edges", True):
                # drawing nodes
                for node in G.nodes():
                    color = "black"
                    penwidth = "1.0"
                    if node in additional_starts:
                        color = "green"
                        penwidth = "2.0"
                    elif node in additional_ends:
                        color = "red"
                        penwidth = "2.0"
                    
                    if draw_options.get("show_node_weights", False) and flow_attr is not None and flow_attr in G.nodes[node]:
                        dot.node(
                            name=str(node),
                            #label=f"{{{node} | {G.nodes[node][flow_attr]}}}",
                            label=f"{G.nodes[node][flow_attr]}\\n{node}",
                            #xlabel=str(G.nodes[node][flow_attr]),
                            shape="record",
                            color=color, 
                            penwidth=penwidth)
                    else:
                        dot.node(
                            name=str(node), 
                            label=str(node), 
                            color=color, 
                            penwidth=penwidth)

                # drawing edges
                for u, v, data in G.edges(data=True):
                    if draw_options.get("show_edge_weights", False):
                        dot.edge(
                            tail_name=str(u), 
                            head_name=str(v), 
                            label=str(data.get(flow_attr,"")),
                            fontname="Arial",)
                    else:
                        dot.edge(
                            tail_name=str(u), 
                            head_name=str(v))

            for index, path in enumerate(paths):
                pathColor = colors[index % len(colors)]
                for i in range(len(path) - 1):
                    if i == 0 and draw_options.get("show_path_weight_on_first_edge", True) or \
                        draw_options.get("show_path_weights", True):
                        dot.edge(
                            str(path[i]),
                            str(path[i + 1]),
                            fontcolor=pathColor,
                            color=pathColor,
                            penwidth=str(draw_options.get("pathwidth", 3.0)),
                            label=str(weights[index]),
                            fontname="Arial",
                        )
                    else:
                        dot.edge(
                            str(path[i]),
                            str(path[i + 1]),
                            color=pathColor,
                            penwidth=str(draw_options.get("pathwidth", 3.0)),
                            )
                
            for index, path in enumerate(subpath_constraints):
                pathColor = colors[index % len(colors)]
                for i in range(len(path)):
                    if len(path[i]) != 2:
                        utils.logger.error(f"{__name__}: Subpaths must be lists of edges.")
                        raise ValueError("Subpaths must be lists of edges.")
                    dot.edge(
                        str(path[i][0]),
                        str(path[i][1]),
                        color=pathColor,
                        style="dashed",
                        penwidth="2.0"
                        )
                    
                if len(path) == 1:
                    dot.node(str(path[0]), color=pathColor, penwidth=str(draw_options.get("pathwidth", 3.0)))

            dot.render(outfile=filename, view=False, cleanup=True)
        
        except ImportError:
            utils.logger.error(f"{__name__}: graphviz module not found. Please install it via pip (pip install graphviz).")
            raise ImportError("graphviz module not found. Please install it via pip (pip install graphviz).")

def get_subgraph_between_topological_nodes(graph: nx.DiGraph, topo_order: list, left: int, right: int) -> nx.DiGraph:
    """
    Create a subgraph with the nodes between left and right in the topological order, 
    including the edges between them, but also the edges from these nodes that are incident to nodes outside this range.
    """

    if left < 0 or right >= len(topo_order):
        utils.logger.error(f"{__name__}: Invalid range for topological order: {left}, {right}.")
        raise ValueError("Invalid range for topological order")
    if left > right:
        utils.logger.error(f"{__name__}: Invalid range for topological order: {left}, {right}.")
        raise ValueError("Invalid range for topological order")

    # Create a subgraph with the nodes between left and right in the topological order
    subgraph = nx.DiGraph()
    if "id" in graph.graph:
        subgraph.graph["id"] = graph.graph["id"]
    for i in range(left, right):
        subgraph.add_node(topo_order[i], **graph.nodes[topo_order[i]])

    fixed_nodes = set(subgraph.nodes())

    # Add the edges between the nodes in the subgraph
    for u, v in graph.edges():
        if u in fixed_nodes or v in fixed_nodes:
            subgraph.add_edge(u, v, **graph[u][v])
            if u not in fixed_nodes:
                subgraph.add_node(u, **graph.nodes[u])
            if v not in fixed_nodes:
                subgraph.add_node(v, **graph.nodes[v])

    return subgraph

def draw_solution_WIP(graph: nx.DiGraph, paths: list, weights: list, id:str):

    import matplotlib.pyplot as plt
    import pydot

    pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
    pydot_graph.set_graph_defaults(rankdir='LR')
    pydot_graph.set_graph_defaults(shape='rectangle')
    
    print("Hello")
    pydot_graph.get_node("a")[0].get_pos()
    pydot_graph.write_dot(f"{id}.dot")
    
    # Read the dot file and extract node positions
    pos = {}
    with open(f"{id}.dot", "r") as file:
        lines = file.readlines()
        for i, line in enumerate(lines):
            if "pos=" in line and "->" not in lines[i - 1]:
                node_id = lines[i - 1].split("[")[0].strip()
                print("node_id", node_id)
                pos_str = line.split("pos=")[1].split('"')[1]
                x, y = map(float, pos_str.split(","))
                pos[node_id] = (x, y)
    
    print(pos)
    
    # pydot_graph.write_png(f"{id}.png")

    # tmp_G = graph

    # g = pydot.Dot(graph_type="digraph")
    
    # print(pydot_graph.get_node("a")[0])

    # pos = nx.nx_pydot.pydot_layout(graph, prog="dot")

    print(pos)

    # # Draw nodes
    # for node, (x, y) in pos.items():
    #     plt.scatter(x, y, s=800, edgecolors="tab:gray", alpha=0.9, color="tab:blue", marker='.')
    #     plt.text(x, y + 4, str(node), fontsize=12, ha='center', va='center', color='black')

    options = {"edgecolors": "tab:gray", "node_size": 800, "alpha": 0.9}
    basic_line_width = 2.0
    nx.draw_networkx_nodes(graph, pos, nodelist=graph.nodes(), node_color="tab:blue", **options)
    nx.draw_networkx_edges(graph, pos, width=basic_line_width, alpha=0.5, arrowsize=2)
    

    # # Draw edges
    # for (u, v, data) in graph.edges(data=True):
    #     x1, y1 = pos[str(u)]
    #     x2, y2 = pos[str(v)]
    #     plt.plot([x1, x2], [y1, y2], color="tab:gray", alpha=0, linestyle='-', linewidth=basic_line_width)
    #     # Optionally, add arrowheads
    #     plt.arrow(x1, y1, x2 - x1, y2 - y1, head_width=1, head_length=1, fc='tab:gray', ec='tab:gray')

    # Draw paths
    # Sort paths by weight in decreasing order
    sorted_paths = sorted(zip(paths, weights), key=lambda x: x[1], reverse=True)
    total_weight = sum(weights)
    colors = ["tab:red", "tab:green", "tab:blue", "tab:orange", "tab:purple", "tab:brown"]
    separator = 2  # Smaller separator between paths
    previous_shift = basic_line_width  # Initial shift up
    linewidth = [0 for i in range(len(sorted_paths))]

    for i, (path, weight) in enumerate(sorted_paths):
        path_edges = list(zip(path[:-1], path[1:]))
        x_coords = []
        y_coords = []
        linewidth[i] = max(2,(weight / total_weight) * 30)  # Set linewidth proportional to the path weight as a percentage of the total weight
        print("linewidth", linewidth[i])
        for (u, v) in path_edges:
            x1, y1 = pos[str(u)]
            x2, y2 = pos[str(v)]
            x_coords.extend([x1, x2])
            y_coords.extend([y1, y2])
        plt.plot(x_coords, y_coords, color=colors[i % len(colors)], alpha=0.35, linestyle='-', linewidth=linewidth[i])
        print("previous_shift", previous_shift)
        previous_shift += linewidth[i]/8 + separator  # Shift up for the next path

    # nodes
    options = {"edgecolors": "tab:gray", "node_size": 800, "alpha": 0.9}
    # nx.draw_networkx_nodes(G, pos, nodelist=[0, 1, 2, 3], node_color="tab:red", **options)
    # nx.draw_networkx_nodes(G, pos, nodelist=[4, 5, 6, 7], node_color="tab:blue", **options)
    # nx.draw_networkx_nodes(tmp_G, pos, nodelist=tmp_G.nodes(), node_color="tab:blue", **options)



    # edges
    # nx.draw_networkx_edges(tmp_G, pos, width=1.0, alpha=0.5, connectionstyle="arc3,rad=0.1")
    # nx.draw_networkx_edges(
    #     tmp_G,
    #     pos,
    #     edgelist=[(0, 1), (1, 2), (2, 3), (3, 0)],
    #     width=15,
    #     alpha=0.5,
    #     edge_color="tab:red",
    # )
    # nx.draw_networkx_edges(
    #     tmp_G,
    #     pos,
    #     edgelist=[(0, 1), (1, 2), (2, 3), (3, 0)],
    #     width=5,
    #     alpha=0.5,
    #     edge_color="tab:blue",
    # )
    # nx.draw_networkx_edges(
    #     tmp_G,
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
    # nx.draw_networkx_labels(tmp_G, pos, labels, font_size=22, font_color="whitesmoke")

    plt.tight_layout()
    plt.axis("off")
    plt.savefig(f"{id}.pdf")
