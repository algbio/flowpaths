import networkx as nx

import flowpaths.kmindiscordantnodescycles as kmindiscordantnodescycles
import flowpaths.numpathsoptimization as numpathsoptimization


class MinPathsMinDiscordantNodesCycles(numpathsoptimization.NumPathsOptimization):
    """
    Find a minimum number of walks for k-MinDiscordantNodes on cyclic graphs by iterating over k.

    This class is a thin wrapper around NumPathsOptimization with:
    - model_type fixed to kMinDiscordantNodesCycles
    - stop_on_delta_abs fixed to 0

    Therefore, the search stops at the first k where the objective value does
    not improve in absolute value compared to the reference used by
    NumPathsOptimization.
    """

    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        weight_type: type = float,
        discordance_tolerance: float = 0.1,
        subset_constraints: list = None,
        additional_starts: list = None,
        additional_ends: list = None,
        optimization_options: dict = None,
        solver_options: dict = None,
        min_num_paths: int = 1,
        max_num_paths: int = 2**64,
        time_limit: float = float("inf"),
    ):
        super().__init__(
            model_type=kmindiscordantnodescycles.kMinDiscordantNodesCycles,
            stop_on_delta_abs=0,
            min_num_paths=min_num_paths,
            max_num_paths=max_num_paths,
            time_limit=time_limit,
            G=G,
            flow_attr=flow_attr,
            weight_type=weight_type,
            discordance_tolerance=discordance_tolerance,
            subset_constraints=subset_constraints or [],
            additional_starts=additional_starts or [],
            additional_ends=additional_ends or [],
            optimization_options=optimization_options,
            solver_options=solver_options or {},
        )