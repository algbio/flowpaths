import time
import flowpaths.abstractpathmodeldag as pathmodel

class NumPathsOptimization(pathmodel.AbstractPathModelDAG): # Note that we inherit from AbstractPathModelDAG to be able to use this class to also compute safe paths, 
    
    # Storing some status names
    solved_status_name = "solved"
    timeout_status_name = "timeout"
    unbounded_status_name = "unbounded"
    infeasible_status_name = "infeasible"

    def __init__(
        self,
        model_type: pathmodel.AbstractPathModelDAG,
        stop_on_first_feasible: bool = None,
        stop_on_delta_abs: float = None,
        stop_on_delta_rel: float = None,
        min_num_paths: int = 1,
        max_num_paths: int = 2**64,
        time_limit: float = float("inf"),
        **kwargs,
    ):
        """
        This is a generic class to find the "best" number of paths optimization problems implemented using `AbstractPathModelDAG`,
        and which are parameterized by the number of paths to be considered.
        The class iterates over a range of path numbers `k`, creating and  
        solving a model for each path number until one of the stopping conditions is met.
        
        Parameters
        ----------

        - `model_type : AbstractPathModelDAG`

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

            Minimum number of paths to be considered in the optimization.
            Default is 1. The class will also call `get_lowerbound_k()` on the `model_type` and the provided arguments to get a better lower bound for the number of paths.

        - `max_num_paths : int`, optional
            
            Maximum number of paths to be computed.
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
        self.kwargs = kwargs

        # We allow only one of the stopping criteria to be set
        if (stop_on_first_feasible is None) and (stop_on_delta_abs is None) and (stop_on_delta_rel is None):
            raise ValueError(
                "At least one of the stopping criteria must be set: stop_on_first_feasible, stop_on_delta_abs, stop_on_delta_rel"
            )
        
        if 'k' in self.kwargs:
            raise ValueError("Do not pass the parameter `k` in the keyword arguments of NumPathsOptimization. This will be iterated over internally to find the best number of paths accoring to the stopping criteria.")
        
        self.lowerbound_k = None
        self.__solution = None
        self.solve_statistics = None

    def solve(self) -> bool:
        """
        Attempts to solve the optimization problem by iterating over a range of path counts, creating and
        solving a model for each count until one of the stopping conditions is met.
        The method iterates from the maximum between the minimum allowed paths and a lower bound (via
        `get_lowerbound_k()` of the model) to the maximum allowed paths. For each iteration:

        - Creates a model instance with the current number of paths (`k`).
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
        
        start_time = time.time()
        previous_solution_objective_value = None
        solve_status = None
        found_feasible = False

        for k in range(max(self.min_num_paths,self.get_lowerbound_k()), self.max_num_paths+1):
            # Create the model
            model = self.model_type(**self.kwargs, k=k)
            model.solve()
            if model.is_solved():
                found_feasible = True
                if self.stop_on_first_feasible:
                    solve_status = NumPathsOptimization.solved_status_name
                    break
                if self.stop_on_delta_abs:
                    if previous_solution_objective_value is None:
                        previous_solution_objective_value = model.get_objective_value()
                    else:
                        if abs(previous_solution_objective_value - model.get_objective_value()) <= self.stop_on_delta_abs:
                            solve_status = NumPathsOptimization.solved_status_name
                            break
                if self.stop_on_delta_rel:
                    if previous_solution_objective_value is None:
                        previous_solution_objective_value = model.get_objective_value()
                    else:
                        if abs(previous_solution_objective_value - model.get_objective_value()) / previous_solution_objective_value <= self.stop_on_delta_rel:
                            solve_status = NumPathsOptimization.solved_status_name
                            break
            if time.time() - start_time > self.time_limit:
                solve_status = NumPathsOptimization.timeout_status_name
                break
            
        if solve_status != NumPathsOptimization.timeout_status_name:
            if not found_feasible:
                solve_status = NumPathsOptimization.infeasible_status_name
            elif solve_status is None:
                solve_status = NumPathsOptimization.unbounded_status_name
        
        self.solve_statistics = {
                "solve_status": solve_status,
                "solve_time": time.time() - start_time,
            }

        if solve_status == NumPathsOptimization.solved_status_name:
            self.__solution = model.get_solution()
            self.set_solved()
            self.solve_statistics.update(model.solve_statistics)
            self.model = model
            return True
            
        return False

    def get_solution(self):
        """
        Retrieves the solution for the flow decomposition problem.

        Returns
        -------

        - `solution: dict`
        
            The solution obtained from the model

        Raises
        -------

        - `exception` If model is not solved.
        """

        self.check_is_solved()
        return self.__solution
    
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
        
        # Returns the lowerbound for the number of paths, by calling the `get_lowerbound_k()` method of the model.

        if self.lowerbound_k != None:
            return self.lowerbound_k
        
        tmp_model = self.model_type(**self.kwargs, k=1)
        self.lowerbound_k = tmp_model.get_lowerbound_k()

        return self.lowerbound_k
            

        


