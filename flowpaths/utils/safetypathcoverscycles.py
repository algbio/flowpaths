import flowpaths.stdigraph as stdigraph
import flowpaths.utils.dominators as dominators
from queue import Queue

def find_path(adj_dict, s, t):
    """Find a path from s to t using DFS."""
    def dfs_path(node, path: list, visited: set):
        if node == t:
            return True
        visited.add(node)
        for neighbor in adj_dict[node]:
            if neighbor not in visited:
                path.append(neighbor)
                if dfs_path(neighbor, path, visited):
                    return True
                path.pop()  # Backtrack if this path doesn't lead to t
        return False
    
    path = [s]
    visited = set()
    dfs_path(s, path, visited)
    return path

def find_idom(adj_dict, s, t) -> list:
    
    # find arbitrary s-t path p
    p = find_path(adj_dict, s, t)

    # add reversed path to G
    # and remove the original edges of the path
    for i in range(len(p)-1):
        adj_dict[p[i]].remove(p[i+1])  # remove original edges
        adj_dict[p[i+1]].append(p[i])

    n            = len(adj_dict)
    i            = 1
    component = dict()  # [0] * n
    for v in adj_dict.keys():
        component[v] = 0
    q            = Queue(maxsize = n+1)
    component[s] = 1
    first_node   = 0
    first_bridge = None
    q.put(s)

    while component[t]==0: #do while :(

        if i!=1:
            #find first node u of P with component[u]=0. all in all we pay |P| time for this
            while component[p[first_node]] != 0:
                first_node += 1

            first_bridge = ( p[first_node-1] ,p[first_node] )
            break

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

    return first_bridge

def maximal_safe_sequences_via_dominators(G : stdigraph.stDiGraph, X = set()) -> list :

    if X == None or len(X) == 0:
        return []

    s_idoms = dict()
    t_idoms = dict()

    adj_dict = {u: list(G.successors(u)) for u in G.nodes()}
    adj_dict_rev = {u: list(G.predecessors(u)) for u in G.nodes()}

    for (u,v) in G.edges:

        s_idom = find_idom(adj_dict_rev, u, G.source)
        t_idom = find_idom(adj_dict    , v,   G.sink)
        s_idoms[(u,v)] = tuple(reversed(s_idom)) if s_idom != None else G.source
        t_idoms[(u,v)] = t_idom                  if t_idom != None else G.sink

    T_s = dominators.Arc_Dominator_Tree(G.number_of_nodes(), G.source, s_idoms, G.edges, X, G.id+str("_s-domtree"))
    T_t = dominators.Arc_Dominator_Tree(G.number_of_nodes(), G.sink  , t_idoms, G.edges, X, G.id+str("_t-domtree"))

    leaves_s_X = [ node for node,children in T_s.children_X.items() if len(children)==0 ] #those nodes in X that do not s-dominate other nodes with respect to X

    cores = []
    for leaf in leaves_s_X: # O(m): the paths are unitary, so no node can belong to two distinct s- (or t-) unitary paths
        s_unitary_path = T_s.find_unitary_path_X(leaf,   "up")
        t_unitary_path = T_t.find_unitary_path_X(leaf, "down")
        
        if len(t_unitary_path) > len(s_unitary_path):
            continue

        i=0
        good_sequence = True
        while good_sequence and i<len(t_unitary_path):
            if s_unitary_path[i] != t_unitary_path[i]:
                good_sequence = False
            else:
                i=i+1
                
        if i == len(t_unitary_path) and T_t.is_leaf_X(t_unitary_path[len(t_unitary_path)-1]):
            assert(good_sequence==True)
            cores.append(leaf)

    maximal_safe_sequences = []
    for core in cores: # O(length of all maximal safe sequences), with no duplicates
        s_doms = T_s.get_dominators(core)
        t_doms = T_t.get_dominators(core)
        maximal_safe_sequences.append( s_doms[::-1] + t_doms[1:] )
    
    return maximal_safe_sequences
