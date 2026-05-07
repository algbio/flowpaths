import networkx as nx
from copy import deepcopy
import time
import numbers
from types import SimpleNamespace

import flowpaths.kmindiscordantnodes as kmindiscordantnodes
import flowpaths.minpathcover as minpathcover
import flowpaths.nodeexpandeddigraph as nedg
import flowpaths.numpathsoptimization as numpathsoptimization
import flowpaths.utils as utils


class MinPathsMinDiscordantNodes(numpathsoptimization.NumPathsOptimization):
    """
    Minimize the number of paths for k-MinDiscordantNodes on DAG-like inputs.

    The class wraps :class:`NumPathsOptimization` with:
    - ``model_type`` fixed to ``kMinDiscordantNodes``
    - ``stop_on_delta_abs`` fixed to ``0``

    This means the search over ``k`` stops at the first plateau, i.e. when the
    objective no longer improves in absolute value.

    Multi-component behavior
    ------------------------
    If ``G`` has multiple weakly connected components, this class solves one
    component-local instance per component and merges the solutions.
    Constraints and optional start/end nodes are filtered per component.
    A single global ``time_limit`` is enforced across all component solves.
    """

    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        weight_type: type = float,
        discordance_tolerance: float = 0.1,
        subsequence_constraints: list = None,
        additional_starts: list = None,
        additional_ends: list = None,
        optimization_options: dict = None,
        solver_options: dict = None,
        round_flow_values_to_int: bool = True,
        flow_values_divisor: float = 1,
        min_num_paths: int = None,
        max_num_paths: int = 2**64,
        time_limit: float = float("inf"),
    ):
        """
        Build a MinPathsMinDiscordantNodes optimizer.

        Parameters
        ----------
        G : nx.DiGraph
            Input graph.
        flow_attr : str
            Node/edge attribute name used by the wrapped discordance model.
        weight_type : type, default=float
            Type for path weights (typically ``int`` or ``float``).
        discordance_tolerance : float, default=0.1
            Relative tolerance used when deciding if a node is discordant.
        subsequence_constraints : list, optional
            List of node sequences that must be covered. In multi-component
            mode, each sequence must lie entirely inside one component.
        additional_starts : list, optional
            Optional allowed start nodes. Filtered per component in
            multi-component mode.
        additional_ends : list, optional
            Optional allowed end nodes. Filtered per component in
            multi-component mode.
        optimization_options : dict, optional
            Options forwarded to underlying models.
        solver_options : dict, optional
            Solver backend options (HiGHS/Gurobi wrapper options).
        flow_values_divisor : float, default=1
            Divides node/edge flow values before solving. Division happens
            before optional rounding.
        min_num_paths : int, optional
            Lower bound for ``k``. If ``None``, a lower bound is computed via
            ``MinPathCover`` on a node-expanded graph (per component when
            componentized).
        max_num_paths : int, default=2**64
            Upper bound for ``k``.
        time_limit : float, default=inf
            Global time limit in seconds. For multi-component graphs, each
            component receives the remaining budget.
        """
        self._is_componentized = False
        self._component_graphs = []
        self._component_labels = []
        self._component_models = []
        self._component_solutions = None
        self._component_objective_value = None
        self._logged_cross_component_constraints = set()
        self._constraint_reachability_infeasible = False
        self._path_cover_seed_info = {}
        self.weight_type = weight_type
        self._round_flow_values_to_int = round_flow_values_to_int
        self._flow_values_divisor = self._validate_flow_values_divisor(flow_values_divisor)
        self._original_graph = G.copy()

        self._model_init_kwargs = {
            "flow_attr": flow_attr,
            "weight_type": weight_type,
            "discordance_tolerance": discordance_tolerance,
            "subsequence_constraints": subsequence_constraints or [],
            "additional_starts": additional_starts or [],
            "additional_ends": additional_ends or [],
            "optimization_options": optimization_options,
            "solver_options": solver_options or {},
            "round_flow_values_to_int": round_flow_values_to_int,
            "flow_values_divisor": self._flow_values_divisor,
            "min_num_paths": min_num_paths,
            "max_num_paths": max_num_paths,
            "time_limit": time_limit,
        }

        G = self._get_preprocessed_graph_with_scaled_flows(
            G=G,
            flow_attr=flow_attr,
            flow_values_divisor=self._flow_values_divisor,
            round_flow_values_to_int=round_flow_values_to_int,
        )

        if not self._validate_subsequence_constraint_reachability(
            graph=G,
            constraints=self._model_init_kwargs["subsequence_constraints"],
        ):
            self._constraint_reachability_infeasible = True
            return

        weak_components = list(nx.weakly_connected_components(G))
        if len(weak_components) > 1:
            self._is_componentized = True
            utils.logger.info(
                f"{__name__}: Detected {len(weak_components)} weakly connected components; solving them independently.",
            )
            for component_index, nodes in enumerate(weak_components, start=1):
                component_graph = G.subgraph(nodes).copy()
                component_name = self._set_component_graph_component_suffix(
                    component_graph=component_graph,
                    parent_graph=G,
                    component_index=component_index,
                    total_components=len(weak_components),
                )
                self._component_graphs.append(component_graph)
                self._component_labels.append(component_name)
                utils.logger.info(
                    f"{__name__}: Prepared component {component_index}/{len(weak_components)} as '{component_name}' with {component_graph.number_of_nodes()} nodes and {component_graph.number_of_edges()} edges.",
                )
            super().__init__(
                model_type=kmindiscordantnodes.kMinDiscordantNodes,
                stop_on_delta_abs=0,
                min_num_paths=(1 if min_num_paths is None else min_num_paths),
                max_num_paths=max_num_paths,
                time_limit=time_limit,
                G=G,
                flow_attr=flow_attr,
                weight_type=weight_type,
                discordance_tolerance=discordance_tolerance,
                subsequence_constraints=subsequence_constraints or [],
                additional_starts=additional_starts or [],
                additional_ends=additional_ends or [],
                optimization_options=optimization_options,
                solver_options=solver_options or {},
            )
            return

        if min_num_paths is None:
            min_num_paths_lb, seed_paths = self._compute_min_path_cover_lower_bound_and_seed(
                G=G,
                subsequence_constraints=subsequence_constraints or [],
                additional_starts=additional_starts or [],
                additional_ends=additional_ends or [],
                optimization_options=optimization_options or {},
                solver_options=solver_options or {},
            )
        else:
            min_num_paths_lb = min_num_paths
            seed_paths = None

        merged_optimization_options = self._get_optimization_options_with_path_cover_seed(
            optimization_options=optimization_options,
            seed_paths=seed_paths,
        )
        self._model_init_kwargs["optimization_options"] = merged_optimization_options
        
        super().__init__(
            model_type=kmindiscordantnodes.kMinDiscordantNodes,
            stop_on_delta_abs=0,
            min_num_paths=max(min_num_paths_lb, 1),
            max_num_paths=max_num_paths,
            time_limit=time_limit,
            G=G,
            flow_attr=flow_attr,
            weight_type=weight_type,
            discordance_tolerance=discordance_tolerance,
            subsequence_constraints=subsequence_constraints or [],
            additional_starts=additional_starts or [],
            additional_ends=additional_ends or [],
            optimization_options=merged_optimization_options,
            solver_options=solver_options or {},
        )

    def _validate_flow_values_divisor(self, flow_values_divisor: float) -> float:
        """Validate and normalize the flow scaling divisor."""
        if not isinstance(flow_values_divisor, numbers.Real) or flow_values_divisor <= 0:
            raise ValueError(f"flow_values_divisor must be a positive real value, not {flow_values_divisor}")
        return float(flow_values_divisor)

    def _get_preprocessed_graph_with_scaled_flows(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        flow_values_divisor: float,
        round_flow_values_to_int: bool,
    ) -> nx.DiGraph:
        """Return an internal graph copy with flow scaling and optional rounding."""
        rounded_graph = G.copy()

        scaled_node_flows = 0
        scaled_edge_flows = 0
        rounded_node_flows = 0
        rounded_edge_flows = 0

        for node, data in rounded_graph.nodes(data=True):
            if flow_attr not in data:
                continue
            value = data[flow_attr]
            if not isinstance(value, numbers.Real):
                utils.logger.warning(
                    f"{__name__}: Skipping non-numeric node flow for node '{node}' and attribute '{flow_attr}': {value}",
                )
                continue

            scaled_value = float(value) / flow_values_divisor
            if scaled_value != value:
                scaled_node_flows += 1

            rounded_value = int(round(scaled_value)) if round_flow_values_to_int else scaled_value
            if rounded_value != value:
                rounded_node_flows += 1
            data[flow_attr] = rounded_value

        for source, target, data in rounded_graph.edges(data=True):
            if flow_attr not in data:
                continue
            value = data[flow_attr]
            if not isinstance(value, numbers.Real):
                utils.logger.warning(
                    f"{__name__}: Skipping non-numeric edge flow for edge ({source}, {target}) and attribute '{flow_attr}': {value}",
                )
                continue

            scaled_value = float(value) / flow_values_divisor
            if scaled_value != value:
                scaled_edge_flows += 1

            rounded_value = int(round(scaled_value)) if round_flow_values_to_int else scaled_value
            if rounded_value != value:
                rounded_edge_flows += 1
            data[flow_attr] = rounded_value

        utils.logger.info(
            f"{__name__}: Preprocessed flow values for attribute '{flow_attr}' with divisor={flow_values_divisor} "
            f"(nodes scaled={scaled_node_flows}, edges scaled={scaled_edge_flows}, "
            f"nodes rounded={rounded_node_flows}, edges rounded={rounded_edge_flows}, "
            f"round_to_int={round_flow_values_to_int}).",
        )
        return rounded_graph

    def _get_trivial_single_node_solution(self, graph: nx.DiGraph):
        """Return a direct feasible solution for one isolated node, if applicable."""
        if graph.number_of_nodes() != 1 or graph.number_of_edges() != 0:
            return None

        node = next(iter(graph.nodes()))
        node_flow = graph.nodes[node].get(self._model_init_kwargs["flow_attr"], None)
        if node_flow is None:
            return None

        return {
            "paths": [[node]],
            "weights": [self.weight_type(node_flow)],
            "discordant_nodes": {node: 0},
        }

    def _compute_min_path_cover_lower_bound_and_seed(
        self,
        G: nx.DiGraph,
        subsequence_constraints: list,
        additional_starts: list,
        additional_ends: list,
        optimization_options: dict,
        solver_options: dict,
    ):
        """Compute the structural lower bound and retain a path-cover witness for seeding/logging."""
        G_expanded = deepcopy(G)
        node_flow_attr = str(id(G_expanded)) + "_flow_attr"
        for node in G_expanded.nodes():
            G_expanded.nodes[node][node_flow_attr] = 0

        ne_graph = nedg.NodeExpandedDiGraph(G_expanded, node_flow_attr=node_flow_attr)

        expanded_subpath_constraints = []
        for constraint in subsequence_constraints:
            expanded_subpath_constraints.append([ne_graph.get_expanded_edge(node) for node in constraint])

        min_path_cover_model = minpathcover.MinPathCover(
            G=ne_graph,
            cover_type="edge",
            subpath_constraints=expanded_subpath_constraints,
            elements_to_ignore=ne_graph.edges_to_ignore,
            additional_starts=additional_starts,
            additional_ends=additional_ends,
            optimization_options=optimization_options or {},
            solver_options=solver_options or {},
        )
        mpc_solved = min_path_cover_model.solve()
        solve_status = None
        if isinstance(min_path_cover_model.solve_statistics, dict):
            solve_status = min_path_cover_model.solve_statistics.get("milp_solver_status_for_num_paths_" + str(getattr(min_path_cover_model.model, "k", "")))

        if not mpc_solved:
            fallback_lb = 1
            self._path_cover_seed_info = {
                "lower_bound": fallback_lb,
                "seed_paths": [],
                "solve_status": solve_status,
                "solved": False,
            }
            utils.logger.warning(
                f"{__name__}: MinPathCover failed while building a structural feasibility witness; falling back to lower bound {fallback_lb}.",
            )
            return fallback_lb, None

        min_path_cover_solution = min_path_cover_model.get_solution()
        seed_paths = min_path_cover_solution.get("paths", [])
        if seed_paths and isinstance(seed_paths[0][0], str) and seed_paths[0][0].startswith("source_"):
            seed_paths = self._condense_expanded_seed_paths(seed_paths)
        lower_bound = min_path_cover_model.get_objective_value()
        self._path_cover_seed_info = {
            "lower_bound": lower_bound,
            "seed_paths": seed_paths,
            "solve_status": solve_status,
            "solved": True,
        }
        utils.logger.info(
            f"{__name__}: MinPathCover found a structural feasibility witness with {len(seed_paths)} paths; using lower bound k={lower_bound}.",
        )
        return lower_bound, seed_paths

    def _get_optimization_options_with_path_cover_seed(self, optimization_options: dict, seed_paths):
        """Return model optimization options augmented with a path-cover witness when available."""
        merged_options = deepcopy(optimization_options) if optimization_options is not None else {}
        if seed_paths:
            merged_options["path_cover_mip_start_paths"] = deepcopy(seed_paths)
        return merged_options

    def _condense_expanded_seed_paths(self, expanded_paths: list):
        """Map expanded-graph source/sink paths to original node sequences."""
        condensed_paths = []
        for path in expanded_paths:
            condensed_path = []
            for node in path:
                if not isinstance(node, str):
                    continue
                if node.startswith("source_") or node.startswith("sink_"):
                    continue
                if node.endswith(".0"):
                    condensed_path.append(node[:-2])
            condensed_paths.append(condensed_path)
        return condensed_paths

    def _merge_path_cover_seed_info_into_statistics(self):
        """Expose the structural path-cover witness in solve statistics when available."""
        if not self._path_cover_seed_info:
            return
        if self.solve_statistics is None:
            self.solve_statistics = {}
        self.solve_statistics.setdefault("path_cover_lower_bound", self._path_cover_seed_info.get("lower_bound"))
        self.solve_statistics.setdefault("path_cover_seed_path_count", len(self._path_cover_seed_info.get("seed_paths", [])))
        self.solve_statistics.setdefault("path_cover_seed_solved", self._path_cover_seed_info.get("solved"))

    def _log_single_component_failure(self):
        """Log timeouts and infeasibility explicitly so they are not conflated."""
        solve_status = None
        if isinstance(self.solve_statistics, dict):
            solve_status = self.solve_statistics.get("solve_status")

        witness_path_count = len(self._path_cover_seed_info.get("seed_paths", []))
        graph_name = self._get_graph_name(self.kwargs.get("G", self._original_graph))

        if solve_status == numpathsoptimization.NumPathsOptimization.timeout_status_name:
            utils.logger.warning(
                f"{__name__}: Graph '{graph_name}' timed out while solving the weighted discordance model; a structural path-cover witness with {witness_path_count} paths exists, so this is not being reported as an infeasible constraint set.",
            )
        elif solve_status == numpathsoptimization.NumPathsOptimization.infeasible_status_name:
            utils.logger.error(
                f"{__name__}: Graph '{graph_name}' is infeasible for the weighted discordance model. Structural witness paths available: {witness_path_count}.",
            )

    def _solve_trivial_single_node_graph(self, graph: nx.DiGraph) -> bool:
        """Solve the isolated single-node case directly without building a MILP."""
        trivial_solution = self._get_trivial_single_node_solution(graph)
        if trivial_solution is None:
            return False

        self._solution = trivial_solution
        self._component_objective_value = 0
        self.model = SimpleNamespace(
            k=1,
            get_objective_value=lambda: 0,
            is_valid_solution=lambda: True,
        )
        self.solve_statistics = {
            "solve_status": numpathsoptimization.NumPathsOptimization.solved_status_name,
            "solve_time": 0,
            "path_cover_lower_bound": 1,
            "path_cover_seed_path_count": 1,
            "path_cover_seed_solved": True,
            "solve_mode": "trivial_single_node",
        }
        self.set_solved()
        utils.logger.info(
            f"{__name__}: Solved isolated single-node graph via direct shortcut.",
        )
        return True

    def _get_graph_name(self, graph: nx.DiGraph) -> str:
        """Best-effort graph label used in component naming and logging."""
        graph_name = getattr(graph, "name", None)
        if not graph_name and hasattr(graph, "graph"):
            graph_name = graph.graph.get("name")
        if not graph_name:
            graph_name = getattr(graph, "id", None)
        return str(graph_name) if graph_name else "graph"

    def _set_component_graph_component_suffix(
        self,
        component_graph: nx.DiGraph,
        parent_graph: nx.DiGraph,
        component_index: int,
        total_components: int,
    ) -> str:
        """Attach a deterministic component suffix to graph name/id for logging clarity."""
        parent_name = self._get_graph_name(parent_graph)
        component_name = f"{parent_name}__component_{component_index}_of_{total_components}"
        component_graph.name = component_name
        if hasattr(component_graph, "graph"):
            component_graph.graph["name"] = component_name

        if hasattr(component_graph, "id"):
            try:
                component_graph.id = component_name
            except Exception:
                # Keep this best-effort and non-fatal for graph implementations with read-only id.
                pass

        return component_name

    def _map_component_subsequence_constraints(self, component_nodes):
        """Return component-local constraints and drop cross-component ones."""
        component_constraints = []
        for constraint in self._model_init_kwargs["subsequence_constraints"]:
            in_component = [node in component_nodes for node in constraint]
            if all(in_component):
                component_constraints.append(constraint)
            elif any(in_component):
                constraint_key = tuple(constraint)
                if constraint_key not in self._logged_cross_component_constraints:
                    utils.logger.critical(
                        f"{__name__}: Dropping subsequence constraint {constraint} because it spans multiple weakly connected components.",
                    )
                    self._logged_cross_component_constraints.add(constraint_key)
        return component_constraints

    def _validate_subsequence_constraint_reachability(self, graph: nx.DiGraph, constraints: list) -> bool:
        """Ensure each consecutive node pair in each constraint is reachable."""
        for constraint_index, constraint in enumerate(constraints or [], start=1):
            for node_index, (source, target) in enumerate(zip(constraint, constraint[1:]), start=1):
                if source not in graph:
                    utils.logger.critical(
                        f"{__name__}: Constraint #{constraint_index} infeasible: node '{source}' (position {node_index}) is not in graph.",
                    )
                    return False

                if target not in graph:
                    utils.logger.critical(
                        f"{__name__}: Constraint #{constraint_index} infeasible: node '{target}' (position {node_index + 1}) is not in graph.",
                    )
                    return False

                if not nx.has_path(graph, source, target):
                    utils.logger.critical(
                        f"{__name__}: Constraint #{constraint_index} infeasible: no path from '{source}' to '{target}' between positions {node_index}->{node_index + 1} in constraint {constraint}.",
                    )
                    return False

        return True

    def _build_component_model(self, component_graph: nx.DiGraph, remaining_time: float):
        """Construct a component-local model with filtered options and budget."""
        component_nodes = set(component_graph.nodes())
        component_subsequence_constraints = self._map_component_subsequence_constraints(component_nodes)
        component_additional_starts = [
            node
            for node in self._model_init_kwargs["additional_starts"]
            if node in component_nodes
        ]
        component_additional_ends = [
            node
            for node in self._model_init_kwargs["additional_ends"]
            if node in component_nodes
        ]

        utils.logger.info(
            f"{__name__}: Building component model for '{self._get_graph_name(component_graph)}' with {len(component_subsequence_constraints)} subsequence constraints, {len(component_additional_starts)} additional starts, {len(component_additional_ends)} additional ends, remaining_time={remaining_time:.3f}s.",
        )

        return MinPathsMinDiscordantNodes(
            G=component_graph,
            flow_attr=self._model_init_kwargs["flow_attr"],
            weight_type=self._model_init_kwargs["weight_type"],
            discordance_tolerance=self._model_init_kwargs["discordance_tolerance"],
            subsequence_constraints=component_subsequence_constraints,
            additional_starts=component_additional_starts,
            additional_ends=component_additional_ends,
            optimization_options=self._model_init_kwargs["optimization_options"],
            solver_options=self._model_init_kwargs["solver_options"],
            round_flow_values_to_int=self._model_init_kwargs["round_flow_values_to_int"],
            flow_values_divisor=self._model_init_kwargs["flow_values_divisor"],
            min_num_paths=self._model_init_kwargs["min_num_paths"],
            max_num_paths=self._model_init_kwargs["max_num_paths"],
            time_limit=remaining_time,
        )

    def _merge_component_solutions(self, solutions):
        """Merge per-component solution dictionaries into one global solution."""
        merged_solution = {}
        for solution in solutions:
            for key, value in solution.items():
                if key == "_weights_scaled_to_original":
                    continue
                if key not in merged_solution:
                    merged_solution[key] = deepcopy(value)
                elif isinstance(value, list) and isinstance(merged_solution[key], list):
                    merged_solution[key].extend(deepcopy(value))
                elif isinstance(value, dict) and isinstance(merged_solution[key], dict):
                    merged_solution[key].update(deepcopy(value))
                else:
                    merged_solution[key] = deepcopy(value)
        merged_solution["_weights_scaled_to_original"] = False
        return merged_solution

    def _get_trivial_zero_flow_component_solution(self, component_graph: nx.DiGraph):
        """Backward-compatible wrapper for the isolated single-node shortcut."""
        return self._get_trivial_single_node_solution(component_graph)

    def solve(self) -> bool:
        """
        Solve the model.

        For a single-component graph, delegates to ``NumPathsOptimization``.
        For multiple weakly connected components, solves components one by one,
        consuming a shared global time budget and summing objective values.
        """
        if self._constraint_reachability_infeasible:
            utils.logger.critical(
                f"{__name__}: Aborting solve because subsequence constraints are infeasible (reachability pre-check failed).",
            )
            self.solve_statistics = {
                "solve_status": numpathsoptimization.NumPathsOptimization.infeasible_status_name,
                "solve_time": 0,
            }
            self._is_solved = False
            return False

        if not self._is_componentized:
            graph = self.kwargs.get("G", self._original_graph)
            if self._solve_trivial_single_node_graph(graph):
                return True

            solved = super().solve()
            self._merge_path_cover_seed_info_into_statistics()
            if not solved:
                self._log_single_component_failure()
            return solved

        self.solve_time_start = time.perf_counter()
        self._component_models = []
        self._component_solutions = []
        self._component_objective_value = 0

        utils.logger.info(
            f"{__name__}: Starting multi-component solve for {len(self._component_graphs)} components with global time_limit={self.time_limit}.",
        )

        for component_index, component_graph in enumerate(self._component_graphs, start=1):
            component_name = self._get_graph_name(component_graph)
            remaining_time = self.time_limit - self.solve_time_elapsed
            if remaining_time <= 0:
                utils.logger.warning(
                    f"{__name__}: Time budget exhausted before component {component_index}/{len(self._component_graphs)} ('{component_name}').",
                )
                self.solve_statistics = {
                    "solve_status": numpathsoptimization.NumPathsOptimization.timeout_status_name,
                    "solve_time": self.solve_time_elapsed,
                }
                self._is_solved = False
                return False

            utils.logger.info(
                f"{__name__}: Solving component {component_index}/{len(self._component_graphs)} ('{component_name}') with remaining_time={remaining_time:.3f}s.",
            )

            trivial_solution = self._get_trivial_zero_flow_component_solution(component_graph)
            if trivial_solution is not None:
                utils.logger.info(
                    f"{__name__}: Component '{component_name}' solved via trivial isolated-node shortcut.",
                )
                self._component_solutions.append(trivial_solution)
                continue

            component_model = self._build_component_model(component_graph, remaining_time)
            component_model.solve()
            self._component_models.append(component_model)

            if not component_model.is_solved():
                component_status = None
                if isinstance(component_model.solve_statistics, dict):
                    component_status = component_model.solve_statistics.get("solve_status")
                if component_status == numpathsoptimization.NumPathsOptimization.timeout_status_name:
                    witness_count = 0
                    if hasattr(component_model, "_path_cover_seed_info"):
                        witness_count = len(component_model._path_cover_seed_info.get("seed_paths", []))
                    utils.logger.warning(
                        f"{__name__}: Component '{component_name}' timed out while solving the weighted discordance model. Structural path-cover witness paths: {witness_count}.",
                    )
                else:
                    utils.logger.error(
                        f"{__name__}: Component '{component_name}' failed with solve_status={component_status}.",
                    )
                self.solve_statistics = {
                    "solve_status": component_status or numpathsoptimization.NumPathsOptimization.infeasible_status_name,
                    "solve_time": self.solve_time_elapsed,
                    "failed_component_name": component_name,
                    "failed_component_index": component_index,
                    "failed_component_status": component_status,
                }
                self._is_solved = False
                return False

            component_solution = component_model.get_solution(remove_empty_paths=False)
            self._component_solutions.append(component_solution)
            self._component_objective_value += component_model.get_objective_value()
            utils.logger.info(
                f"{__name__}: Component '{component_name}' solved. Partial global objective={self._component_objective_value}.",
            )

        self._solution = self._merge_component_solutions(self._component_solutions)
        self.solve_statistics = {
            "solve_status": numpathsoptimization.NumPathsOptimization.solved_status_name,
            "solve_time": self.solve_time_elapsed,
        }
        utils.logger.info(
            f"{__name__}: Multi-component solve completed. Total objective={self._component_objective_value}, solve_time={self.solve_time_elapsed:.3f}s.",
        )
        self.set_solved()
        return True

    def get_solution(self, remove_empty_paths=True):
        """Return merged solution, optionally removing empty paths."""
        if not self._is_componentized:
            raw_solution = super().get_solution(remove_empty_paths=False)
            self._solution = self._postprocess_solution_for_original_graph(raw_solution)
            return self._remove_empty_sequences(self._solution) if remove_empty_paths else self._solution

        self.check_is_solved()
        if self._solution is None:
            self._solution = self._merge_component_solutions(self._component_solutions or [])

        self._solution = self._postprocess_solution_for_original_graph(self._solution)

        return self._remove_empty_sequences(self._solution) if remove_empty_paths else self._solution

    def get_objective_value(self):
        """Return discordant-node count for the postprocessed solution."""
        self.check_is_solved()
        solution = self.get_solution(remove_empty_paths=False)
        return sum(solution.get("discordant_nodes", {}).values())

    def is_valid_solution(self) -> bool:
        """Validate transformed solution against original graph flow values."""
        self.check_is_solved()
        solution = self.get_solution(remove_empty_paths=False)
        if solution is None:
            return False

        sequence_key = "paths" if "paths" in solution else "walks"
        sequences = solution.get(sequence_key, [])
        weights = solution.get("weights", [])
        if len(sequences) != len(weights):
            return False

        if self._is_componentized:
            return all(component_model.is_valid_solution() for component_model in self._component_models) and self._is_solution_discordance_consistent(solution)

        return self._is_solution_discordance_consistent(solution)

    def _postprocess_solution_for_original_graph(self, solution: dict):
        """Scale solution weights back and recompute discordance labels on original flows."""
        if solution is None:
            return solution

        if solution.get("_weights_scaled_to_original", False):
            return solution

        processed_solution = deepcopy(solution)
        weights = processed_solution.get("weights", [])
        processed_solution["weights"] = [weight * self._flow_values_divisor for weight in weights]
        processed_solution["discordant_nodes"] = self._compute_discordant_nodes_for_solution(processed_solution)
        processed_solution["_weights_scaled_to_original"] = True
        return processed_solution

    def _compute_discordant_nodes_for_solution(self, solution: dict) -> dict:
        """Compute discordance labels from solution sequences and original node flows."""
        sequence_key = "paths" if "paths" in solution else "walks"
        sequences = solution.get(sequence_key, [])
        weights = solution.get("weights", [])

        covered_weight_per_node = {node: 0 for node in self._original_graph.nodes()}
        for sequence, weight in zip(sequences, weights):
            for node in sequence:
                if node in covered_weight_per_node:
                    covered_weight_per_node[node] += weight

        discordant_nodes = {}
        flow_attr = self._model_init_kwargs["flow_attr"]
        for node, data in self._original_graph.nodes(data=True):
            if flow_attr not in data:
                continue
            flow_value = data[flow_attr]
            if not isinstance(flow_value, numbers.Real):
                continue

            interval_lb = (1 - self._model_init_kwargs["discordance_tolerance"]) * flow_value
            interval_ub = (1 + self._model_init_kwargs["discordance_tolerance"]) * flow_value
            node_value = covered_weight_per_node.get(node, 0)
            inside_interval = interval_lb - 0.001 <= node_value <= interval_ub + 0.001
            discordant_nodes[node] = 0 if inside_interval else 1

        return discordant_nodes

    def _is_solution_discordance_consistent(self, solution: dict, tolerance: float = 0.001) -> bool:
        """Check that discordance labels match interval checks on original flows."""
        expected_discordant_nodes = self._compute_discordant_nodes_for_solution(solution)
        reported_discordant_nodes = solution.get("discordant_nodes", {})

        for node, expected_value in expected_discordant_nodes.items():
            reported_value = reported_discordant_nodes.get(node)
            if reported_value is None:
                return False
            if int(round(reported_value)) != expected_value:
                return False

        objective_value = self.get_objective_value()
        expected_objective = sum(expected_discordant_nodes.values())
        if abs(objective_value - expected_objective) > tolerance * max(1, len(expected_discordant_nodes)):
            return False

        return True

    def get_lowerbound_k(self):
        """Return lower bound used for the ``k`` search."""
        if not self._is_componentized:
            return super().get_lowerbound_k()

        return sum(component_graph.number_of_nodes() > 0 for component_graph in self._component_graphs)