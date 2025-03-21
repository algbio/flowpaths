import flowpaths.stdigraph as stdigraph
from collections import deque 

def compute_inexact_flow_decomp_safe_paths(
    G: stdigraph.stDiGraph, lowerbound_attr: str, upperbound_attr: str, decomp_paths: list, no_duplicates: bool = True
) -> set():
    """
    Computes all flow decomposition safe paths for a given non-negative inexact flow.
    A path is called flow decomposition safe if it appears in all flow
    decompositions as a subpath of a path.

    Parameters
    ----------
    - `G`: stDiGraph: 

        A directed graph of type stDiGraph.

    - `lowerbound_attr`: str

        The name of the edge attribute where to get the lower bound flow values from.

    - `upperbound_attr`: str

        The name of the edge attribute where to get the upper bound flow values from.

    - `decomp_paths`: list

        The list of paths from which flow decomposition safe paths will be extracted.
        It is recommended that the paths correspond to a flow decomposition, otherwise the output
        does not necessarily correspond to flow decomposition safe paths.

    - `no_duplicates`: bool

        If `True`, the function returns a set of paths without duplicates.
        
    Returns
    -------
    
    - `paths` (list of lists):
    
        A list of maximal-length flow decomposition safe paths, as lists of nodes.

    Raises
    ------

    - ValueError: If an edge in a path from decomp_paths does not have the required flow attributes `lowerbound_attr` and `upperbound_attr`.
    - ValueError: If an edge in a path from decomp_paths has a negative flow lower or upper bound.
    - ValueError: If an edge in a path from decomp_paths has a larger lower bound than upper bound flow attribute.
    - ValueError: If an edge in a path from decomp_paths has a zero flow upper bound.
    """

    # Check the necessary constraints
    for path in decomp_paths:
        for u, v in zip(path, path[1:]):
            for flow_attr in [lowerbound_attr, upperbound_attr]:
                if flow_attr not in G.edges[u, v]:
                    raise ValueError(
                        f"Edge ({u},{v}) does not have the required flow attribute '{flow_attr}'. Check that the attribute passed under 'flow_attr' is present in the edge data."
                    )
            if G.edges[u, v][lowerbound_attr] < 0:
                raise ValueError(
                    f"Edge ({u},{v}) has negative lower bound flow value {G.edges[u, v][lowerbound_attr]}. All lower bound flow values must be >=0."
                )
            if G.edges[u, v][lowerbound_attr] > G.edges[u, v][upperbound_attr]:
                raise ValueError(
                    f"Edge ({u},{v}) has a larger lower bound flow value {G.edges[u, v][lowerbound_attr]} than upper bound flow value {G.edges[u, v][upperbound_attr]}."
                )
            if G.edges[u, v][upperbound_attr] == 0:
                raise ValueError(
                    f"Edge ({u},{v}) has a flow upper bound of zero."
                )

    safe_paths_set = set()
    safe_paths_list = []

    # The algorithm follows a two pointer approach computing inexact excess flow
    # See https://doi.org/10.1007/978-3-031-04749-7_11 and https://doi.org/10.4230/LIPIcs.SEA.2024.14

    for path in decomp_paths:
        if len(path) <= 1:
            continue

        safe_path = deque()
        L, R = 0, 0
        inexact_excess = 0
        safe_path.append(path[L])
        path_not_suffix_of_previous = True

        while R+1 < len(path):
            # Initialize new safe path
            if L == R:
                assert len(safe_path) == 1
                assert inexact_excess == 0

                R += 1
                inexact_excess = G.edges[path[L], path[R]][lowerbound_attr]
                safe_path.append(path[R])
                path_not_suffix_of_previous = True

            # Maximally extend the safe path to the right
            while R+1 < len(path):
                rightdiff = G.edges[path[R], path[R+1]][upperbound_attr] - sum(G.edges[u, v][upperbound_attr] for u, v in G.out_edges(path[R]))

                if inexact_excess + rightdiff <= 0:
                    break

                inexact_excess += rightdiff
                safe_path.append(path[R+1])
                R += 1
                path_not_suffix_of_previous = True

            if path_not_suffix_of_previous:
                safe_paths_set.add(tuple(safe_path.copy())) if no_duplicates else safe_paths_list.append(safe_path.copy())

            # Remove the left most edge of the safe path
            inexact_excess -= G.edges[path[L], path[L+1]][lowerbound_attr]
            if L+1 < R:
                inexact_excess += sum(G.edges[u, v][upperbound_attr] for u, v in G.out_edges(path[L+1])) - G.edges[path[L+1], path[L+2]][upperbound_attr]
                inexact_excess += G.edges[path[L+1], path[L+2]][lowerbound_attr]
            safe_path.popleft()
            L += 1
            path_not_suffix_of_previous = False

    if no_duplicates:
        safe_paths_list = [list(sp) for sp in safe_paths_set]
    
    return safe_paths_list


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

    # Check that flow is non-negative and all edges have the required flow attributes
    G.get_max_flow_value_and_check_non_negative_flow(
        flow_attr=flow_attr,
        edges_to_ignore=set(G.out_edges(G.source))|set(G.in_edges(G.sink))
    )

    decomp_paths = G.decompose_using_max_bottleck(flow_attr)[0]
    return compute_inexact_flow_decomp_safe_paths(G = G, lowerbound_attr = flow_attr, upperbound_attr = flow_attr, decomp_paths = decomp_paths, no_duplicates = no_duplicates)
