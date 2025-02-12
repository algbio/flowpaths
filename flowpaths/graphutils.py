from itertools import count
import networkx as nx
import random
import logging
#from graphviz  import Digraph

logger    = logging.getLogger(__name__)
bigNumber = 1 << 32

def read_graph(graph_raw) -> nx.DiGraph:
    #Input format is: ['#Graph id\n', 'n\n', 'u_1 v_1 w_1\n', ..., 'u_k v_k w_k\n']
    id = graph_raw[0].strip('# ').strip()
    n  = int(graph_raw[1])

    G = nx.DiGraph()
    G.graph['id'] = id

    if n == 0:
        logging.warning("Graph %s has 0 vertices.", id)
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
    

# def is_0_flow_everywhere(G : graph.stDiGraph) -> bool:
#     is_0_everywhere = True
#     for edge in G.flow:
#         if G.flow[edge]!=0:
#             is_0_everywhere=False
#             break
#     return is_0_everywhere


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





'''
def network2dot(G : graph.st_DAG, safe_sequences=[]):
    dot = Digraph(format='pdf')
    dot.graph_attr['rankdir'] = 'LR'        # Display the graph in landscape mode
    dot.node_attr['shape']    = 'rectangle' # Rectangle nodes

    E = G.edge_list
    colors = ['red','blue','green','purple','brown','cyan','yellow','pink','grey']

    for (u,v) in E:
        dot.edge(str(u),str(v))#,label=str(F[(u,v)]))

    for sequence in safe_sequences:
        pathColor = colors[len(sequence)+73 % len(colors)]
        for (u,v) in sequence:
            dot.edge(str(u), str(v), fontcolor=pathColor, color=pathColor, penwidth='2.0') #label=str(weight)
        if len(sequence) == 1:
            dot.node(str(sequence[0]), color=pathColor, penwidth='2.0')
           
    dot.render(filename=G.id,directory='.', view=True)


def visualize(G : graph.st_DAG, paths=[]):
    network2dot(G, paths)
'''


# class GRB_TimeOut(Exception):
#     def __init__(self, message:str):
#         super(GRB_TimeOut, self).__init__('Gurobi TimeOut: ' + message)
