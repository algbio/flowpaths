from itertools import count
import networkx as nx
import flowpaths.utils as utils
# NOTE: Do NOT import flowpaths.stdigraph at module import time to avoid a circular
# import chain: stdag -> graphutils -> stdigraph -> stdag. We instead lazily import
# stdigraph inside functions that need it (e.g. read_graph) after this module is fully loaded.

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
    """
    Parse a single graph block from a list of lines.

    Accepts one or more header lines at the beginning (each prefixed by '#'),
    followed by a line containing the number of vertices (n), then any number
    of edge lines of the form: "u v w" (whitespace-separated).

    Subpath constraint lines:
        Lines starting with "#S" define a (directed) subpath constraint as a
        sequence of nodes: "#S n1 n2 n3 ...". For each such line we build the
        list of consecutive edge tuples [(n1,n2), (n2,n3), ...] and append this
        edge-list (the subpath) to G.graph["constraints"]. Duplicate filtering
        is applied on the whole node sequence: if an identical sequence of
        nodes has already appeared in a previous "#S" line, the entire subpath
        line is ignored (its edges are not added again). Different subpaths may
    share edges; they are kept as separate entries. After all graph edges
    are parsed, every constraint edge is validated to ensure it exists in
    the graph; a missing edge raises ValueError.

    Example block:
        # graph number = 1 name = foo
        # any other header line
        #S a b c d          (adds subpath [(a,b),(b,c),(c,d)])
        #S b c e            (adds subpath [(b,c),(c,e)])
        #S a b c d          (ignored: exact node sequence already seen)
        5
        a b 1.0
        b c 2.5
        c d 3.0
        c e 4.0
    """

    # Collect leading header lines (prefixed by '#') and parse constraint lines prefixed by '#S'
    idx = 0
    header_lines = []
    constraint_subpaths = []       # list of subpaths, each a list of (u,v) edge tuples
    subpaths_seen = set()          # set of full node sequences (tuples) to filter duplicate subpaths
    while idx < len(graph_raw) and graph_raw[idx].lstrip().startswith("#"):
        stripped = graph_raw[idx].lstrip()
        # Subpath constraint line: starts with '#S'
        if stripped.startswith("#S"):
            # Remove leading '#S' and split remaining node sequence
            nodes_part = stripped[2:].strip()  # drop '#S'
            if nodes_part:
                nodes_seq = nodes_part.split()
                seq_key = tuple(nodes_seq)
                # Skip if this exact subpath sequence already processed
                if seq_key not in subpaths_seen:
                    subpaths_seen.add(seq_key)
                    edges_list = [(u, v) for u, v in zip(nodes_seq, nodes_seq[1:])]
                    # Only append if there is at least one edge (>=2 nodes)
                    if edges_list:
                        constraint_subpaths.append(edges_list)
        else:
            # Regular header line (remove leading '#') for metadata / id extraction
            header_lines.append(stripped.lstrip("#").strip())
        idx += 1

    # Determine graph id from the first (non-#S) header line if present
    graph_id = header_lines[0] if header_lines else str(id(graph_raw))

    # Skip blank lines before the vertex-count line
    while idx < len(graph_raw) and graph_raw[idx].strip() == "":
        idx += 1

    if idx >= len(graph_raw):
        error_msg = "Graph block missing vertex-count line."
        utils.logger.error(f"{__name__}: {error_msg}")
        raise ValueError(error_msg)
    # Parse number of vertices (kept for information; not used to count edges here)
    try:
        n = int(graph_raw[idx].strip())
    except ValueError:
        utils.logger.error(f"{__name__}: Invalid vertex-count line: {graph_raw[idx].rstrip()}.")
        raise

    idx += 1

    G = nx.DiGraph()
    G.graph["id"] = graph_id
    # Store (possibly empty) list of subpaths (each a list of edge tuples)
    G.graph["constraints"] = constraint_subpaths

    if n == 0:
        utils.logger.info(f"Graph {graph_id} has 0 vertices.")
        return G

    # Parse edges: skip blanks and comment/header lines defensively
    for line in graph_raw[idx:]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        elements = line.split()
        if len(elements) != 3:
            utils.logger.error(f"{__name__}: Invalid edge format: {line.rstrip()}")
            raise ValueError(f"Invalid edge format: {line.rstrip()}")
        u, v, w_str = elements
        try:
            w = float(w_str)
        except ValueError:
            utils.logger.error(f"{__name__}: Invalid weight value in edge: {line.rstrip()}")
            raise
        G.add_edge(u.strip(), v.strip(), flow=w)

    # Validate that every constraint edge exists in the graph
    for subpath in constraint_subpaths:
        for (u, v) in subpath:
            if not G.has_edge(u, v):
                utils.logger.error(f"{__name__}: Constraint edge ({u}, {v}) not found in graph {graph_id} edges.")
                raise ValueError(f"Constraint edge ({u}, {v}) not found in graph edges.")

    G.graph["n"] = G.number_of_nodes()
    G.graph["m"] = G.number_of_edges()
    # Lazy import here to avoid circular import at module load time
    from flowpaths import stdigraph as _stdigraph  # type: ignore
    G.graph["w"] = _stdigraph.stDiGraph(G).get_width()

    return G


def read_graphs(filename):
    """
    Read one or more graphs from a file.

    Supports graphs whose header consists of one or multiple consecutive lines
    prefixed by '#'. Each graph block is:
        - one or more header lines starting with '#'
        - one line with the number of vertices (n)
        - zero or more edge lines "u v w"

    Graphs are delimited by the start of the next header (a line starting with '#')
    or the end of file.
    """
    with open(filename, "r") as f:
        lines = f.readlines()

    graphs = []
    n_lines = len(lines)
    i = 0

    # Iterate through the file, capturing blocks that start with one or more '#' lines
    while i < n_lines:
        # Move to the start of the next graph header
        while i < n_lines and not lines[i].lstrip().startswith('#'):
            i += 1
        if i >= n_lines:
            break

        start = i

        # Consume all consecutive header lines for this graph
        while i < n_lines and lines[i].lstrip().startswith('#'):
            i += 1

        # Advance until the next header line (start of next graph) or EOF
        j = i
        while j < n_lines and not lines[j].lstrip().startswith('#'):
            j += 1

        graphs.append(read_graph(lines[start:j]))
        i = j

    return graphs


def read_ngraph(graph_raw) -> nx.DiGraph:
    """
    Parse a single node-weighted ngraph block from a list of lines.

    Expected block structure:
        - one or more leading header lines starting with '#'
          (optional #S constraints can appear here)
        - one line with the number of nodes n
        - a marker line starting with '#NODES'
        - exactly n node lines: "node_id node_weight"
        - a marker line starting with '#EDGES'
        - zero or more edge lines: "u v edge_weight"

    Constraint lines:
        - '#S n1 n2 n3 ...' lines define subpath constraints.
        - Duplicates are filtered by exact node sequence.
        - Constraints are stored in G.graph['constraints'] as edge lists.
    """

    idx = 0
    header_lines = []
    constraint_subpaths = []
    subpaths_seen = set()

    # Parse leading header lines and #S constraints.
    while idx < len(graph_raw) and graph_raw[idx].lstrip().startswith("#"):
        stripped = graph_raw[idx].lstrip()
        if stripped.startswith("#S"):
            nodes_part = stripped[2:].strip()
            if nodes_part:
                nodes_seq = nodes_part.split()
                seq_key = tuple(nodes_seq)
                if seq_key not in subpaths_seen:
                    subpaths_seen.add(seq_key)
                    edges_list = [(u, v) for u, v in zip(nodes_seq, nodes_seq[1:])]
                    if edges_list:
                        constraint_subpaths.append(edges_list)
        else:
            header_lines.append(stripped.lstrip("#").strip())
        idx += 1

    graph_id = header_lines[0] if header_lines else str(id(graph_raw))

    while idx < len(graph_raw) and graph_raw[idx].strip() == "":
        idx += 1

    if idx >= len(graph_raw):
        error_msg = "ngraph block missing node-count line."
        utils.logger.error(f"{__name__}: {error_msg}")
        raise ValueError(error_msg)

    try:
        n = int(graph_raw[idx].strip())
    except ValueError:
        utils.logger.error(f"{__name__}: Invalid ngraph node-count line: {graph_raw[idx].rstrip()}.")
        raise

    idx += 1
    while idx < len(graph_raw) and graph_raw[idx].strip() == "":
        idx += 1

    if idx >= len(graph_raw) or not graph_raw[idx].lstrip().startswith("#NODES"):
        error_msg = "ngraph block missing #NODES section marker."
        utils.logger.error(f"{__name__}: {error_msg}")
        raise ValueError(error_msg)
    idx += 1

    G = nx.DiGraph()
    G.graph["id"] = graph_id
    G.graph["constraints"] = constraint_subpaths

    # Read exactly n node lines.
    nodes_read = 0
    while idx < len(graph_raw) and nodes_read < n:
        line = graph_raw[idx].strip()
        idx += 1
        if line == "":
            continue
        if line.lstrip().startswith("#"):
            utils.logger.error(f"{__name__}: Unexpected comment in #NODES section: {line}")
            raise ValueError(f"Unexpected comment in #NODES section: {line}")
        elements = line.split()
        if len(elements) != 2:
            utils.logger.error(f"{__name__}: Invalid node format in ngraph: {line}")
            raise ValueError(f"Invalid node format in ngraph: {line}")
        node_id, weight_str = elements
        try:
            weight = float(weight_str)
        except ValueError:
            utils.logger.error(f"{__name__}: Invalid node weight in ngraph: {line}")
            raise
        G.add_node(node_id.strip(), flow=weight)
        nodes_read += 1

    if nodes_read != n:
        error_msg = f"ngraph node section ended early: expected {n}, read {nodes_read}."
        utils.logger.error(f"{__name__}: {error_msg}")
        raise ValueError(error_msg)

    while idx < len(graph_raw) and graph_raw[idx].strip() == "":
        idx += 1

    if idx >= len(graph_raw) or not graph_raw[idx].lstrip().startswith("#EDGES"):
        error_msg = "ngraph block missing #EDGES section marker."
        utils.logger.error(f"{__name__}: {error_msg}")
        raise ValueError(error_msg)
    idx += 1

    # Parse edges until the end of the block.
    for line in graph_raw[idx:]:
        stripped = line.strip()
        if not stripped:
            continue

        if line.lstrip().startswith("#"):
            comment = line.lstrip()
            # Allow additional #S lines after #EDGES for flexibility.
            if comment.startswith("#S"):
                nodes_part = comment[2:].strip()
                if nodes_part:
                    nodes_seq = nodes_part.split()
                    seq_key = tuple(nodes_seq)
                    if seq_key not in subpaths_seen:
                        subpaths_seen.add(seq_key)
                        edges_list = [(u, v) for u, v in zip(nodes_seq, nodes_seq[1:])]
                        if edges_list:
                            constraint_subpaths.append(edges_list)
            continue

        elements = stripped.split()
        if len(elements) != 3:
            utils.logger.error(f"{__name__}: Invalid edge format in ngraph: {line.rstrip()}")
            raise ValueError(f"Invalid edge format in ngraph: {line.rstrip()}")

        u, v, w_str = elements
        try:
            w = float(w_str)
        except ValueError:
            utils.logger.error(f"{__name__}: Invalid edge weight in ngraph: {line.rstrip()}")
            raise

        if u not in G.nodes or v not in G.nodes:
            utils.logger.error(
                f"{__name__}: Edge ({u}, {v}) references unknown node in graph {graph_id}."
            )
            raise ValueError(f"Edge ({u}, {v}) references unknown node in ngraph.")

        G.add_edge(u.strip(), v.strip(), flow=w)

    # For ngraph, constraints can encode node-pair evidence (MultiTrans R),
    # which is not necessarily an existing edge. Validate only node existence.
    for subpath in constraint_subpaths:
        for (u, v) in subpath:
            if u not in G.nodes or v not in G.nodes:
                utils.logger.error(
                    f"{__name__}: Constraint references unknown nodes ({u}, {v}) in ngraph {graph_id}."
                )
                raise ValueError(f"Constraint references unknown nodes ({u}, {v}).")

    G.graph["n"] = G.number_of_nodes()
    G.graph["m"] = G.number_of_edges()
    from flowpaths import stdigraph as _stdigraph  # type: ignore
    G.graph["w"] = _stdigraph.stDiGraph(G).get_width()

    return G


def read_ngraphs(filename):
    """
    Read one or more ngraph blocks from a file.

    Graph blocks are delimited by lines starting with '# graph' (case-insensitive).
    If no such delimiter exists, the whole file is parsed as one ngraph block.
    """

    with open(filename, "r") as f:
        lines = f.readlines()

    starts = []
    for i, line in enumerate(lines):
        stripped = line.lstrip().lower()
        if stripped.startswith("# graph") or stripped.startswith("#graph"):
            starts.append(i)

    if len(starts) == 0:
        return [read_ngraph(lines)]

    graphs = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        graphs.append(read_ngraph(lines[start:end]))

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
    
        The input directed acyclic graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html).

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

def draw(
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
            "show_graph_title": False,
            "show_path_weights": False,
            "show_path_weight_on_first_edge": True,
            "pathwidth": 3.0,
            "style": "default",
            "color_nodes": False,
            "sankey_arrowlen": 0,
            "sankey_color_toggle": False,
            "sankey_arrow_toggle": False,
        },
        ):
        """
        Draw the graph with the paths and their weights highlighted.

        Parameters
        ----------

        - `G`: nx.DiGraph 
        
            The input directed acyclic graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html). 

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

            - `show_graph_title`: bool

                Whether to show the graph title (from graph id) in the figure.
                Default is `False`.

            - `show_path_weights`: bool

                Whether to show the path weights in the graph on every edge. Default is `False`.

            - `show_path_weight_on_first_edge`: bool

                Whether to show the path weight on the first edge of the path. Default is `True`.

            - `pathwidth`: float
            
                The width of the path to be drawn. Default is `3.0`.

            - `style`: str

                The style of the drawing. Available options: `default`, `points`, `sankey`.
                
                - `default`: Standard graphviz rendering with nodes as rounded rectangles
                - `points`: Graphviz rendering with nodes as points
                - `sankey`: Interactive Sankey diagram using plotly (requires acyclic graph). 
                  Saves as HTML by default (interactive) or static image formats (png, pdf, svg) if kaleido is installed.
                  Automatically displays in Jupyter notebooks.

            - `color_nodes`: bool

                    Whether to use the existing node coloring behavior.
                    If `False` (default), all nodes use a neutral color.
                    If `True`, nodes are colored as before (including `additional_starts`
                    in green and `additional_ends` in red for graphviz styles).

            - `sankey_arrowlen`: float

                Length of arrowheads for Sankey links (Plotly `arrowlen`).
                Default is `0` (no arrowheads).

            - `sankey_color_toggle`: bool

                Whether to add an interactive toggle (buttons) to switch Sankey
                links between colored and monochrome gray.
                Default is `False`.

            - `sankey_arrow_toggle`: bool

                Whether to add an interactive toggle (buttons) to switch Sankey
                link arrowheads on/off.
                Default is `False`.

        """

        if len(paths) != len(weights) and len(weights) > 0:
            raise ValueError(f"{__name__}: Paths and weights must have the same length, if provided.")

        style = draw_options.get("style", "default")
        
        # Handle Sankey diagram separately
        if style == "sankey":
            # Check if graph is acyclic
            if not nx.is_directed_acyclic_graph(G):
                utils.logger.error(f"{__name__}: Sankey diagram requires an acyclic graph.")
                raise ValueError("Sankey diagram requires an acyclic graph.")

            try:
                sankey_arrowlen = float(draw_options.get("sankey_arrowlen", 0))
            except (TypeError, ValueError):
                utils.logger.error(f"{__name__}: draw_options['sankey_arrowlen'] must be numeric.")
                raise ValueError("draw_options['sankey_arrowlen'] must be numeric.")

            if sankey_arrowlen < 0:
                utils.logger.error(f"{__name__}: draw_options['sankey_arrowlen'] must be >= 0.")
                raise ValueError("draw_options['sankey_arrowlen'] must be >= 0.")

            sankey_color_toggle = bool(draw_options.get("sankey_color_toggle", False))
            sankey_arrow_toggle = bool(draw_options.get("sankey_arrow_toggle", False))
            color_nodes = bool(draw_options.get("color_nodes", False))
            show_graph_title = bool(draw_options.get("show_graph_title", False))
            default_arrowlen_for_toggle = sankey_arrowlen if sankey_arrowlen > 0 else 15.0
            
            try:
                import plotly.graph_objects as go
            except ImportError:
                utils.logger.error(f"{__name__}: plotly module not found. It should be installed with flowpaths. Try reinstalling: pip install --force-reinstall flowpaths")
                raise ImportError("plotly module not found. It should be installed with flowpaths. Try reinstalling: pip install --force-reinstall flowpaths")
            
            # Create node list in topological order, with sources and sinks at the end
            # This ordering can help preserve link ordering in the Sankey layout
            topo_order = list(nx.topological_sort(G))
            longest_path_len = nx.algorithms.dag.dag_longest_path_length(G)
            sankey_width = max(900, 500 + 50 * max(1, longest_path_len))
            
            # Identify sources (in-degree 0) and sinks (out-degree 0)
            sources = [node for node in topo_order if G.in_degree(node) == 0]
            sinks = [node for node in topo_order if G.out_degree(node) == 0]
            
            # Middle nodes (neither pure source nor pure sink)
            middle_nodes = [node for node in topo_order if node not in sources and node not in sinks]
            
            # Build node list: middle nodes in topo order, then sources, then sinks
            node_list = middle_nodes + sources + sinks
            node_dict = {node: idx for idx, node in enumerate(node_list)}
            
            # Define colors for paths (with transparency for blending)
            colors = [
                "rgba(255, 0, 0, 0.4)",      # red
                "rgba(0, 0, 255, 0.4)",      # blue
                "rgba(0, 128, 0, 0.4)",      # green
                "rgba(128, 0, 128, 0.4)",    # purple
                "rgba(165, 42, 42, 0.4)",    # brown
                "rgba(0, 255, 255, 0.4)",    # cyan
                "rgba(255, 255, 0, 0.4)",    # yellow
                "rgba(255, 192, 203, 0.4)",  # pink
                "rgba(128, 128, 128, 0.4)",  # grey
                "rgba(210, 105, 30, 0.4)",   # chocolate
                "rgba(0, 0, 139, 0.4)",      # darkblue
                "rgba(85, 107, 47, 0.4)",    # darkolivegreen
                "rgba(47, 79, 79, 0.4)",     # darkslategray
                "rgba(0, 191, 255, 0.4)",    # deepskyblue
                "rgba(95, 158, 160, 0.4)",   # cadetblue
                "rgba(139, 0, 139, 0.4)",    # darkmagenta
                "rgba(255, 193, 37, 0.4)",   # goldenrod 
            ]
            
            # Build links with path information to maintain consistent ordering at nodes
            # Structure: list of (source, target, weight, color, path_idx)
            links_with_metadata = []
            
            for path_idx, path in enumerate(paths):
                path_weight = weights[path_idx] if path_idx < len(weights) else 1
                path_color = colors[path_idx % len(colors)]
                
                # Add each edge in the path
                for i in range(len(path) - 1):
                    source = node_dict[path[i]]
                    target = node_dict[path[i + 1]]
                    links_with_metadata.append((source, target, path_weight, path_color, path_idx))
            
            # Sort links by path index to maintain consistent ordering throughout the diagram
            # This ensures edges from the same path appear in the same relative order at all nodes
            links_with_metadata.sort(key=lambda x: x[4])
            
            # Extract sorted components
            link_sources = [link[0] for link in links_with_metadata]
            link_targets = [link[1] for link in links_with_metadata]
            link_values = [link[2] for link in links_with_metadata]
            link_colors = [link[3] for link in links_with_metadata]
            
            # Create Sankey diagram
            link_dict = dict(
                source=link_sources,
                target=link_targets,
                value=link_values,
                color=link_colors,
            )
            if sankey_arrowlen > 0:
                link_dict["arrowlen"] = sankey_arrowlen

            node_color = "rgba(99, 110, 120, 0.85)" if not color_nodes else "rgba(31, 119, 180, 0.8)"

            base_fig = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=[str(node) for node in node_list],
                    color=[node_color] * len(node_list),
                ),
                link=link_dict
            )])
            
            # Use graph ID as title if available
            graph_id = G.graph.get("id", fpid(G))
            title_text = f"{graph_id}" if show_graph_title and graph_id and graph_id != str(id(G)) else ""
            
            base_fig.update_layout(
                title_text=title_text,
                font_size=10,
                width=sankey_width,
                height=600,
            )

            fig = go.Figure(base_fig)

            updatemenus = []

            if sankey_color_toggle and len(link_colors) > 0:
                monochrome_colors = ["rgba(150, 150, 150, 0.6)"] * len(link_colors)
                updatemenus.append(
                    dict(
                        type="buttons",
                        direction="left",
                        x=0.0,
                        y=1.12,
                        showactive=True,
                        buttons=[
                            dict(
                                label="Colored links",
                                method="restyle",
                                args=[{"link.color": [link_colors]}],
                            ),
                            dict(
                                label="Monochrome links",
                                method="restyle",
                                args=[{"link.color": [monochrome_colors]}],
                            ),
                        ],
                    )
                )

            if sankey_arrow_toggle:
                updatemenus.append(
                    dict(
                        type="buttons",
                        direction="left",
                        x=0.0,
                        y=1.05,
                        showactive=True,
                        buttons=[
                            dict(
                                label="Arrowheads on",
                                method="restyle",
                                args=[{"link.arrowlen": [default_arrowlen_for_toggle]}],
                            ),
                            dict(
                                label="Arrowheads off",
                                method="restyle",
                                args=[{"link.arrowlen": [0]}],
                            ),
                        ],
                    )
                )

            if len(updatemenus) > 0:
                fig.update_layout(updatemenus=updatemenus)
            
            # Determine base filename and extension
            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
            base_filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            # Always save HTML (interactive version)
            html_filename = base_filename + '.html'
            fig.write_html(html_filename)
            utils.logger.info(f"{__name__}: Sankey diagram (HTML) saved as {html_filename}")
            
            # Also save static image (PDF by default, or specified format)
            static_format = file_ext if file_ext in ['png', 'pdf', 'svg', 'jpg', 'jpeg'] else 'pdf'
            static_filename = base_filename + '.' + static_format
            
            try:
                static_fig = go.Figure(base_fig)
                if static_format == 'pdf':
                    static_fig.update_layout(
                        width=sankey_width,
                        height=900,
                    )

                static_fig.write_image(static_filename, format=static_format)
                utils.logger.info(f"{__name__}: Sankey diagram (static) saved as {static_filename}")
            except Exception as e:
                utils.logger.warning(f"{__name__}: Could not save static image. Error: {e}")
                utils.logger.warning(f"{__name__}: Static image export may require additional system dependencies.")
            
            # Check if we're in a Jupyter notebook and show the figure
            if "get_ipython" in globals():
                try:
                    if globals()["get_ipython"]() is not None:
                        fig.show()
                except Exception:
                    pass  # Not in a notebook, just save
            
            return

        try:
            import graphviz as gv

            color_nodes = bool(draw_options.get("color_nodes", False))
        
            dot = gv.Digraph(format="pdf")
            dot.graph_attr["rankdir"] = "LR"  # Display the graph in landscape mode
            
            # style already extracted above
            if style == "default":
                dot.node_attr["shape"] = "rectangle"  # Rectangle nodes
                dot.node_attr["style"] = "rounded"  # Rounded rectangle nodes
            elif style == "points":
                dot.node_attr["shape"] = "point"  # Point nodes
                dot.node_attr["style"] = "filled"  # Filled point nodes
                # dot.node_attr['label'] = '' 
                dot.node_attr['width'] = '0.1' 

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
                    neutral_node_color = "gray40"
                    color = neutral_node_color
                    penwidth = "1.0"
                    if color_nodes:
                        color = "black"
                        if node in additional_starts:
                            color = "green"
                            penwidth = "2.0"
                        elif node in additional_ends:
                            color = "red"
                            penwidth = "2.0"

                    if draw_options.get("show_node_weights", False) and flow_attr is not None and flow_attr in G.nodes[node]:
                        label = f"{G.nodes[node][flow_attr]}\\n{node}" if style != "points" else ""
                        dot.node(
                            name=str(node),
                            label=label,
                            shape="record",
                            color=color, 
                            penwidth=penwidth)
                    else:
                        label = str(node) if style != "points" else ""
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
                            label=str(weights[index]) if len(weights) > 0 else "",
                            fontname="Arial",
                        )
                    else:
                        dot.edge(
                            str(path[i]),
                            str(path[i + 1]),
                            color=pathColor,
                            penwidth=str(draw_options.get("pathwidth", 3.0)),
                            )
                if len(path) == 1:
                    dot.node(str(path[0]), color=pathColor, penwidth=str(draw_options.get("pathwidth", 3.0)))        
                
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

def draw_WIP(graph: nx.DiGraph, paths: list, weights: list, id:str):

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
