import stDiGraph as graph
from queue import Queue

def find_all_bridges(adj_dict, s, t) -> list:

    #find arbitrary s-t path
    s_aux = s
    p = [s_aux] # path of nodes

    while s_aux != t:
        x = adj_dict[s_aux].pop() #remove edge in O(1)
        p.append(x)               #keep track of the path
        s_aux = x
    #add reversed path to G
    for i in range(len(p)-1):
        adj_dict[p[i+1]].append(p[i])

    n            = len(adj_dict)  # len(adj_list)
    i            = 1
    bridges      = []
    component    = dict()  # [0] * n
    for v in adj_dict.keys(): 
        component[v] = 0
    q            = Queue(maxsize = n+1)
    component[s] = 1
    first_node   = 0
    q.put(s)

    while component[t]==0: #do while :(

        if i!=1:
            #find first node u of P with component[u]=0. all in all we pay |P| time for this
            while component[p[first_node]] != 0:
                first_node += 1

            y = p[first_node-1]
            z = p[first_node  ]

            bridges.append((y,z))
            q.put(z)
            component[z] = i

        while not q.empty():
            u = q.get()
            for v in adj_dict[u]:
                if component[v]==0:
                    q.put(v)
                    component[v]=i
        i = i+1

    #recover original adjacency relation
    for i in range(len(p)-1):
        u,v = p[i],p[i+1]
        adj_dict[v].pop()      #remove reversed edges
        adj_dict[u].append(v)  #reinsert removed edges

    return bridges

def safe_sequences_of_base_edges(G : graph.stDiGraph, no_duplicates = False) -> list :
    
    return safe_sequences(G, G.base_graph.edges(), no_duplicates)

def safe_sequences(G : graph.stDiGraph, edges_to_cover: list, no_duplicates = False) -> list :
    
    sequences = set() if no_duplicates else []

    adj_dict = {u: [] for u in G.nodes()}
    for u in G.nodes():
        for v in G.successors(u):
            adj_dict[u].append(v)

    adj_dict_rev = {u: [] for u in G.nodes()}
    for u in G.nodes():
        for v in G.predecessors(u):
            adj_dict_rev[u].append(v)

    for (u,v) in edges_to_cover:
        left_extension  = find_all_bridges(adj_dict_rev , u, G.source)
        right_extension = find_all_bridges(adj_dict     , v, G.sink  )

        for i in range(len(left_extension)): #reverse edges of left extension, recall G^R
            x,y = left_extension[i]
            left_extension[i] = (y,x)

        seq = left_extension[::-1] + [ (u,v,) ] + right_extension

        if no_duplicates:
            sequences.add(tuple(seq))
        else:
            sequences.append(seq)

    if no_duplicates:
        return list(sequences)
    else:
        return sequences

def safe_paths_of_base_edges(G : graph.stDiGraph, no_duplicates = False) -> list :

    return safe_paths(G, G.base_graph.edges(), no_duplicates)

def safe_paths(G : graph.stDiGraph, edges_to_cover: list, no_duplicates = False) -> list :
    
    paths = set() if no_duplicates else []

    for e in edges_to_cover:
        path = []
        u,v = e
        
        while G.in_degree(u) == 1:
            x = next(G.predecessors(u))
            path.append( (x,u) )
            u = x

        path = path[::-1]
        path.append(e)
        
        while G.out_degree(v) == 1:
            x = next(G.successors(v))
            path.append( (v,x) )
            v = x

        if no_duplicates:
            paths.add(tuple(path))
        else:
            paths.append(path)

    if no_duplicates:
        return list(paths)
    else:
        return paths
