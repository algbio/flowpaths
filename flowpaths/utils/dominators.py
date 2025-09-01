class Arc_Dominator_Tree:

    def __init__(self, n:int, start:str, idoms:dict, edgelist : list, X : set, id:str):
        self.id              = id
        self.n               = n
        self.start           = start
        self.X               = X
        self.idom            = idoms
        self.children        = {e: [] for e in edgelist}
        self.children[start] = []

        for node,idom in self.idom.items():
            self.children[idom].append(node)

        self.idom_X            = dict()
        # self.idom_X[start]     = start
        self.children_X        = {e: [] for e in X}
        self.children_X[start] = []
        self.build_children_relation_X()

    def is_leaf_X(self, arc : tuple):
        # if arc not in self.children_X:
        #     return False
        return len(self.children_X[arc])==0

    def has_unique_child_X(self, arc : tuple):
        # if arc not in self.children_X:
        #     return False
        return len(self.children_X[arc])==1
    
    def get_dominators(self, arc : tuple):
        dominators = []
        while arc != self.start:
            dominators.append(arc)
            arc = self.idom[arc]
        return dominators
    
    def build_children_relation_X(self):

        def dfs(node, last_in_X): # recall that X is a set of arcs. the term "node" is to allude to nodes of the dominator tree
            if node != last_in_X and node in self.X: # note that sink and source are never in X
                self.children_X[last_in_X].append(node)
                self.idom_X[node] = last_in_X
                last_in_X = node
            for child in self.children[node]:
                dfs(child, last_in_X)

        dfs(self.start, self.start)

    #a unitary path in a dominator tree is a path towards the root such that every node has exactly one children except the deepest node
    def find_unitary_path_X(self, arc : tuple, mode : str):
        if mode == "up":
            fn = ( lambda node : self.idom_X[node]        if self.has_unique_child_X(self.idom_X[node]) and self.idom_X[node] != self.start else node )
        if mode == "down":
            fn = ( lambda node : self.children_X[node][0] if self.has_unique_child_X(node)                                                  else node )

        path = [arc]
        while arc != fn(arc):
            arc = fn(arc)
            path.append(arc)
        return path
