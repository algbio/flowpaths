import flowpaths.stdag as stdag
from queue import Queue
from copy import deepcopy


def find_all_bridges(adj_dict, s, t) -> list:

    # find arbitrary s-t path
    s_aux = s
    p = [s_aux]  # path of nodes

    while s_aux != t:
        x = adj_dict[s_aux].pop()  # remove edge in O(1)
        p.append(x)  # keep track of the path
        s_aux = x
    # add reversed path to G
    for i in range(len(p) - 1):
        adj_dict[p[i + 1]].append(p[i])

    n = len(adj_dict)  # len(adj_list)
    i = 1
    bridges = []
    component = dict()  # [0] * n
    for v in adj_dict.keys():
        component[v] = 0
    q = Queue(maxsize=n + 1)
    component[s] = 1
    first_node = 0
    q.put(s)

    while component[t] == 0:  # do while :(

        if i != 1:
            # find first node u of P with component[u]=0. all in all we pay |P|=O(n) time for this
            while component[p[first_node]] != 0:
                first_node += 1

            y = p[first_node - 1]
            z = p[first_node]

            bridges.append((y, z))
            q.put(z)
            component[z] = i

        while not q.empty():
            u = q.get()
            for v in adj_dict[u]:
                if component[v] == 0:
                    q.put(v)
                    component[v] = i
        i = i + 1

    #recover original adjacency relation
    for i in range(len(p)-1):
        u,v = p[i],p[i+1]
        adj_dict[v].pop()      #remove reversed edges
        adj_dict[u].append(v)  #reinsert removed edges

    return bridges


def is_core(G : stdag.stDAG, u: int, v: int) -> bool:
    return (G.out_degree(v) < 1 or G.in_degree(v) != 1) and (G.in_degree(u) < 1 or G.out_degree(u) != 1)


def find_unitig_of_arc(G : stdag.stDAG, e : tuple):
    u,v = e
    #assert(G.is_edge(e))
    unitig = [(u,v)]
    while G.has_unique_out_neighbor(v) and G.has_unique_in_neighbor(v):
        x = G.out_neighbors(v)[0]
        unitig.append((v,x))
        v = x
    while G.has_unique_in_neighbor(u) and G.has_unique_out_neighbor(u):
        x = G.in_neighbors(u)[0]
        unitig = [(x,u)] + unitig
        u = x
    return u,v,unitig


def safe_sequences_of_base_edges(
    G: stdag.stDAG, no_duplicates=False, threads: int = 4
) -> list:

    return safe_sequences(G, G.base_graph.edges(), no_duplicates, threads=threads)


def safe_sequences(
    G: stdag.stDAG, 
    edges_or_subpath_constraints_to_cover: list, 
    no_duplicates: bool = False, 
    threads: int = 4
) -> list:

    if edges_or_subpath_constraints_to_cover is None:
        return []

    sequences = set() if no_duplicates else []

    adj_dict = {u: list(G.successors(u)) for u in G.nodes()}
    adj_dict_rev = {u: list(G.predecessors(u)) for u in G.nodes()}

    adj_dict_pool = [deepcopy(adj_dict) for _ in range(threads)]
    adj_dict_rev_pool = [deepcopy(adj_dict_rev) for _ in range(threads)]

    import threading
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        # Create a lock per worker to serialize access to per-worker data structures
        worker_locks = [threading.Lock() for _ in range(threads)]
    
        def process_edge_locked(edge, worker_id: int):
            # This lock ensures that tasks for the same worker_id do not run concurrently
            with worker_locks[worker_id]:
                if isinstance(edge, tuple):
                    u, v, sequence_edge = edge[0], edge[-1], [edge]
                elif isinstance(edge, list):
                    if len(edge) == 0:
                        raise ValueError("Empty edge list provided")
                    u, v, sequence_edge = edge[0][0], edge[-1][-1], edge
                else:
                    raise ValueError("Invalid edge format (must be `tuple` or `list`)")
                left_extension = find_all_bridges(adj_dict_rev_pool[worker_id], u, G.source)
                right_extension = find_all_bridges(adj_dict_pool[worker_id], v, G.sink)
    
                # reverse left_extension edges
                for i in range(len(left_extension)):
                    x, y = left_extension[i]
                    left_extension[i] = (y, x)
    
                seq = (
                    left_extension[::-1]
                    + sequence_edge
                    + right_extension
                )
                return tuple(seq) if no_duplicates else seq
    
        # Distribute each edge along with its worker id (using modulo)
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            work_items = [(i % threads, edge) for i, edge in enumerate(edges_or_subpath_constraints_to_cover)]
            results = list(executor.map(lambda args: process_edge_locked(args[1], args[0]), work_items))
    
        if no_duplicates:
            sequences.update(results)
        else:
            sequences.extend(results)
    
    return list(sequences) if no_duplicates else sequences


def safe_paths_of_base_edges(
    G: stdag.stDAG, no_duplicates=False, threads: int = 4
) -> list:

    return safe_paths(G, G.base_graph.edges(), no_duplicates, threads=threads)


def safe_maximal_paths(G : stdag.stDAG, arcs_to_cover = []) -> list :
    
    paths          = []
    processed_arcs = set()
    cores          = []

    for e in arcs_to_cover:
        if e in processed_arcs: #is the arc e part of a unitig that has been tested for being a core?
            continue

        L,R,unitig = find_unitig_of_arc(G,e) #every edge-unitig U has a leftmost and rightmost nonunivocal vertex (or s/t), which together identify U

        for arc in unitig:
            processed_arcs.add(arc)

        if is_core(G,L,R):
            cores.append((L,R,unitig))
        
    for (L,R,unitig) in cores: #can paralelize this loop if we wish to
        path = []

        while G.has_unique_in_neighbor(L):
            x = G.in_neighbors(L)[0]
            path.append( (x,L) )
            L = x

        path  = path[::-1]
        path += unitig
        
        while G.has_unique_out_neighbor(R):
            x = G.out_neighbors(R)[0]
            path.append( (R,x) )
            R = x
            
        paths.append(path)

    return paths


def safe_paths(
    G: stdag.stDAG, edges_to_cover: list, no_duplicates=False, threads: int = 4
) -> list:

    paths = set() if no_duplicates else []

    import concurrent.futures

    def process_edge(e):
        path = []
        u, v = e

        while G.in_degree(u) == 1:
            x = next(G.predecessors(u))
            path.append((x, u))
            u = x

        path = path[::-1]
        path.append(e)

        while G.out_degree(v) == 1:
            x = next(G.successors(v))
            path.append((v, x))
            v = x

        return tuple(path) if no_duplicates else path

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        results = list(executor.map(process_edge, edges_to_cover))

    if no_duplicates:
        paths.update(results)
    else:
        paths.extend(results)

    if no_duplicates:
        return list(paths)
    else:
        return paths


def get_endpoints_of_longest_safe_path_in(safe_sequence: list) -> list:
    """
    Given a sequence of safe edges, this function finds the endpoints of the longest continuous safe path inside it.

    Parameters
    ----------
    - safe_sequence (list): A list of tuples where each tuple represents an edge in the form (start_node, end_node).

    Returns
    ----------
    - list: A list containing two elements, the start and end nodes of the longest continuous safe path.
    """

    left_node = max_left_node = safe_sequence[0][0]
    right_node = max_right_node = safe_sequence[0][1]
    length_safe_path = max_length_safe_path = 1

    # iterating through the edges of the safe sequence
    for j in range(len(safe_sequence) - 1):
        # if there is no break in the sequence, we advance the right node
        if safe_sequence[j][1] == safe_sequence[j + 1][0]:
            right_node = safe_sequence[j + 1][1]
            length_safe_path += 1
        else:  # otherwise, we check if the current path is the longest one, and reset the left and right nodes
            if length_safe_path > max_length_safe_path:
                max_length_safe_path = length_safe_path
                max_left_node = left_node
                max_right_node = right_node
            left_node = safe_sequence[j + 1][0]
            right_node = safe_sequence[j + 1][1]
            length_safe_path = 1

    return max_left_node, max_right_node
