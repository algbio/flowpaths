import flowpaths as fp
import networkx as nx
import time


SOLVER_OPTIONS = {"external_solver": "highs"}


class _FakeSolver:
    def __init__(self, status):
        self._status = status

    def get_model_status(self):
        return self._status


class _FakeModelForInfeasibleAfterFeasible:
    def __init__(self, k, **kwargs):
        self.k = k
        self.solve_statistics = {}
        self._statuses = {
            1: (True, 10.0, "kOptimal"),
            2: (False, None, "kInfeasible"),
            3: (True, 10.0, "kOptimal"),
        }
        solved, objective, status = self._statuses.get(k, (False, None, "kInfeasible"))
        self._is_solved = solved
        self._objective = objective
        self.solver = _FakeSolver(status)

    def solve(self):
        return self._is_solved

    def is_solved(self):
        return self._is_solved

    def get_objective_value(self):
        return self._objective

    def get_solution(self, **kwargs):
        return {"paths": [["s", "t"]], "weights": [1]}

    def get_lowerbound_k(self):
        return 1


class _FakeModelFirstInfeasibleThenFeasible:
    def __init__(self, k, **kwargs):
        self.k = k
        self.solve_statistics = {}
        self._statuses = {
            1: (False, None, "kInfeasible"),
            2: (True, 10.0, "kOptimal"),
        }
        solved, objective, status = self._statuses.get(k, (False, None, "kInfeasible"))
        self._is_solved = solved
        self._objective = objective
        self.solver = _FakeSolver(status)

    def solve(self):
        return self._is_solved

    def is_solved(self):
        return self._is_solved

    def get_objective_value(self):
        return self._objective

    def get_solution(self, **kwargs):
        return {"paths": [["s", "t"]], "weights": [1]}

    def get_lowerbound_k(self):
        return 1


class _FakeModelTracksPerIterationTimeLimit:
    seen_solver_time_limits = []

    def __init__(self, k, solver_options=None, **kwargs):
        self.k = k
        self.solve_statistics = {}
        self._is_solved = False
        self._objective = None
        self.solver = _FakeSolver("kInfeasible")

        current_limit = None
        if isinstance(solver_options, dict):
            current_limit = solver_options.get("time_limit")
        self.__class__.seen_solver_time_limits.append(current_limit)

    def solve(self):
        # Consume noticeable wall time so the global budget shrinks across k.
        time.sleep(0.03)
        return False

    def is_solved(self):
        return self._is_solved

    def get_objective_value(self):
        return self._objective

    def get_solution(self, **kwargs):
        return {"paths": [["s", "t"]], "weights": [1]}

    def get_lowerbound_k(self):
        return 1


class _FakeModelReportsSolverTimeout:
    def __init__(self, k, **kwargs):
        self.k = k
        self.solve_statistics = {}
        self._is_solved = False
        self._objective = None
        self.solver = _FakeSolver("kTimeLimit")

    def solve(self):
        return False

    def is_solved(self):
        return self._is_solved

    def get_objective_value(self):
        return self._objective

    def get_solution(self, **kwargs):
        return {"paths": [["s", "t"]], "weights": [1]}

    def get_lowerbound_k(self):
        return 1


class _FakeModelTimeoutWithIncumbent:
    def __init__(self, k, **kwargs):
        self.k = k
        self.solve_statistics = {}
        self._is_solved = False
        self._has_incumbent_solution = True
        self._objective = 3.0
        self.solver = _FakeSolver("kTimeLimit")

    def solve(self):
        return False

    def is_solved(self):
        return self._is_solved

    def has_incumbent_solution(self):
        return self._has_incumbent_solution

    def get_incumbent_solution_paths(self):
        return [["s", "a", "t"]]

    def get_incumbent_objective_value(self):
        return self._objective

    def get_objective_value(self):
        return self._objective

    def get_solution(self, **kwargs):
        return {"paths": [["s", "a", "t"]], "weights": [1]}

    def get_lowerbound_k(self):
        return 1


def test_num_paths_optimization_delta_stops_on_infeasible_by_default():
    model = fp.NumPathsOptimization(
        model_type=_FakeModelForInfeasibleAfterFeasible,
        stop_on_delta_abs=0,
        min_num_paths=1,
        max_num_paths=3,
    )

    solved = model.solve()

    assert solved is False
    assert model.is_solved() is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.infeasible_status_name


def test_num_paths_optimization_delta_stops_on_first_infeasible_by_default():
    model = fp.NumPathsOptimization(
        model_type=_FakeModelFirstInfeasibleThenFeasible,
        stop_on_delta_abs=0,
        min_num_paths=1,
        max_num_paths=2,
    )

    solved = model.solve()

    assert solved is False
    assert model.is_solved() is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.infeasible_status_name


def test_num_paths_optimization_delta_can_ignore_infeasible_and_continue():
    model = fp.NumPathsOptimization(
        model_type=_FakeModelForInfeasibleAfterFeasible,
        stop_on_delta_abs=0,
        stop_on_infeasible_on_delta=False,
        min_num_paths=1,
        max_num_paths=3,
    )

    solved = model.solve()

    assert solved is True
    assert model.is_solved()
    # k=2 is infeasible and ignored; first delta stop is reached again at k=3 and keeps previous feasible model.
    assert model.model.k == 1


def test_num_paths_optimization_supports_cyclic_walk_models():
    graph = nx.DiGraph()
    graph.add_edge("s", "a", flow=5)
    graph.add_edge("a", "b", flow=5)
    graph.add_edge("b", "a", flow=1)
    graph.add_edge("b", "t", flow=4)

    model = fp.NumPathsOptimization(
        model_type=fp.kLeastAbsErrorsCycles,
        stop_on_first_feasible=True,
        min_num_paths=1,
        max_num_paths=2,
        G=graph,
        flow_attr="flow",
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )

    model.solve()

    assert model.is_solved()
    solution = model.get_solution(remove_empty_paths=True)
    assert "walks" in solution
    assert "weights" in solution


def test_num_paths_optimization_remove_empty_paths_filters_walk_solutions():
    graph = nx.DiGraph()
    graph.add_edge("s", "t", flow=1)

    model = fp.NumPathsOptimization(
        model_type=fp.kLeastAbsErrorsCycles,
        stop_on_first_feasible=True,
        min_num_paths=1,
        max_num_paths=1,
        G=graph,
        flow_attr="flow",
        weight_type=float,
        solver_options=SOLVER_OPTIONS,
    )

    model._solution = {
        "walks": [["s"], ["s", "t"]],
        "weights": [3.0, 7.0],
        "edge_errors": [1.0, 2.0],
    }
    model.set_solved()

    filtered = model.get_solution(remove_empty_paths=True)
    unfiltered = model.get_solution(remove_empty_paths=False)

    assert filtered["walks"] == [["s", "t"]]
    assert filtered["weights"] == [7.0]
    assert filtered["edge_errors"] == [2.0]
    assert unfiltered["walks"] == [["s"], ["s", "t"]]


def test_num_paths_optimization_applies_global_time_budget_across_k():
    _FakeModelTracksPerIterationTimeLimit.seen_solver_time_limits = []

    model = fp.NumPathsOptimization(
        model_type=_FakeModelTracksPerIterationTimeLimit,
        stop_on_first_feasible=True,
        min_num_paths=1,
        max_num_paths=3,
        time_limit=0.05,
        solver_options={},
    )

    solved = model.solve()

    assert solved is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.timeout_status_name
    finite_limits = [
        value
        for value in _FakeModelTracksPerIterationTimeLimit.seen_solver_time_limits
        if value is not None
    ]
    assert len(finite_limits) >= 2
    first_limit = finite_limits[0]
    second_limit = finite_limits[1]
    assert second_limit < first_limit


def test_num_paths_optimization_stops_immediately_on_solver_timeout_status():
    model = fp.NumPathsOptimization(
        model_type=_FakeModelReportsSolverTimeout,
        stop_on_first_feasible=True,
        min_num_paths=1,
        max_num_paths=3,
        time_limit=100.0,
    )

    solved = model.solve()

    assert solved is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.timeout_status_name


def test_num_paths_optimization_stores_incumbent_on_solver_timeout():
    model = fp.NumPathsOptimization(
        model_type=_FakeModelTimeoutWithIncumbent,
        stop_on_delta_abs=0,
        min_num_paths=1,
        max_num_paths=3,
        time_limit=100.0,
    )

    solved = model.solve()

    assert solved is False
    assert model.is_solved() is False
    assert model.solve_statistics["solve_status"] == fp.NumPathsOptimization.timeout_status_name
    assert model.has_incumbent_solution() is True
    assert model.get_incumbent_solution(remove_empty_paths=True)["paths"] == [["s", "a", "t"]]
