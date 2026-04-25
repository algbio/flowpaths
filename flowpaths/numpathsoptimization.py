import time
import copy
import flowpaths.abstractpathmodeldag as pathmodel
import flowpaths.abstractwalkmodeldigraph as walkmodel
import flowpaths.utils as utils

class NumPathsOptimization(pathmodel.AbstractPathModelDAG, walkmodel.AbstractWalkModelDiGraph):
    # We inherit both abstract bases so this optimizer can wrap either DAG path
    # models or cyclic walk models while exposing a unified API.
    
    # Storing some status names
    solved_status_name = "solved"
    timeout_status_name = "timeout"
    unbounded_status_name = "unbounded"
    infeasible_status_name = "infeasible"

    def __init__(
        self,
        model_type,
        stop_on_first_feasible: bool = None,
        stop_on_delta_abs: float = None,
        stop_on_delta_rel: float = None,
        min_num_paths: int = 1,
        max_num_paths: int = 2**64,
        time_limit: float = float("inf"),
        **kwargs,
    ):
        """
        This is a generic class to find the "best" number of path/walks for optimization
        problems implemented using `AbstractPathModelDAG` or
        `AbstractWalkModelDiGraph`, and parameterized by the number of
        paths/walks considered.
        The class iterates over a range of `k` values, creating and
        solving a model for each path/walk count until one of the stopping conditions is met.
        
        Parameters
        ----------

        - `model_type`

            The type of the model used for optimization.

        - `stop_on_first_feasible : bool`, optional

            If True, the optimization process stops as soon as a feasible solution is found.
            Default is None.

        - `stop_on_delta_abs` : float, optional

            The threshold for change (in absolute value) in objective value between iterations to determine stopping the optimization.
            Default is `None`.

        - `stop_on_delta_rel` : float, optional

            The relative threshold for change (in absolute value) in objective value between iterations to determine stopping the optimization. 
            This is computed as the difference in objective value between iterations divided by the objective value of the previous iteration.
            Default is `None`.

            !!! warning "Pass at least one stopping criterion"
                At least one of the stopping criterion must be set: `stop_on_first_feasible`, `stop_on_delta_abs`, `stop_on_delta_rel`.

        - `min_num_paths : int`, optional

            Minimum number of paths/walks to be considered in the optimization.
            Default is 1. The class will also call `get_lowerbound_k()` on the
            `model_type` and the provided arguments to get a better lower bound.

        - `max_num_paths : int`, optional
            
            Maximum number of paths/walks to be computed.
            Default is `2**64`.

        - `time_limit : float`, optional
            
            Time limit (in seconds) for the optimization process.
            Default is `float("inf")`.

        - `**kwargs`

            The keyword arguments to be passed to the model. 

            !!! warning "Note"
                
                Do not pass the parameter `k` here, as it will be handled by the internal optimization process.

        Raises
        ------

        - `ValueError`

            If none of the stopping criteria (`stop_on_first_feasible`, `stop_on_delta_abs`, or
            `stop_on_delta_rel`) is provided (i.e., all are `None`).
        """
       
        self.model_type = model_type
        self.stop_on_first_feasible = stop_on_first_feasible
        self.stop_on_delta_abs = stop_on_delta_abs
        self.stop_on_delta_rel = stop_on_delta_rel
        self.min_num_paths = min_num_paths
        self.max_num_paths = max_num_paths
        self.time_limit = time_limit
        self.solve_time_start = None
        self.kwargs = kwargs

        # We allow only one of the stopping criteria to be set
        if (stop_on_first_feasible is None) and (stop_on_delta_abs is None) and (stop_on_delta_rel is None):
            raise ValueError(
                "At least one of the stopping criteria must be set: stop_on_first_feasible, stop_on_delta_abs, stop_on_delta_rel"
            )
        
        if 'k' in self.kwargs:
            raise ValueError("Do not pass the parameter `k` in the keyword arguments of NumPathsOptimization. This will be iterated over internally to find the best number of paths/walks according to the stopping criteria.")
        
        self.lowerbound_k = None
        self._solution = None
        self.solve_statistics = None
        self._is_solved = False

        utils.logger.info(f"{__name__}: created NumPathsOptimization with model_type = {model_type}")

    def _get_unfiltered_solution_from_model(self, model):
        """
        Retrieve solution from wrapped model without removing empty paths/walks,
        regardless of whether the model exposes `remove_empty_paths` or
        `remove_empty_walks`.
        """

        try:
            return model.get_solution(remove_empty_paths=False)
        except TypeError:
            pass

        try:
            return model.get_solution(remove_empty_walks=False)
        except TypeError:
            pass

        return model.get_solution()

    def solve(self) -> bool:
        """
        Attempts to solve the optimization problem by iterating over a range of `k` values, creating and
        solving a model for each count until one of the stopping conditions is met.
        The method iterates from the maximum between the minimum allowed paths and a lower bound (via
        `get_lowerbound_k()` of the model) to the maximum allowed paths. For each iteration:

        - Creates a model instance with the current number of paths/walks (`k`).
        - Solves the model, and checks if it has been successfully solved.
        - Applies various stopping criteria including:

            - `stop_on_first_feasible`: stops at the first feasible solution.
            - `stop_on_delta_abs`: stops if the absolute change in the objective value between iterations is
                less than or equal to the `stop_on_delta_abs` value.
            - `stop_on_delta_rel`: stops if the relative change in the objective value between iterations is
                less than or equal to the `stop_on_delta_rel` value.

        - Stops if the elapsed time exceeds the designated time limit.

        Upon termination, the method sets the overall solve status:

        - If no feasible solution was found, the status is marked as infeasible.
        - If the process did not exceed the time limit but no other stopping condition was met, the status
            is marked as unbounded.
        - If any of the stopping criteria (feasible or delta conditions) were satisfied, the status is set as solved.

        If a valid solution is found, it stores the solution, updates solve statistics and the model,
        marks the problem as solved, and returns `True`. Otherwise, it returns `False`.
        
        Returns
        -------

        - `bool`
        
            `True` if an optimal solution is found and the problem is marked as solved, `False` otherwise.
            
        """
        
        self.solve_time_start = time.perf_counter()
        previous_solution_objective_value = None
        solve_status = None
        found_feasible = False
        previous_feasible_model = None
        selected_model = None

        for k in range(max(self.min_num_paths,self.get_lowerbound_k()), self.max_num_paths+1):
            # Create the model
            utils.logger.info(f"{__name__}: model id = {id(self)}, iteration with k = {k}")
            model = self.model_type(**self.kwargs, k=k)
            model.solve()
            if model.is_solved():
                found_feasible = True
                current_solution_objective_value = model.get_objective_value()
                utils.logger.info(f"{__name__}: model id = {id(self)}, iteration with k = {k}, current_solution_objective_value = {current_solution_objective_value}")
                if self.stop_on_first_feasible:
                    solve_status = NumPathsOptimization.solved_status_name
                    selected_model = model
                    break
                if previous_solution_objective_value is not None:
                    if self.stop_on_delta_abs is not None:
                        if abs(previous_solution_objective_value - current_solution_objective_value) <= self.stop_on_delta_abs:
                            solve_status = NumPathsOptimization.solved_status_name
                            selected_model = previous_feasible_model
                            break
                    if self.stop_on_delta_rel is not None:
                        abs_delta = abs(previous_solution_objective_value - current_solution_objective_value)
                        if previous_solution_objective_value == 0:
                            if abs_delta == 0:
                                solve_status = NumPathsOptimization.solved_status_name
                                selected_model = previous_feasible_model
                                break
                        elif abs_delta / abs(previous_solution_objective_value) <= self.stop_on_delta_rel:
                            solve_status = NumPathsOptimization.solved_status_name
                            selected_model = previous_feasible_model
                            break

                previous_feasible_model = model
                previous_solution_objective_value = current_solution_objective_value
            else:
                utils.logger.info(f"{__name__}: model id = {id(self)}, iteration with k = {k}, model is not solved")
            if self.solve_time_elapsed > self.time_limit:
                solve_status = NumPathsOptimization.timeout_status_name
                utils.logger.info(f"{__name__}: model id = {id(self)}, iteration with k = {k}, time out")
                break
            
        if solve_status != NumPathsOptimization.timeout_status_name:
            if not found_feasible:
                solve_status = NumPathsOptimization.infeasible_status_name
            elif solve_status is None:
                solve_status = NumPathsOptimization.unbounded_status_name
        
        self.solve_statistics = {
                "solve_status": solve_status,
                "solve_time": self.solve_time_elapsed,
            }

        if solve_status == NumPathsOptimization.solved_status_name:
            if selected_model is None:
                selected_model = model
            # Store the unfiltered solution when the wrapped model supports it,
            # so callers can decide whether to remove empty paths/walks.
            self._solution = self._get_unfiltered_solution_from_model(selected_model)
            self.set_solved()
            self.solve_statistics.update(selected_model.solve_statistics)
            self.model = selected_model
            return True
            
        return False

    def _remove_empty_sequences(self, solution):
        """
        Removes empty paths/walks from a solution dictionary.

        A path/walk is considered non-empty if it has at least two nodes.
        Lists aligned with the sequence list (for example, "weights" and
        "slacks")
        are filtered consistently.
        """

        if solution is None:
            return solution

        sequence_key = None
        if "paths" in solution:
            sequence_key = "paths"
        elif "walks" in solution:
            sequence_key = "walks"

        if sequence_key is None:
            return solution

        solution_copy = copy.deepcopy(solution)
        keep_indices = [
            idx
            for idx, seq in enumerate(solution_copy[sequence_key])
            if len(seq) > 1
        ]

        solution_copy[sequence_key] = [solution_copy[sequence_key][idx] for idx in keep_indices]

        for key, value in solution_copy.items():
            if key == sequence_key:
                continue
            if isinstance(value, list) and len(value) == len(solution[sequence_key]):
                solution_copy[key] = [value[idx] for idx in keep_indices]

        return solution_copy

    def get_solution(self, remove_empty_paths=False):
        """
        Retrieves the solution from the wrapped model.

        Parameters
        ----------
        - `remove_empty_paths: bool`, optional

            If True, remove empty paths/walks (fewer than two nodes)
            and filter aligned list fields consistently. Default is False.

        Returns
        -------

        - `solution: dict`
        
            The solution obtained from the wrapped model.

        Raises
        -------

        - `exception` If model is not solved.
        """

        self.check_is_solved()
        if self._solution is not None:
            return self._remove_empty_sequences(self._solution) if remove_empty_paths else self._solution

        self._solution = self._get_unfiltered_solution_from_model(self.model)

        return self._remove_empty_sequences(self._solution) if remove_empty_paths else self._solution
    
    def get_objective_value(self):
        """
        Returns the objective value of the model, if it is solved. Otherwise, raises an exception.
        """

        self.check_is_solved()

        return self.model.get_objective_value()

    def is_valid_solution(self) -> bool:
        """
        Checks if the solution is valid, by calling the `is_valid_solution()` method of the model.
        """
        return self.model.is_valid_solution()
    
    def get_lowerbound_k(self):
        
        # Returns the lower bound for number of paths/walks using wrapped model's `get_lowerbound_k()`.

        if self.lowerbound_k != None:
            return self.lowerbound_k
        
        tmp_model = self.model_type(**self.kwargs, k = 1)
        self.lowerbound_k = tmp_model.get_lowerbound_k()

        return self.lowerbound_k
    
    @property
    def solve_time_elapsed(self):
        """
        Returns the elapsed time since the start of the solve process.

        Returns
        -------
        - `float`
        
            The elapsed time in seconds.
        """
        return time.perf_counter() - self.solve_time_start if self.solve_time_start is not None else 0
            

        


