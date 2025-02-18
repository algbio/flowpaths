from itertools import count
import networkx as nx

bigNumber = 1 << 32

def read_graph(graph_raw) -> nx.DiGraph:
    #Input format is: ['#Graph id\n', 'n\n', 'u_1 v_1 w_1\n', ..., 'u_k v_k w_k\n']
    id = graph_raw[0].strip('# ').strip()
    n  = int(graph_raw[1])

    G = nx.DiGraph()
    G.graph['id'] = id

    if n == 0:
        print("Graph %s has 0 vertices.", id)
        return G

    for edge in graph_raw[2:]:
        u, v, w = list(map(lambda x : int(x), edge.split(" ")))
        G.add_edge(u, v, flow = w)

    return G


def read_graphs(filename):
    f      = open(filename, "r")
    lines  = f.readlines()
    f.close()
    graphs = []

    #Assume: every file contains at least one graph
    i,j = 0,1 
    while True:
        if lines[j].startswith("#"):
            graphs.append(read_graph(lines[i:j]))
            i = j
        j += 1
        if (j==len(lines)):
            graphs.append(read_graph(lines[i:j]))
            break

    return graphs

def min_cost_flow(G : nx.DiGraph, s, t):
    
    flowNetwork = nx.DiGraph()
    
    

    flowNetwork.add_node(s, demand = -bigNumber)
    flowNetwork.add_node(t, demand = bigNumber)
            
    for v in G.nodes():
        if v != s and v != t:
            flowNetwork.add_node(v, demand = 0)
    
    flowNetwork.add_edge(s, t, weight = 0)

    counter = count(1) # Start an iterator given increasing integers starting from 1
    edgeMap = dict()
    
    for (x,y) in G.edges():
        z1 = str(next(counter))
        z2 = str(next(counter))
        edgeMap[(x,y)] = z1
        l = G[x][y]['l']
        u = G[x][y]['u']
        c = G[x][y]['c']
        flowNetwork.add_node(z1, demand = l)
        flowNetwork.add_node(z2, demand = -l)
        flowNetwork.add_edge(x, z1, weight = c, capacity = u)
        flowNetwork.add_edge(z1, z2, weight = 0, capacity = u)
        flowNetwork.add_edge(z2, y, weight = 0, capacity = u)

    flowCost, flowDictNet = nx.network_simplex(flowNetwork)
    
    flowDict = dict()
    for x in G.nodes():
        flowDict[x] = dict()

    for (x,y) in G.edges():
        flowDict[x][y] = flowDictNet[x][edgeMap[(x,y)]]

    return flowCost, flowDict