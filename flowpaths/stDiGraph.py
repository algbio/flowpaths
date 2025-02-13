import networkx as nx
import graphutils
import warnings

class stDiGraph(nx.DiGraph):
    def __init__(self, base_graph: nx.DiGraph, 
                 additional_starts: list = [], 
                 additional_ends: list = []):
        super().__init__()
        self.base_graph             = base_graph
        if 'id' in base_graph.graph:
            self.id                     = base_graph.graph['id']
        else:
            self.id                     = id(self)
        self.additional_starts      = set(additional_starts)
        self.additional_ends        = set(additional_ends)
        self.source                 = f"source_{id(self)}"
        self.sink                   = f"sink_{id(self)}"

        self.__build_graph__()

        # TODO: add check that base_graph is acyclic

        nx.freeze(self)

    def __build_graph__(self):
        self.add_nodes_from(self.base_graph.nodes(data=True))
        self.add_edges_from(self.base_graph.edges(data=True))

        for u in self.base_graph.nodes:
            if self.base_graph.in_degree(u) == 0 or u in self.additional_starts:
                self.add_edge(self.source, u)
            if self.base_graph.out_degree(u) == 0 or u in self.additional_ends:
                self.add_edge(u, self.sink)

        self.source_edges = list(self.out_edges(self.source))
        self.sink_edges = list(self.in_edges(self.sink))

        self.width, self.edge_antichain = self.compute_max_edge_antichain(self)
    
    def compute_max_edge_antichain(self, get_antichain = False, weight_function = {}) -> list :

        G_nx       = nx.DiGraph()
        demand     = dict()

        G_nx.add_nodes_from(self.nodes())
        
        for (u,v) in self.edges():
            # the cost of each path is 1
            cost = 1 if u == self.source else 0 
            # the demand of each edge is either from weight_function, or 1 if edge of base_graph, or 0 otherwise
            is_not_source_sink = int(u != self.source and v != self.sink)
            demand[(u,v)] = weight_function[(u,v)] if weight_function else is_not_source_sink
            # adding the edge
            G_nx.add_edge(u, v, l = demand[(u,v)], u = graphutils.bigNumber, c = cost)

        minFlowCost, minFlow = graphutils.min_cost_flow(G_nx, self.source, self.sink)

        def DFS_find_reachable_from_source(u,visited):
            if visited[u]!=0:
                return
            assert(u!=self.sink)
            visited[u] = 1
            for v in self.successors(u):
                if minFlow[u][v] > demand[(u,v)]:
                    DFS_find_reachable_from_source(v, visited)
            for v in self.predecessors(u):
                DFS_find_reachable_from_source(v,visited)

        def DFS_find_saturating(u,visited):
            if visited[u] != 1:
                return
            visited[u] = 2
            for v in self.successors(u):
                if minFlow[u][v] > demand[(u,v)]:
                    DFS_find_saturating(v, visited)
                elif minFlow[u][v] == demand[(u,v)] and demand[(u,v)]>=1 and visited[v]==0:
                    antichain.append((u,v))
            for v in self.predecessors(u):
                DFS_find_saturating(v,visited)

        if get_antichain:
            antichain = []
            visited = {node: 0 for node in self.nodes()}
            DFS_find_reachable_from_source(self.source, visited)
            DFS_find_saturating(self.source, visited)
            if weight_function:
                assert(minFlowCost == sum(map(lambda edge : weight_function[edge], antichain)))
            else:
                assert(minFlowCost == len(antichain))
            return minFlowCost,antichain
        
        return minFlowCost


