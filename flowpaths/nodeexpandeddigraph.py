import networkx as nx
from flowpaths.utils import graphutils as gu

class NodeExpandedDiGraph(nx.DiGraph):
    
    def __init__(
            self,
            G: nx.DiGraph,
            node_flow_attr: str,
            try_filling_in_missing_flow_attr: bool = False,
            node_length_attr: str = None,
            ):
        """
        This class is a subclass of the networkx DiGraph class. It is used to represent a directed graph
        where all nodes `v` have been "expanded" or "subdivided" into an edge `(v.0, v.1)`. This is useful for representing
        graphs where the flow values, or weights, are associated with the nodes, rather than the edges. 
        These expanded edges are then added to the `edges_to_ignore` list, available as a property of this class.

        !!! info "Using this class"

            - Create a `NodeExpandedDiGraph` object by passing a directed graph `G` and the attribute name `node_flow_attr` from where to get the flow values / weights on the nodes.
            - Pass the edges from the `edges_to_ignore` attribute of this class to the decomposition models, in order to ignore all original edges of the graph,
              and thus consider in the constraints only the new edges added in the expanded graph (which have flow values).
            - Solve the decomposition model on the expanded graph.
            - Use the `condense_paths` method to condense the solution paths (which are in the expanded graph) to paths in the original graph.

        Parameters
        ----------
        - `G : nx.DiGraph`
            
            The input directed graph, as networkx DiGraph.

        - `node_flow_attr : str`

            The attribute name from where to get the flow values / weights on the nodes. 
            This attribute must be present in all nodes of the graph. This atrribute for each `v` is then 
            set to the edge `(v.0, v.1)` connecting the new expanded nodes.

        - `try_filling_in_missing_flow_attr : bool`, optional

            If `True`, try filling in missing flow values in the expanded graph (i.e., if some original edge does not have the attribute specified by `node_flow_attr`), 
            by setting them to the flow values of a flow between the sources and the sinks of the original graph, such that for every edge where `node_flow_attr` is present,
            the demand and capacity are equal to the value specified by `node_flow_attr`.
            Default is `False`.

        - `node_length_attr : str`, optional

            The attribute name from where to get the length values on the nodes. Default is `None`. 
            If you specify this attribute, it must be present in all nodes of the graph.

        !!! example "Example"

            ```python
            import flowpaths as fp
            import networkx as nx

            graph = nx.DiGraph()
            graph.add_node("s", flow=13)
            graph.add_node("a", flow=6)
            graph.add_node("b", flow=9)
            graph.add_node("c", flow=13)
            graph.add_node("d", flow=6)
            graph.add_node("t", flow=13)

            # Adding edges
            graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("c", "t"), ("d", "t")])

            # Expand the graph
            ne_graph = fp.NodeExpandedDiGraph(graph, node_flow_attr="flow")

            # Solve the problem on the expanded graph
            mfd_model = fp.MinFlowDecomp(
                ne_graph, 
                flow_attr="flow",
                edges_to_ignore=ne_graph.edges_to_ignore,
                )
            mfd_model.solve()

            if mfd_model.is_solved():
                # Getting the solution in the expanded graph
                solution = mfd_model.get_solution()
                # Condensing the paths in the expanded graph to paths in the the original graph
                original_paths = ne_graph.get_condensed_paths(solution["paths"])
                print("Original paths:", original_paths)
                print("Weights:", solution["weights"])
            ```
        """
        super().__init__()

        if not all(isinstance(node, str) for node in G.nodes()):
            raise ValueError("Every node of the graph must be a string.")
        # if not all nodes have the flow attribute, raise an error
        if not all(node_flow_attr in G.nodes[node] for node in G.nodes()):
            raise ValueError(f"Every node must have the flow attribute specified as `node_flow_attr` ({node_flow_attr}).")

        self.original_G = nx.DiGraph(G)

        if "id" in G.graph:
            self.graph["id"] = G.graph["id"]
            
        self.node_flow_attr = node_flow_attr
        self.__edges_to_ignore = []

        for node in G.nodes:
            node0 = node + '.0'
            node1 = node + '.1'
            self.add_node(node0, **G.nodes[node])
            self.add_node(node1, **G.nodes[node])
            self.add_edge(node0, node1, **G.nodes[node])
            self[node0][node1][node_flow_attr] = G.nodes[node][node_flow_attr]
            if node_length_attr is not None:
                if node_length_attr not in G.nodes[node]:
                    raise ValueError(f"Every node must have the length attribute specified as `node_length_attr` ({node_length_attr}).")
                self[node0][node1][node_length_attr] = G.nodes[node][node_length_attr]

            # Adding in-coming edges
            for pred in G.predecessors(node):
                pred1 = pred + '.1'
                self.add_edge(pred1, node0, **G.edges[pred, node])
                self.__edges_to_ignore.append((pred1, node0))
                
                # If the edge (pred,node) does not have the length attribute, set it to 0
                if node_length_attr is not None:
                    if node_length_attr not in G.edges[pred, node]:
                        self[pred1][node0][node_length_attr] = 0

            # Adding out-going edges
            for succ in G.successors(node):
                succ0 = succ + '.0'
                self.add_edge(node1, succ0, **G.edges[node, succ])
                # This is not necessary, as the edge (node1, succ0) has already been added above, for succ
                # self.__edges_to_ignore.append((node1, succ0))

        if try_filling_in_missing_flow_attr:
            self.__try_filling_in_missing_flow_values()

        nx.freeze(self)    

    def __try_filling_in_missing_flow_values(self):
        
        # Fills in missing flow values in the expanded graph, by setting them to the flow values of a maximum flow
        # between the source and the sink of the original graph, with capacity equal to the flow values of the nodes.
        
        # Create a max flow instance where the edges with missing flow have infinite capacity
        # and the edges with flow have capacity equal to the flow value
        # The source are the sources of the original graph, and the sink are the sinks of the original graph
        # We solve this with the networkx package
        
        min_cost_flow_network = nx.DiGraph(self)

        source_node = f'source{id(min_cost_flow_network)}'
        sink_node = f'sink{id(min_cost_flow_network)}'
        demands_attr = f'demand{id(min_cost_flow_network)}'
        capacities_attr = f'capacities{id(min_cost_flow_network)}'
        costs_attr = f'costs{id(min_cost_flow_network)}'
        
        min_cost_flow_network.add_node(source_node)
        min_cost_flow_network.add_node(sink_node)

        # For every node in the graph, add an edge from the source to the node.0 with infinite capacity
        for node in self.original_G.nodes:
            if self.original_G.in_degree(node) == 0:
                min_cost_flow_network.add_edge(source_node, node + '.0')
                min_cost_flow_network[source_node][node + '.0'].update({demands_attr: 0, capacities_attr: float('inf'), costs_attr: 0})
            if self.original_G.out_degree(node) == 0:
                min_cost_flow_network.add_edge(node + '.1', sink_node)
                min_cost_flow_network[node + '.1'][sink_node].update({demands_attr: 0, capacities_attr: float('inf'), costs_attr: 0})

        for u, v, data in self.edges(data=True):
            if self.node_flow_attr not in data:
                min_cost_flow_network[u][v].update({demands_attr: 0, capacities_attr: float('inf'), costs_attr: 0})
            else:
                min_cost_flow_network[u][v].update({demands_attr: data[self.node_flow_attr], capacities_attr: data[self.node_flow_attr], costs_attr: 0})
        
        flow_value, flow_dict = gu.min_cost_flow(
            G = min_cost_flow_network, 
            s = source_node, 
            t = sink_node, 
            demands_attr = demands_attr,
            capacities_attr = capacities_attr,
            costs_attr = costs_attr,
            )

        if flow_dict is not None:
            for edge in self.edges:
                if self.node_flow_attr not in self.edges[edge]:
                    self.edges[edge][self.node_flow_attr] = flow_dict[edge[0]][edge[1]]

    @property
    def edges_to_ignore(self):
        """
        List of edges to ignore when solving the decomposition model on the expanded graph. 

        These are the edges of the original graph, since only the new edges that have been introduced 
        for every node must considered in the decomposition model, with flow value from the node attribute `node_flow_attr`.
        """
        return self.__edges_to_ignore
    
    def get_expanded_subpath_constraints_nodes(self, subpath_constraints):
        """
        Expand a list of subpath constraints from the original graph (where every constraint is a list **nodes**
        in the original graph) to a list of subpath constraints in the expanded graph (where every constraint 
        is a list of edges (of type `('node.0', 'node.1`)` in the expanded graph).

        Parameters
        ----------
        - `subpath_constraints : list`
            
            List of subpath constraints in the original graph (as lists of **nodes**).

        Returns
        -------
        - `expanded_constraints : list`
            
            List of subpath constraints in the expanded graph (as lists of edges of type `('node.0', 'node.1`)`).
        """

        expanded_constraints = []

        for constraint in subpath_constraints:
            expanded_constraint = []
            for node in constraint:
                if node not in self.original_G.nodes:
                    raise ValueError(f"Node {node} not in the original graph.")
                expanded_constraint.append((node + '.0', node + '.1'))
            expanded_constraints.append(expanded_constraint)

        return expanded_constraints
    
    def get_expanded_subpath_constraints_edges(self, subpath_constraints):
        """
        Expand a list of subpath constraints from the original graph (where every constraint is a list **edges** 
        in the original graph) to a list of subpath constraints in the expanded graph where every constraint 
        is a list of the corresponding edges in the expanded graph).

        Parameters
        ----------
        - `subpath_constraints : list`
            
            List of subpath constraints in the original graph (as lists of **edges**).

        Returns
        -------
        - `expanded_constraints : list`
            
            List of subpath constraints in the expanded graph (as lists of corresponding edges).
        """

        expanded_constraints = []

        for constraint in subpath_constraints:
            expanded_constraint = []
            for edge in constraint:
                if edge not in self.original_G.edges:
                    raise ValueError(f"Edge {edge} not in the original graph.")
                expanded_constraint.append((edge[0] + '.1', edge[1] + '.0'))
            expanded_constraints.append(expanded_constraint)

        return expanded_constraints

    def get_expanded_edge(self, node):
        """
        Get the the expanded edge `('node.0', 'node.1')` for a given node `node` in the original graph.
        """

        if node not in self.original_G.nodes:
            raise ValueError(f"Node {node} not in the original graph.")

        return (node + '.0', node + '.1')

    def get_condensed_paths(self, paths):
        """
        Condense a list of paths from the expanded graph to the original graph. 
        
        This assumes that:

        - The nodes in the expanded graph are named as 'node.0' and 'node.1', where 'node' is the name of the node in the
        original graph. 
        - The paths are lists of nodes in the expanded graph, where the nodes are ordered as 'nodeA.0', 'nodeA.1', 'nodeB.0', 'nodeB.1', etc.
        Meaning that we always have two nodes from the same original node in sequence.

        Parameters
        ----------
        - `paths : list`
            
            List of paths in the expanded graph.

        Returns
        -------
        - `condensed_paths: list`
            
            List of paths in the original graph.

        Raises
        ------
        - `ValueError`
            
            - If the node names in the expanded_path on even positions (starting from 0) do not end with `.0`.
            - If these node names (with the suffix `.0` removed) are not in the original graph.
        """

        condensed_paths = []
        for path in paths:
            condensed_path = []
            for i in range(0, len(path) - 1, 2):
                # Raise an error if the last two symbols of path[i] are not '.0'
                if path[i][-2:] != '.0':
                    raise ValueError(f"Invalid node name in path: {path[i]}")
                node = path[i][:-2]
                if node not in self.original_G.nodes:
                    raise ValueError(f"Node {node} not in the original graph.")
                condensed_path.append(node)
            condensed_paths.append(condensed_path)
        return condensed_paths

if __name__ == "__main__":
    G = NodeExpandedDiGraph()
    G.add_node(1, flow=10)
    G.add_node(2, flow=20)
    G.add_edge(1, 2)
    print(G.nodes[1])
    print(G.nodes[2])
    print(G.edges[1, 2])

    # Output:
    # {'flow': 10}
    # {'flow': 20}
    # {}