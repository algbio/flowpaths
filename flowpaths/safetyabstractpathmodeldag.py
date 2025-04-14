from flowpaths import abstractpathmodeldag
from flowpaths import minflowdecomp
from flowpaths import numpathsoptimization
from flowpaths.utils import solverwrapper as sw
from copy import deepcopy
import flowpaths.utils as utils
import time

class SafetyAbstractPathModelDAG():

    allowed_optimization_options = [
        "optimize_with_safe_paths",
        "optimize_with_safe_sequences",
        "optimize_with_safe_zero_edges",
        "optimize_with_subpath_constraints_as_safe_sequences",
        "optimize_with_flow_safe_paths",
    ]

    def __init__(
        self, 
        model_type: abstractpathmodeldag.AbstractPathModelDAG,
        time_limit: float = float('inf'),
        delta_in_objective_value: float = 0.0,
        **kwargs,
    ):
        """
        This class computes all the maximal safe paths of any model with a given number of paths, that inherits from `AbstractPathModelDAG`.

        A path is *safe* if it belongs to all solutions of the model with `k` paths, for a given `k`. 
        A path is *maximal safe* if it is not a proper subpath of any other safe path.
        The class uses a group testing approach to find the safe paths, in addition to setting suitable constraints on the model, from [https://doi.org/10.1093/bioinformatics/btad640](https://doi.org/10.1093/bioinformatics/btad640).

        Parameters
        ----------
        
        - `model_type: AbstractPathModelDAG`
        
            The type of the model to be used. It should be a subclass of `AbstractPathModelDAG`.

        - `time_limit: float`, optional
        
            The time limit for the solver, in seconds. Default is Infinity.

        - `delta_in_objective_value: float`, optional
            
            This parameter to be used for the safety check. Default is 0.0.
            That is, we can generalize safety and say that a path is *safe* if it belongs to all solutions of the model with `k` paths, 
            but with an objective value different from the original one by a factor of at most `delta_in_objective_value`. 

        - `**kwargs`
        
            Additional arguments to be passed to the model. Include the number `k` of paths, and all other that are required for the model whose safe paths you are computing.
        """
        self.model_type = model_type
        self.time_limit = time_limit
        self.delta_in_objective_value = delta_in_objective_value
        self.kwargs = kwargs

        if not issubclass(self.model_type, abstractpathmodeldag.AbstractPathModelDAG):
            utils.logger.error(f"{__name__}: The model_type parameter must be a subclass of AbstractPathModelDAG. You passed {self.model_type}.")
            raise TypeError(f"{__name__}: The model_type parameter must be a subclass of AbstractPathModelDAG. You passed {self.model_type}.")
        
        # Some hard-coded checks
        if issubclass(self.model_type, minflowdecomp.MinFlowDecomp) or issubclass(self.model_type, numpathsoptimization.NumPathsOptimization):
            utils.logger.error(f"{__name__}: The model_types MinFlowDecomp and NumPathsOptimization are not supported (you passed {self.model_type}). First find a feasible solution, and pass the k-version of the model, e.g. kFlowDecomp.")
            raise TypeError(f"{__name__}: The model_types MinFlowDecomp and NumPathsOptimization are not supported (you passed {self.model_type}). First find a feasible solution, and pass the k-version of the model, e.g. kFlowDecomp.")
        
        if 'k' not in self.kwargs:
            utils.logger.error(f"{__name__}: The model must have a parameter 'k' in kwargs. This is the number of paths.")
            raise ValueError("The model must have a parameter 'k' in kwargs. This is the number of paths.")
        
        if 'optimization_options' in self.kwargs:
            # Raise an error if some of the optimization options are not allowed
            for opt in self.kwargs["optimization_options"]:
                if opt not in SafetyAbstractPathModelDAG.allowed_optimization_options:
                    utils.logger.error(f"{__name__}: The optimization option {opt} is not allowed. Allowed options are {self.allowed_optimization_options}.")
                    raise ValueError(f"The optimization option {opt} is not allowed. Allowed options are {self.allowed_optimization_options}.")

        self.safe_paths = []
        self.__is_solved = False
        self.solve_time_start = None
        self.solve_statistics = {}

        utils.logger.debug(f"{__name__}: SafetyAbstractPathModelDAG initialized with model_type {self.model_type} and kwargs {self.kwargs}.")

    def solve(self):
        
        self.solve_time_start = time.perf_counter()

        # We make a copy of kwargs since the models may modify them
        kwargs_initial_deepcopy = deepcopy(self.kwargs)
        # We create the model and solve it once to get an initial solution
        initial_model: abstractpathmodeldag.AbstractPathModelDAG = self.model_type(**kwargs_initial_deepcopy)
        initial_model.solve()

        # Handling time limit. 
        # TODO: In the group testing method, this should be placed in the proper places.
        if self.__solve_time_elapsed > self.time_limit:
            self.solve_statistics = {
                "solve_status": sw.SolverWrapper.timelimit_status,
                "solve_time": self.__solve_time_elapsed,
            }
            return

        if not initial_model.is_solved():
            utils.logger.error(f"{__name__}: The model of type {self.model_type} with parameters {self.kwargs} cannot solved. We cannot compute the safe paths.")
            raise Exception(f"{__name__}: The model of type {self.model_type} with parameters {self.kwargs} cannot solved. We cannot compute the safe paths.")
        
        # We get the initial solution
        initial_paths = initial_model.get_solution()["paths"]
        k = len(initial_paths)
        utils.logger.info(f"{__name__}: The model of type {self.model_type} with parameters {self.kwargs} has {k} solution paths.")
        initial_objective_value = initial_model.get_objective_value()

        if k == 0:
            raise Exception(f"{__name__}: The model of type {self.model_type} with parameters {self.kwargs} has no solution paths. We cannot compute the safe paths.")

        # We apply the group testing approach to find the safe paths
        # Here is an example of testing whether the entire first solution path is safe
        ########### BEGIN ###########
        candidate_path = initial_paths[0]
        # Example of logging
        utils.logger.debug(f"{__name__}: Testing the candidate path {candidate_path}.")
        utils.logger.debug(f"{__name__}: The candidate path has edges {list(zip(candidate_path[:-1], candidate_path[1:]))}.")
        utils.logger.debug(f"{__name__}: The candidate path has {len(candidate_path)} nodes and {len(candidate_path) - 1} edges.")

        
        # We again take the original kwargs to create the model, since the model may modify them
        kwargs_tmp_deepcopy = deepcopy(self.kwargs)
        
        # Setting 'optimize_with_greedy: False' optimization that can be used by kFlowDecomp and messes up with the ILP solver creation
        optimization_options_tmp = kwargs_tmp_deepcopy.get("optimization_options", {})
        optimization_options_tmp["optimize_with_greedy"] = False
        kwargs_tmp_deepcopy["optimization_options"] = optimization_options_tmp
            
        tmp_model: abstractpathmodeldag.AbstractPathModelDAG = self.model_type(**kwargs_tmp_deepcopy)
        # We add the constraints to the model to enforce that not all edges of candidate_path are used in each path i
        for i in range(0,k):
            tmp_model.solver.add_constraint(
                tmp_model.solver.quicksum(
                    tmp_model.edge_vars[(u,v,i)] for (u,v) in zip(candidate_path[:-1], candidate_path[1:]))
                    <= len(candidate_path) - 2
                ,
                name=f"excluded_in_path_{i}"
            )
        tmp_model.solve()

        # Handling time limit. 
        # TODO: In the group testing method, this should be placed in the proper places.
        if self.__solve_time_elapsed > self.time_limit:
            self.solve_statistics = {
                "solve_status": SafetyAbstractPathModelDAG.timeout_status_name,
                "solve_time": self.__solve_time_elapsed,
            }
            return

        # TODO: In the group testing methods, `self.__is_solved = True` should be set only if 
        # we managed to check all possible paths for safety. 
        # The meaning of True is that we successfully checked all possible candidate paths for safety 
        # (within the given time_limit, with the model always solving or returning unfeasible, and not strange statuses)
        tmp_status = tmp_model.solver.get_model_status()
        is_safe = False
        if tmp_model.is_solved(): 
            # If the model is solved, the the path is afe iff there is a change in objective value
            self.__is_solved = True # See above TODO
            current_obj = tmp_model.get_objective_value()
            is_safe = abs(current_obj - initial_objective_value) / initial_objective_value > self.delta_in_objective_value
        elif tmp_status == 'kInfeasible': 
            # If the mode is infeasible, then the path is safe
            self.__is_solved = True # See above TODO
            is_safe = True
        else: 
            # If the model is not solved and not infeasible, then we cannot say anything about the path.
            # We set the is_solved to False, and we need to stop computing other safe paths.
            self.__is_solved = False # See above TODO

        if is_safe:
            self.safe_paths.append(candidate_path)

        self.solve_statistics = {
                "solve_time": self.__solve_time_elapsed,
            }
        ########### END ###########

    def is_solved(self):
        """
        Returns True if all possible safety checks have been performed, and the safe paths we can reporting as solution are all the maximal safe paths.
        """
        
        return self.__is_solved
    
    def check_is_solved(self):
        if not self.is_solved():
            utils.logger.error(f"{__name__}: Model not solved. If you want to solve it, call the `solve` method first. If you already ran the `solve` method, then the model is infeasible, or you need to increase parameter time_limit.")
            raise Exception(
                "Model not solved. If you want to solve it, call the `solve` method first. \
                  If you already ran the `solve` method, then the model is infeasible, or you need to increase parameter time_limit.")

    def get_solution(self):
        """
        Returns a list containing all the maximal safe paths. Each path is a list of nodes. 
        
        If the model is not solved, it raises an exception.
        """

        self.check_is_solved()

        return self.safe_paths
        
    @property
    def __solve_time_elapsed(self):
        """
        Returns the elapsed time since the start of the solve process.

        Returns
        -------
        - `float`
        
            The elapsed time in seconds.
        """
        return time.perf_counter() - self.solve_time_start if self.solve_time_start is not None else None
