import copy
import time

import networkx as nx

import flowpaths.abstractwalkmodeldigraph as walkmodel
import flowpaths.nodeexpandeddigraph as nedg
import flowpaths.stdigraph as stdigraph
import flowpaths.utils as utils


class kMinDiscordantNodesCycles(walkmodel.AbstractWalkModelDiGraph):
    def __init__(
        self,
        G: nx.DiGraph,
        flow_attr: str,
        k: int,
        weight_type: type = float,
        discordance_tolerance: float = 0.1,
        subset_constraints: list = [],
        additional_starts: list = [],
        additional_ends: list = [],
        optimization_options: dict = None,
        solver_options: dict = {},
    ):
        """
        This class implements the k-MinDiscordantNodes problem on general directed graphs,
        possibly with cycles. It looks for a decomposition of a weighted graph into
        $k$ weighted walks, minimizing the number of *discordant* nodes. A node is
        *discordant* if the sum of the walk-weights traversing it lies outside the interval

            [(1 - discordance_tolerance) * observed_flow,
             (1 + discordance_tolerance) * observed_flow].

        Additionally, it is required that every node and every edge appear in some
        solution walk.

        Parameters
        ----------
        - `G: nx.DiGraph`

            The input directed graph, as [networkx DiGraph](https://networkx.org/documentation/stable/reference/classes/digraph.html),
            which can have cycles.

        - `k: int`

            The number of walks to decompose in.

        - `weight_type: int | float`, optional

            The type of the weights (`int` or `float`). Default is `float`.

        - `subset_constraints: list`, optional

            List of subset constraints. Default is an empty list.

            In this node-weighted model, constraints are expected on original graph nodes,
            i.e. each constraint is a list/set of node names that must be covered by some
            solution walk (order-independent, set semantics).

            These are converted to expanded-graph edges via `NodeExpandedDiGraph`
            (node `v` becomes expanded edge `(v.0, v.1)`) before encoding.

        - `additional_starts: list`, optional

            List of additional start nodes of the walks. Default is an empty list.

        - `additional_ends: list`, optional

            List of additional end nodes of the walks. Default is an empty list.

        - `optimization_options: dict`, optional

            Dictionary with optimization options. Default is `None`.

        - `solver_options: dict`, optional

            Dictionary with solver options. Default is `{}`.

        Raises
        ------
        - `ValueError`

            - If `weight_type` is not `int` or `float`.
            - If the flow attribute `flow_attr` is not specified in some edge.
            - If the graph contains edges with negative flow values.
        """

        utils.logger.info(f"{__name__}: START initialized with graph id = {utils.fpid(G)}, k = {k}")

        if G.number_of_nodes() == 0:
            utils.logger.error(f"{__name__}: The input graph G has no nodes. Please provide a graph with at least one node.")
            raise ValueError("The input graph G has no nodes. Please provide a graph with at least one node.")

        self.G_internal = nedg.NodeExpandedDiGraph(G, node_flow_attr=flow_attr)
        subset_constraints_expanded = self.G_internal.get_expanded_subpath_constraints(subset_constraints)
        additional_starts_internal = self.G_internal.get_expanded_additional_starts(additional_starts)
        additional_ends_internal = self.G_internal.get_expanded_additional_ends(additional_ends)

        edges_to_ignore_internal = self.G_internal.edges_to_ignore

        self.G = stdigraph.stDiGraph(
            self.G_internal,
            additional_starts=additional_starts_internal,
            additional_ends=additional_ends_internal,
        )
        self.subset_constraints = subset_constraints_expanded
        self.edges_to_ignore = self.G.source_sink_edges.union(edges_to_ignore_internal)
        # Nodes/edges are required to be covered, so all expanded-graph edges are safe to trust.
        self.trusted_edges_for_safety = self.G_internal.edges()

        if weight_type not in [int, float]:
            utils.logger.error(f"{__name__}: weight_type must be either int or float, not {weight_type}")
            raise ValueError(f"weight_type must be either int or float, not {weight_type}")
        self.weight_type = weight_type

        self.k = k
        self.original_k = k
        self.optimization_options = optimization_options or {}
        self.discordance_tolerance = discordance_tolerance

        self.flow_attr = flow_attr
        self.w_max = self.k * self.weight_type(
            self.G.get_max_flow_value_and_check_non_negative_flow(
                flow_attr=self.flow_attr,
                edges_to_ignore=self.edges_to_ignore,
            )
        )

        self.pi_vars = {}
        self.path_weights_vars = {}
        self.discordant_edge_vars = {}
        self.discordant_low_vars = {}
        self.discordant_high_vars = {}

        self.path_weights_sol = None
        self.discordant_edges_sol = None
        self.discordant_nodes_sol = None
        self._solution = None
        self._lowerbound_k = None

        self.solve_statistics = {}
        self.solve_time_start = time.perf_counter()

        self.optimization_options["trusted_edges_for_safety"] = set(self.trusted_edges_for_safety)

        super().__init__(
            G=self.G,
            k=self.k,
            max_edge_repetition_dict=self.G.compute_edge_max_reachable_value(flow_attr=self.flow_attr),
            subset_constraints=self.subset_constraints,
            subset_constraints_coverage=1.0,
            optimization_options=self.optimization_options,
            solver_options=solver_options,
            solve_statistics=self.solve_statistics,
        )

        # Called from the walk-model parent class.
        self.create_solver_and_walks()

        # Called from this class to encode objective and extra constraints.
        self._encode_discordance_decomposition()
        self._encode_cover_every_node_edge_constraints()
        self._encode_objective()

        utils.logger.info(f"{__name__}: END initialized with graph id = {utils.fpid(G)}, k = {self.k}")

    def _encode_discordance_decomposition(self):

        self.pi_vars = self.solver.add_variables(
            self.edge_indexes,
            name_prefix="pi",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )
        self.path_weights_vars = self.solver.add_variables(
            self.path_indexes,
            name_prefix="weights",
            lb=0,
            ub=self.w_max,
            var_type="integer" if self.weight_type == int else "continuous",
        )

        # Expanded-graph edges (originating from the nodes of the original graph) that carry observed node-flow and are evaluated for discordance;
        # Excludes helper source-sink edges, and the edges of the original graph that are ignored for discordance evaluation (e.g. because this model does not use their flow values).
        self.edge_indexes_basic = [(u, v) for (u, v) in self.G.edges() if (u, v) not in self.edges_to_ignore]

        self.discordant_edge_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="z",
            lb=0,
            ub=1,
            var_type="integer",
        )
        self.discordant_low_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="zlow",
            lb=0,
            ub=1,
            var_type="integer",
        )
        self.discordant_high_vars = self.solver.add_variables(
            self.edge_indexes_basic,
            name_prefix="zhigh",
            lb=0,
            ub=1,
            var_type="integer",
        )

        for u, v, data in self.G.edges(data=True):
            if (u, v) in self.edges_to_ignore:
                continue

            f_u_v = data[self.flow_attr]
            interval_lb = (1 - self.discordance_tolerance) * f_u_v
            interval_ub = (1 + self.discordance_tolerance) * f_u_v
            total_pi_u_v = self.solver.quicksum(self.pi_vars[(u, v, i)] for i in range(self.k))

            # Safe bound for sum_i pi[(u,v,i)] across k walks.
            sum_pi_ub = self.k * self.w_max
            big_m = sum_pi_ub + abs(interval_lb) + abs(interval_ub)
            strict_eps = 1 if self.weight_type == int else 1e-6

            for i in range(self.k):
                if (u, v, i) in self.edges_set_to_zero:
                    self.solver.add_constraint(
                        self.pi_vars[(u, v, i)] == 0,
                        name=f"i={i}_u={u}_v={v}_10b",
                    )
                elif (u, v, i) in self.edges_set_to_one:
                    self.solver.add_constraint(
                        self.pi_vars[(u, v, i)] == self.path_weights_vars[(i)],
                        name=f"i={i}_u={u}_v={v}_10b",
                    )
                else:
                    self.solver.add_integer_continuous_product_constraint(
                        integer_var=self.edge_vars[(u, v, i)],
                        continuous_var=self.path_weights_vars[(i)],
                        product_var=self.pi_vars[(u, v, i)],
                        lb=0,
                        ub=self.w_max,
                        name=f"10_u={u}_v={v}_i={i}",
                    )

            self.solver.add_constraint(
                total_pi_u_v >= interval_lb - big_m * self.discordant_low_vars[(u, v)],
                name=f"disc_lb_u={u}_v={v}",
            )
            self.solver.add_constraint(
                total_pi_u_v <= interval_ub + big_m * self.discordant_high_vars[(u, v)],
                name=f"disc_ub_u={u}_v={v}",
            )
            self.solver.add_constraint(
                total_pi_u_v <= interval_lb - strict_eps + big_m * (1 - self.discordant_low_vars[(u, v)]),
                name=f"disc_force_low_u={u}_v={v}",
            )
            self.solver.add_constraint(
                total_pi_u_v >= interval_ub + strict_eps - big_m * (1 - self.discordant_high_vars[(u, v)]),
                name=f"disc_force_high_u={u}_v={v}",
            )
            self.solver.add_constraint(
                self.discordant_low_vars[(u, v)] + self.discordant_high_vars[(u, v)] <= 1,
                name=f"disc_side_exclusive_u={u}_v={v}",
            )
            self.solver.add_constraint(
                self.discordant_edge_vars[(u, v)]
                == self.discordant_low_vars[(u, v)] + self.discordant_high_vars[(u, v)],
                name=f"disc_z_link_u={u}_v={v}",
            )

    def _encode_cover_every_node_edge_constraints(self):
        """
        Adds constraints to ensure every expanded-graph edge (except source/sink helper edges)
        is covered by at least one walk.
        """
        for u, v in self.G.edges():
            if (u, v) in self.G.source_sink_edges:
                continue

            self.solver.add_constraint(
                self.solver.quicksum(
                    self.edge_vars[(u, v, i)] for i in range(self.k)
                )
                >= 1,
                name=f"cover_edge_u={u}_v={v}",
            )

    def _encode_objective(self):

        self.solver.set_objective(
            self.solver.quicksum(
                self.discordant_edge_vars[(u, v)] for (u, v) in self.edge_indexes_basic
            ),
            sense="minimize",
        )

    def _remove_empty_walks(self, solution):
        """
        Removes empty walks from the solution. Empty walks are those with 0 or 1 nodes.
        """
        solution_copy = copy.deepcopy(solution)
        non_empty_walks = []
        non_empty_weights = []
        for walk, weight in zip(solution["walks"], solution["weights"]):
            if len(walk) > 1:
                non_empty_walks.append(walk)
                non_empty_weights.append(weight)

        solution_copy["walks"] = non_empty_walks
        solution_copy["weights"] = non_empty_weights
        return solution_copy

    def get_solution(self, remove_empty_walks=True):
        """
        Retrieves the solution for the discordance minimization problem.
        """

        if self._solution is not None:
            return self._remove_empty_walks(self._solution) if remove_empty_walks else self._solution

        self.check_is_solved()

        weights_sol_dict = self.solver.get_values(self.path_weights_vars)

        self.path_weights_sol = [
            round(weights_sol_dict[i]) if self.weight_type == int else float(weights_sol_dict[i])
            for i in range(self.k)
        ]

        self.discordant_edges_sol = self.solver.get_values(self.discordant_edge_vars)
        for (u, v) in self.edge_indexes_basic:
            self.discordant_edges_sol[(u, v)] = int(round(self.discordant_edges_sol[(u, v)]))

        self.discordant_nodes_sol = {}
        for expanded_edge, z_value in self.discordant_edges_sol.items():
            condensed_node = self.G_internal.get_condensed_node(expanded_edge)
            if condensed_node is not None:
                self.discordant_nodes_sol[condensed_node] = z_value
            else:
                utils.logger.error(
                    f"{__name__}: Error: expanded edge {expanded_edge} does not correspond to any condensed node. This should not happen."
                )

        self._solution = {
            "_walks_internal": self.get_solution_walks(),
            "walks": self.G_internal.get_condensed_paths(self.get_solution_walks()),
            "weights": self.path_weights_sol,
            "discordant_nodes": self.discordant_nodes_sol,
        }

        return self._remove_empty_walks(self._solution) if remove_empty_walks else self._solution

    def is_valid_solution(self, tolerance=0.001):
        """
        Checks if the solution is valid by comparing walk-induced values and discordance labels.
        """

        if self._solution is None:
            self.get_solution()

        solution_walks = self._solution.get("_walks_internal", self._solution["walks"])
        solution_weights = self._solution["weights"]

        if self.discordant_edges_sol is None:
            self.discordant_edges_sol = self.solver.get_values(self.discordant_edge_vars)
            for (u, v) in self.edge_indexes_basic:
                self.discordant_edges_sol[(u, v)] = int(round(self.discordant_edges_sol[(u, v)]))

        solution_discordance_expanded = self.discordant_edges_sol
        solution_walks_of_edges = [
            [(walk[i], walk[i + 1]) for i in range(len(walk) - 1)]
            for walk in solution_walks
        ]

        weight_from_walks = {(u, v): 0 for (u, v) in self.G.edges()}
        for weight, walk in zip(solution_weights, solution_walks_of_edges):
            for e in walk:
                weight_from_walks[e] += weight

        for u, v, data in self.G.edges(data=True):
            if self.flow_attr in data and (u, v) not in self.edges_to_ignore:
                interval_lb = (1 - self.discordance_tolerance) * data[self.flow_attr]
                interval_ub = (1 + self.discordance_tolerance) * data[self.flow_attr]
                inside_interval = interval_lb - tolerance <= weight_from_walks[(u, v)] <= interval_ub + tolerance
                edge_z = int(round(solution_discordance_expanded[(u, v)]))

                if edge_z == 0 and not inside_interval:
                    utils.logger.debug(
                        f"{__name__}: Invalid solution for expanded-graph node item ({u}, {v}): z=0 but "
                        f"weight from walks {weight_from_walks[(u, v)]} is outside "
                        f"[{interval_lb}, {interval_ub}]"
                    )
                    return False
                if edge_z == 1 and inside_interval:
                    utils.logger.debug(
                        f"{__name__}: Invalid solution for expanded-graph node item ({u}, {v}): z=1 but "
                        f"weight from walks {weight_from_walks[(u, v)]} is inside "
                        f"[{interval_lb}, {interval_ub}]"
                    )
                    return False

        if abs(self.get_objective_value() - self.solver.get_objective_value()) > tolerance * self.original_k:
            utils.logger.debug(
                f"{__name__}: Invalid solution: objective value {self.get_objective_value()} != solver objective value {self.solver.get_objective_value()} (tolerance: {tolerance * self.original_k})"
            )
            return False

        return True

    def get_objective_value(self):

        self.check_is_solved()

        if self.discordant_edges_sol is None:
            self.get_solution()

        return sum(self.discordant_edges_sol.values())

    def get_lowerbound_k(self):

        if self._lowerbound_k is not None:
            return self._lowerbound_k

        self._lowerbound_k = self.G.get_width(edges_to_ignore=self.edges_to_ignore)

        return self._lowerbound_k