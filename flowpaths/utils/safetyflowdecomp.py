import flowpaths.stdigraph as stdigraph
from collections import deque 

def compute_flow_decomp_safe_paths(
    G: stdigraph.stDiGraph, flow_attr: str, no_duplicates: bool = True
) -> set():
    """
    Computes all flow decomposition safe paths for a given non-negative flow.
    A path is called flow decompostion safe if it appears in all flow
    decompositions as a subpath of a path.

    Parameters
    ----------
    - `G`: stDiGraph: 

        A directed graph of type stDiGraph.

    - `flow_attr`: str

        The name of the edge attribute where to get the flow values from.

    - `no_duplicates`: bool

        If `True`, the function returns a set of paths without duplicates.
        
    Returns
    -------
    
    - `paths` (list of lists):
    
        A list of flow safe paths, as lists of nodes.

    Raises
    ------

    - ValueError: If an edge does not have the required flow attribute.
    - ValueError: If an edge has a negative flow value.
    """

    # Check that flow is non-negative
    G.get_max_flow_value_and_check_non_negative_flow(
        flow_attr=flow_attr,
        edges_to_ignore=set(G.out_edges(G.source))|set(G.in_edges(G.sink))
    )

    decomp_paths = G.decompose_using_max_bottleck(flow_attr)[0]
    safe_paths_set = set()
    safe_paths_list = []

    # The algorithm follows a two pointer approach computing excess flow
    # See https://doi.org/10.1007/978-3-031-04749-7_11

    for path in decomp_paths:
        if len(path) <= 1:
            continue

        safe_path = deque()
        L, R = 0, 0
        excess_flow = 0
        safe_path.append(path[L])
        path_not_suffix_of_previous = True

        while R+1 < len(path):
            # Initialize new safe path
            if L == R:
                assert len(safe_path) == 1
                assert excess_flow == 0

                R += 1
                excess_flow = G.edges[path[L], path[R]][flow_attr]
                safe_path.append(path[R])
                path_not_suffix_of_previous = True

            # Maximally extend the safe path to the right
            while R+1 < len(path):
                rightdiff = G.edges[path[R], path[R+1]][flow_attr] - sum(G.edges[u, v][flow_attr] for u, v in G.out_edges(path[R]))

                if excess_flow + rightdiff <= 0:
                    break

                excess_flow += rightdiff
                safe_path.append(path[R+1])
                R += 1
                path_not_suffix_of_previous = True

            if path_not_suffix_of_previous:
                safe_paths_set.add(tuple(safe_path.copy())) if no_duplicates else safe_paths_list.append(safe_path.copy())

            # Remove the left most edge of the safe path
            excess_flow -= G.edges[path[L], path[L+1]][flow_attr]
            if L+1 < R:
                excess_flow += sum(G.edges[u, v][flow_attr]
                    for u, v in G.out_edges(path[L+1]))
            safe_path.popleft()
            L += 1
            path_not_suffix_of_previous = False

    if no_duplicates:
        safe_paths_list = [list(sp) for sp in safe_paths_set]
    
    return safe_paths_list
