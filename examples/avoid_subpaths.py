######################
# This example shows how to build a custom DAG path-finding model on top of
# AbstractPathModelDAG. The model finds exactly one path while forbidding a
# collection of subpaths from appearing completely in that path.
######################

import flowpaths as fp
import networkx as nx


class OnePathAvoidingSubpaths(fp.AbstractPathModelDAG):
    """Find exactly one DAG path while forbidding selected subpaths.

    The model builds a single source-to-sink path in the augmented `stDAG`
    and adds one linear constraint per forbidden subpath so that not all edges
    of that subpath can be selected simultaneously.
    """

    def __init__(
        self,
        G: nx.DiGraph,
        subpaths_to_avoid: list,
        additional_starts: list | None = None,
        additional_ends: list | None = None,
        solver_options: dict = {},
    ):
        """Initialize the one-path avoidance model.

        Parameters
        ----------
        G : nx.DiGraph
            Input DAG.
        subpaths_to_avoid : list
            List of forbidden subpaths, each given as a list of edges.
        additional_starts : list | None, optional
            Nodes that may serve as alternative path starts.
        additional_ends : list | None, optional
            Nodes that may serve as alternative path ends.
        solver_options : dict, optional
            Options forwarded to the solver wrapper.
        """

        self.G = fp.stDAG(
            G,
            additional_starts=additional_starts,
            additional_ends=additional_ends,
        )
        self.subpaths_to_avoid = subpaths_to_avoid or []
        self._check_valid_subpaths_to_avoid()
        self._solution = None

        super().__init__(
            self.G,
            k=1,
            solver_options=solver_options,
        )

        self.create_solver_and_paths()
        self._encode_subpaths_to_avoid()
        self._encode_objective()

    def _check_valid_subpaths_to_avoid(self):
        """Validate the forbidden subpaths against the augmented graph."""

        if not all(isinstance(subpath, list) for subpath in self.subpaths_to_avoid):
            raise ValueError("subpaths_to_avoid must be a list of lists of edges.")

        for subpath in self.subpaths_to_avoid:
            if len(subpath) == 0:
                raise ValueError("Each forbidden subpath must contain at least one edge.")
            if not all(isinstance(edge, tuple) and len(edge) == 2 for edge in subpath):
                raise ValueError("Each forbidden subpath must be a list of edges.")
            for edge in subpath:
                if not self.G.has_edge(edge[0], edge[1]):
                    raise ValueError(f"Forbidden subpath contains edge {edge}, which is not in the graph.")

    def _encode_subpaths_to_avoid(self):
        """Add one avoidance constraint for each forbidden subpath."""

        for j, subpath in enumerate(self.subpaths_to_avoid):
            self.solver.add_constraint(
                self.solver.quicksum(self.edge_vars[(u, v, 0)] for (u, v) in subpath)
                <= len(subpath) - 1,
                name=f"avoid_subpath_j={j}",
            )

    def _encode_objective(self):
        """Set a dummy objective so the model has an explicit objective value."""

        self.solver.set_objective(
            self.solver.quicksum([]),
            sense="minimize",
        )

    def get_solution(self):
        """Return the decoded path solution and cache it."""

        if self._solution is not None:
            return self._solution

        self.check_is_solved()

        paths = self.get_solution_paths()
        self._solution = {
            "path": paths[0],
        }
        return self._solution

    def is_valid_solution(self):
        """Check that no forbidden subpath appears completely in the solution."""

        self.check_is_solved()

        path = self.get_solution()["path"]
        path_edges = {
            (path[i], path[i + 1])
            for i in range(len(path) - 1)
        }

        for subpath in self.subpaths_to_avoid:
            if sum(edge in path_edges for edge in subpath) == len(subpath):
                return False

        return True

    def get_objective_value(self):
        """Return the solver objective value for the current solution."""

        self.check_is_solved()
        return self.solver.get_objective_value()

    def has_no_path_avoiding(self):
        """Return whether infeasibility proves that no avoiding path exists.

        Returns
        -------
        bool
            `False` if the model is solved, `True` if the solver terminated with
            infeasibility, and otherwise raises an exception.
        """

        if self.is_solved():
            return False

        model_status = self.solver.get_model_status()
        if model_status == fp.utils.solverwrapper.SolverWrapper.infeasible_status:
            return True

        raise Exception(
            "Model is not solved and solver did not prove infeasibility. "
            f"Current status: {model_status}."
        )

    def get_lowerbound_k(self):
        """Return the lower bound on the number of paths, which is always one."""

        return 1


def process_solution(model: OnePathAvoidingSubpaths):
    """Print a compact summary of the model result."""

    if model.is_solved():
        solution = model.get_solution()
        print("Solution:", solution)
        print("Objective value:", model.get_objective_value())
        print("Valid solution:", model.is_valid_solution())
        print("Solve statistics:", model.solve_statistics)
    elif model.has_no_path_avoiding():
        print("No path avoiding the forbidden subpaths exists.")
    else:
        print("Model could not be solved.")


def main():
    """Run one feasible and one infeasible avoidance example."""

    solver_options = {
        "external_solver": "highs",  # we can try also "gurobi" at some point
    }

    graph = nx.DiGraph()
    graph.graph["id"] = "avoid_subpaths_example"
    graph.add_edge("0", "a")
    graph.add_edge("a", "b")
    graph.add_edge("a", "c")
    graph.add_edge("b", "d")
    graph.add_edge("c", "d")
    graph.add_edge("d", "1")

    feasible_model = OnePathAvoidingSubpaths(
        graph,
        subpaths_to_avoid=[[('a', 'b'), ('b', 'd')]],
        additional_starts=["a"],
        additional_ends=["d"],
        solver_options=solver_options,
    )
    feasible_model.solve()
    process_solution(feasible_model)

    infeasible_model = OnePathAvoidingSubpaths(
        graph,
        subpaths_to_avoid=[
            [('a', 'b'), ('b', 'd')],
            [('a', 'c'), ('c', 'd')],
        ],
        additional_starts=["a"],
        additional_ends=["d"],
        solver_options=solver_options,
    )
    infeasible_model.solve()
    process_solution(infeasible_model)


if __name__ == "__main__":
    main()