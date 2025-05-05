import networkx as nx
from flowpaths.utils import graphutils
import flowpaths.utils as utils

class stDiGraph(nx.DiGraph):
    # # Cache for storing processed graphs keyed by id(G)
    # _cached_graphs = {}
    # _use_cache = False

    # def __new__(cls, G, *args, **kwargs):
    #     # If a processed instance for this graph id already exists, return it        
    #     if kwargs.get("use_cache", cls._use_cache):
    #         obj = cls._cached_graphs.get(id(G))
    #         if obj is not None:
    #             utils.logger.debug(f"{cls.__name__}.__new__(): found cached instance for graph id {id(G)}")
    #             return obj
            
    #     # Otherwise, create a new instance
    #     obj = super().__new__(cls)
        
    #     if kwargs.get("use_cache", cls._use_cache):
    #         cls._cached_graphs[id(G)] = obj
    #         utils.logger.debug(f"{cls.__name__}.__new__(): cached the instance of graph id {id(G)}")
    #     return obj

    def __init__(
        self,
        base_graph: nx.DiGraph,
        additional_starts: list = [],
        additional_ends: list = [],
        # use_cache: bool = _use_cache,
    ):
        # # Optionally, check if already initialized to avoid reprocessing:
        # if use_cache and hasattr(self, "_initialized") and self._initialized:
        #     utils.logger.debug(f"{__name__}.__init__(): skipping init since we found a cached instance for graph id {id(base_graph)}")
        #     return

        if not all(isinstance(node, str) for node in base_graph.nodes()):
            utils.logger.error(f"{__name__}: Every node of the graph must be a string.")
            raise ValueError("Every node of the graph must be a string.")

        super().__init__()
        self.base_graph = base_graph
        if "id" in base_graph.graph:
            self.id = base_graph.graph["id"]
        else:
            self.id = id(self)
        self.additional_starts = set(additional_starts)
        self.additional_ends = set(additional_ends)
        self.source = f"source_{id(self)}"
        self.sink = f"sink_{id(self)}"

        self.__build_graph__()

        nx.freeze(self)

        # self._initialized = True
        # utils.logger.debug(f"{__name__}.__init__(): initialized for graph id {id(base_graph)}")

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
            utils.logger.error(f"{__name__}: The base graph must be a directed acyclic graph.")
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

        self.source_sink_edges = set(self.source_edges + self.sink_edges)

        self.width = None
        self.flow_width = None

        self.topological_order = list(nx.topological_sort(self))
        self.topological_order_rev = list(reversed(self.topological_order))

        # These two dict store the set of node (resp. edges) reachable from each node, including the node itself
        self.__reachable_nodes_from = None
        self.__reachable_edges_from = None
        
        # These two dict store the set of node (resp. edges) reverse reachable from each node
        self.__reachable_nodes_rev_from = None
        self.__reachable_edges_rev_from = None

    @property
    def reachable_nodes_from(self):

        if self.__reachable_nodes_from is None:
            # Initialize by traversing the nodes in reverse topological order.
            self.__reachable_nodes_from = {node:{node} for node in self.nodes()}
            for node in self.topological_order_rev:
                for v in self.successors(node):
                    self.__reachable_nodes_from[node] |= self.__reachable_nodes_from[v]
        
        return self.__reachable_nodes_from
    
    @property
    def reachable_edges_from(self):
        
        if self.__reachable_edges_from is None:
            # Initialize by traversing the nodes in reverse topological order.
            self.__reachable_edges_from = {node:set() for node in self.nodes()}
            for node in self.topological_order_rev:
                for v in self.successors(node):
                    self.__reachable_edges_from[node] |= self.__reachable_edges_from[v]
                    self.__reachable_edges_from[node] |= {(node, v)}
        
        return self.__reachable_edges_from

    @property
    def reachable_nodes_rev_from(self):

        if self.__reachable_nodes_rev_from is None:
            # Initialize by traversing the nodes in topological order.
            self.__reachable_nodes_rev_from = {node:{node} for node in self.nodes()}
            for node in self.topological_order:
                for v in self.predecessors(node):
                    self.__reachable_nodes_rev_from[node] |= self.__reachable_nodes_rev_from[v]

        return self.__reachable_nodes_rev_from

    @property
    def reachable_edges_rev_from(self):

        if self.__reachable_edges_rev_from is None:
            # Initialize by traversing the nodes in topological order.
            self.__reachable_edges_rev_from = {node:set() for node in self.nodes()}
            for node in self.topological_order:
                for v in self.predecessors(node):
                    self.__reachable_edges_rev_from[node] |= self.__reachable_edges_rev_from[v]
                    self.__reachable_edges_rev_from[node] |= {(v, node)}

        return self.__reachable_edges_rev_from

    def get_width(self, edges_to_ignore: list = None) -> int:
        """
        Calculate and return the width of the graph.
        The width is computed as the minimum number of paths needed to cover all the edges of the graph, 
        except those in the `edges_to_ignore` list. 
        
        If the width has already been computed and `edges_to_ignore` is empty,
        the stored value is returned.

        Returns
        ----------
        - int: The width of the graph.
        """

        if self.width is not None and (edges_to_ignore is None or len(edges_to_ignore) == 0):
            return self.width
        
        edges_to_ignore_set = set(edges_to_ignore or [])

        weight_function = {e: 1 for e in self.edges() if e not in edges_to_ignore_set}
        self.width = self.compute_max_edge_antichain(get_antichain=False, weight_function=weight_function)

        return self.width

    def get_flow_width(self, flow_attr: str, edges_to_ignore: list = None) -> int:
        """
        Calculate, store, and return the [flow-width](https://arxiv.org/abs/2409.20278) of the graph.
        The flow width is computed as the minimum number to cover all the edges, with the constraint 
        that an edge cannot be covered more time than the flow value given as `flow_attr` in the edge data.
        
        If the flow-width has already been computed, the stored value is returned.

        Returns
        ----------
        - int: The flow-width of the graph.
        """

        if self.flow_width != None:
            return self.flow_width
        
        G_nx = nx.DiGraph()

        edges_to_ignore_set = set(edges_to_ignore or [])

        G_nx.add_nodes_from(self.nodes())

        for u, v in self.edges():
            # the cost of each path is 1
            cost = 1 if u == self.source else 0

            edge_demand = int(u != self.source and v != self.sink)
            if (u, v) in edges_to_ignore_set:
                edge_demand = 0
            edge_capacity = self[u][v].get(flow_attr, float('inf'))

            # adding the edge
            G_nx.add_edge(u, v, l=edge_demand, u=edge_capacity, c=cost)

        minFlowCost, _ = graphutils.min_cost_flow(G_nx, self.source, self.sink)

        self.flow_width = minFlowCost

        return self.flow_width

    def compute_max_edge_antichain(self, get_antichain=False, weight_function=None):
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

        G_nx = nx.DiGraph()
        demand = dict()

        G_nx.add_nodes_from(self.nodes())

        for u, v in self.edges():
            # the cost of each path is 1
            cost = 1 if u == self.source else 0

            edge_demand = int(u != self.source and v != self.sink)
            if weight_function:
                edge_demand = weight_function.get((u, v), 0)

            demand[(u, v)] = edge_demand
            # adding the edge
            G_nx.add_edge(u, v, l=demand[(u, v)], u=graphutils.bigNumber, c=cost)

        minFlowCost, minFlow = graphutils.min_cost_flow(G_nx, self.source, self.sink)

        # def DFS_find_reachable_from_source(u, visited):
        #     if visited[u] != 0:
        #         return
        #     assert u != self.sink
        #     visited[u] = 1
        #     for v in self.successors(u):
        #         if minFlow[u][v] > demand[(u, v)]:
        #             if visited[v] == 0:
        #                 DFS_find_reachable_from_source(v, visited)
        #     for v in self.predecessors(u):
        #         if visited[v] == 0:
        #             DFS_find_reachable_from_source(v, visited)
        
        # The following code was created by Claude 3.7 Sonnet to avoid recursion and uses a stack instead.
        def DFS_find_reachable_from_source(start_node, visited):
            stack = [start_node]
            
            while stack:
                u = stack.pop()
                if visited[u] != 0:
                    continue
                    
                assert u != self.sink
                visited[u] = 1
                
                for v in self.successors(u):
                    if minFlow[u][v] > demand[(u, v)] and visited[v] == 0:
                        stack.append(v)
                        
                for v in self.predecessors(u):
                    if visited[v] == 0:
                        stack.append(v)

        # def DFS_find_saturating(u, visited):
        #     if visited[u] != 1:
        #         return
        #     visited[u] = 2
        #     for v in self.successors(u):
        #         if minFlow[u][v] > demand[(u, v)]:
        #             DFS_find_saturating(v, visited)
        #         elif (
        #             minFlow[u][v] == demand[(u, v)]
        #             and demand[(u, v)] >= 1
        #             and visited[v] == 0
        #         ):
        #             antichain.append((u, v))
        #     for v in self.predecessors(u):
        #         DFS_find_saturating(v, visited)

        # The following code was created by Claude 3.7 Sonnet to avoid recursion and uses a stack instead.
        def DFS_find_saturating(start_node, visited):
            stack = [start_node]
            
            while stack:
                u = stack.pop()
                
                if visited[u] != 1:
                    continue
                    
                visited[u] = 2
                
                # Process successors
                for v in self.successors(u):
                    if minFlow[u][v] > demand[(u, v)]:
                        if visited[v] == 1:  # Only visit nodes marked as reachable (1)
                            stack.append(v)
                    elif (minFlow[u][v] == demand[(u, v)] 
                        and demand[(u, v)] >= 1 
                        and visited[v] == 0):
                        antichain.append((u, v))
                
                # Process predecessors
                for v in self.predecessors(u):
                    if visited[v] == 1:  # Only visit nodes marked as reachable (1)
                        stack.append(v)

        if get_antichain:
            antichain = []
            visited = {node: 0 for node in self.nodes()}
            DFS_find_reachable_from_source(self.source, visited)
            DFS_find_saturating(self.source, visited)
            if weight_function:
                assert minFlowCost == sum(
                    map(lambda edge: weight_function[edge], antichain)
                )
            else:
                assert minFlowCost == len(antichain)
            return minFlowCost, antichain

        return minFlowCost

    def decompose_using_max_bottleneck(self, flow_attr: str):
        """
        Decomposes the flow greedily into paths using the maximum bottleneck algorithm.
        This method iteratively finds the path with the maximum bottleneck capacity
        in the graph and decomposes the flow along that path. The process continues
        until no more paths can be found.

        !!! note "Note"
            The decomposition path do not contain the global source nor sink.

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
            bottleneck, path = graphutils.max_bottleneck_path(temp_G, flow_attr)
            if path is None:
                break

            for i in range(len(path) - 1):
                temp_G[path[i]][path[i + 1]][flow_attr] -= bottleneck

            paths.append(path)
            weights.append(bottleneck)

        return (paths, weights)

    def get_non_zero_flow_edges(
        self, flow_attr: str, edges_to_ignore: set = set()
    ) -> set:
        """
        Get all edges with non-zero flow values.

        Returns
        -------
        set
            A set of edges (tuples) that have non-zero flow values.
        """

        non_zero_flow_edges = set()
        for u, v, data in self.edges(data=True):
            if (u, v) not in edges_to_ignore and data.get(flow_attr, 0) != 0:
                non_zero_flow_edges.add((u, v))

        return non_zero_flow_edges

    def get_max_flow_value_and_check_non_negative_flow(
        self, flow_attr: str, edges_to_ignore: set
    ) -> float:
        """
        Determines the maximum flow value in the graph and checks for positive flow values.

        This method iterates over all edges in the graph, ignoring edges specified in
        `self.edges_to_ignore`. It checks if each edge has the required flow attribute
        specified by `self.flow_attr`. If an edge does not have this attribute, a
        ValueError is raised. If an edge has a negative flow value, a ValueError is
        raised. The method returns the maximum flow value found among all edges.

        Returns
        -------
        - float: The maximum flow value among all edges in the graph.

        Raises
        -------
        - ValueError: If an edge does not have the required flow attribute.
        - ValueError: If an edge has a negative flow value.
        """

        w_max = float("-inf")
        if edges_to_ignore is None:
            edges_to_ignore = set()

        for u, v, data in self.edges(data=True):
            if (u, v) in edges_to_ignore:
                continue
            if not flow_attr in data:
                utils.logger.error(
                    f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data."
                )
                raise ValueError(
                    f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data."
                )
            if data[flow_attr] < 0:
                utils.logger.error(
                    f"Edge ({u},{v}) has negative flow value {data[flow_attr]}. All flow values must be >=0."
                )
                raise ValueError(
                    f"Edge ({u},{v}) has negative flow value {data[flow_attr]}. All flow values must be >=0."
                )
            w_max = max(w_max, data[flow_attr])

        return w_max
