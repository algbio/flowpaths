import networkx as nx
from utils import graphutils

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

        nx.freeze(self)

    def __build_graph__(self):
        """
        Builds the graph by adding nodes and edges from the base graph, and 
        connecting source and sink nodes.

        This method performs the following steps:
        1. Checks if the base graph is a directed acyclic graph (DAG). If not, 
           raises a ValueError.
        2. Adds all nodes and edges from the base graph to the current graph.
        3. Connects nodes with no incoming edges or specified as additional 
           start nodes to the source node.
        4. Connects nodes with no outgoing edges or specified as additional 
           end nodes to the sink node.
        5. Stores the edges connected to the source and sink nodes.
        6. Initializes the width attribute to None.

        Raises
        ----------
        - ValueError: If the base graph is not a directed acyclic graph (DAG).
        """

        if not nx.is_directed_acyclic_graph(self.base_graph):
            raise ValueError("The base graph must be a directed acyclic graph.")

        self.add_nodes_from(self.base_graph.nodes(data=True))
        self.add_edges_from(self.base_graph.edges(data=True))

        for u in self.base_graph.nodes:
            if self.base_graph.in_degree(u) == 0 or u in self.additional_starts:
                self.add_edge(self.source, u)
            if self.base_graph.out_degree(u) == 0 or u in self.additional_ends:
                self.add_edge(u, self.sink)

        self.source_edges = list(self.out_edges(self.source))
        self.sink_edges = list(self.in_edges(self.sink))

        self.width = None

    def get_width(self) -> int:
        """
        Calculate and return the width of the graph.
        The width is computed as the maximum edge antichain if it has not been
        previously calculated and stored. If the width has already been computed,
        the stored value is returned.

        Returns
        ----------
        - int: The width of the graph.
        """
        
        if self.width == None:
            width, _ = self.compute_max_edge_antichain(self)
            self.width = width

        return self.width
    
    def compute_max_edge_antichain(self, get_antichain = False, weight_function = None):
        """
        Computes the maximum edge antichain in a directed graph.

        Parameters
        ----------
        - get_antichain (bool): If True, the function also returns the antichain along with its cost. Default is False.
        - weight_function (dict): A dictionary where keys are edges (tuples) and values are weights. 
                If None, weights 1 are used for original graph edges, and weights 0 are used for global source / global sink edges. 
                If given, the antichain weight is computed as the sum of the weights of the edges in the antichain,
                where edges that have some missing weight again get weight 0. 
                Default is None.
        
        Returns
        ----------
        - If get_antichain is False, returns the size of maximum edge antichain.
        - If get_antichain is True, returns a tuple containing the 
                size of maximum edge antichain and the antichain.
        """

        G_nx       = nx.DiGraph()
        demand     = dict()

        G_nx.add_nodes_from(self.nodes())
        
        for (u,v) in self.edges():
            # the cost of each path is 1
            cost = 1 if u == self.source else 0 
            
            edge_demand = int(u != self.source and v != self.sink)
            if weight_function:
                edge_demand = weight_function.get((u,v),0)
            
            demand[(u,v)] = edge_demand
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


    def get_reachable_nodes_from(self, v) -> set:
        """
        Get all nodes reachable from a given node in the graph.
        This method performs a depth-first search (DFS) starting from the specified node
        and returns a set of all nodes that can be reached from it, including the given node `v`.

        Args
        ----------
        - v: The starting node from which to find all reachable nodes.

        Returns
        ----------
        - A set of nodes that are reachable from the given node `v`.
        """

        successors = nx.dfs_successors(self, source=v)
        reachable_nodes = {v} | {reachable_node for node in successors for reachable_node in successors[node]}
        
        return reachable_nodes

    def get_reachable_nodes_reverse_from(self, v) -> set:
        """
        Get the set of nodes that are reachable in reverse from a given node `v`.
        This method computes the set of nodes that can reach the given node `v`, including node `v`,
        by traversing the graph in reverse. If the given node `v` is the source 
        node, it returns a set containing only `v`.
        
        Parameters
        ----------
        - v The node from which to find all reachable nodes in reverse.
        
        Returns
        ----------
        - A set of nodes that can reach the given node `v` by traversing the graph in reverse.
        """

        if v == self.source:
            return {v}
        
        rev_G = nx.DiGraph(self).reverse()
        predecessors = nx.dfs_successors(rev_G, source=v)
        reachable_nodes_reverse = {v} | {reachable_node_reverse for node in predecessors for reachable_node_reverse in predecessors[node]}
        
        return reachable_nodes_reverse
    
    def decompose_using_max_bottleck(self, flow_attr: str):
        """
        Decomposes the flow greedily into paths using the maximum bottleneck algorithm.
        This method iteratively finds the path with the maximum bottleneck capacity
        in the graph and decomposes the flow along that path. The process continues
        until no more paths can be found.
        
        Returns
        ----------
        - tuple: A tuple containing two lists:
            - paths (list of lists): A list of paths, where each path is represented
                as a list of nodes.
            - weights (list): A list of weights (bottleneck capacities) corresponding to each path.
        """
        
        paths = list()
        weights = list()
        
        temp_G = nx.DiGraph()
        temp_G.add_nodes_from(self.nodes())
        temp_G.add_edges_from(self.edges(data=True))
        temp_G.remove_nodes_from([self.source, self.sink])
        
        while True:
            bottleneck, path = graphutils.maxBottleckPath(temp_G, flow_attr)
            if path is None:
                break
                
            for i in range(len(path)-1):
                temp_G[path[i]][path[i+1]][flow_attr] -= bottleneck
            
            paths.append(path)
            weights.append(bottleneck)
            
        return (paths, weights)


