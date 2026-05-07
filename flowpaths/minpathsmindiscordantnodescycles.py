import networkx as nx
from copy import deepcopy
import time
import numbers

import flowpaths.kmindiscordantnodescycles as kmindiscordantnodescycles
import flowpaths.minpathcovercycles as minpathcovercycles
import flowpaths.nodeexpandeddigraph as nedg
import flowpaths.numpathsoptimization as numpathsoptimization
import flowpaths.utils as utils


class MinPathsMinDiscordantNodesCycles(numpathsoptimization.NumPathsOptimization):
    """
    Minimize the number of walks for k-MinDiscordantNodes on cyclic graphs.

    The class wraps :class:`NumPathsOptimization` with:
    - ``model_type`` fixed to ``kMinDiscordantNodesCycles``
    - ``stop_on_delta_abs`` fixed to ``0``

    This means the search over ``k`` stops at the first plateau, i.e. when the
    objective no longer improves in absolute value.

    Multi-component behavior
    ------------------------
    If ``G`` has multiple weakly connected components, one component-local
    optimizer is solved per component and their solutions are merged.
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
        Build a MinPathsMinDiscordantNodesCycles optimizer.

        Parameters
        ----------
        G : nx.DiGraph
            Input graph.
        flow_attr : str
            Node/edge attribute name used by the wrapped discordance model.
        weight_type : type, default=float
            Type for walk weights (typically ``int`` or ``float``).
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
            ``MinPathCoverCycles`` on a node-expanded graph (per component when
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
                model_type=kmindiscordantnodescycles.kMinDiscordantNodesCycles,
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
            # Compute min_num_paths using MinPathCoverCycles with node-expanded graph.
            G_expanded = deepcopy(G)
            node_flow_attr = str(id(G_expanded)) + "_flow_attr"
            for node in G_expanded.nodes():
                G_expanded.nodes[node][node_flow_attr] = 0  # dummy value

            ne_graph = nedg.NodeExpandedDiGraph(G_expanded, node_flow_attr=node_flow_attr)

            expanded_subset_constraints = []
            if subsequence_constraints:
                for constraint in subsequence_constraints:
                    expanded_constraint = [ne_graph.get_expanded_edge(node) for node in constraint]
                    expanded_subset_constraints.append(expanded_constraint)

            min_path_cover_model = minpathcovercycles.MinPathCoverCycles(
                G=ne_graph,
                cover_type="edge",
                subset_constraints=expanded_subset_constraints,
                elements_to_ignore=ne_graph.edges_to_ignore,
                additional_starts=additional_starts or [],
                additional_ends=additional_ends or [],
                optimization_options=optimization_options or {},
                solver_options=solver_options or {},
            )
            min_path_cover_model.solve()
            min_num_paths_lb = min_path_cover_model.get_objective_value()
        else:
            min_num_paths_lb = min_num_paths
        
        super().__init__(
            model_type=kmindiscordantnodescycles.kMinDiscordantNodesCycles,
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
            optimization_options=optimization_options,
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

        return MinPathsMinDiscordantNodesCycles(
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

    def solve(self) -> bool:
        """
        Solve the model.

        For a single-component graph, delegates to ``NumPathsOptimization``.
        For multiple weakly connected components, solves components one by one,
        consuming a shared global time budget and summing objective values.
        """
        if not self._is_componentized:
            return super().solve()

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

            component_model = self._build_component_model(component_graph, remaining_time)
            component_model.solve()
            self._component_models.append(component_model)

            if not component_model.is_solved():
                utils.logger.error(
                    f"{__name__}: Component '{component_name}' failed to solve.",
                )
                component_status = None
                if isinstance(component_model.solve_statistics, dict):
                    component_status = component_model.solve_statistics.get("solve_status")
                self.solve_statistics = {
                    "solve_status": component_status or numpathsoptimization.NumPathsOptimization.infeasible_status_name,
                    "solve_time": self.solve_time_elapsed,
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
        """Return merged solution, optionally removing empty walks."""
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

        sequence_key = "walks" if "walks" in solution else "paths"
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
        sequence_key = "walks" if "walks" in solution else "paths"
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