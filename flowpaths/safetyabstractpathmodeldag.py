from flowpaths import abstractpathmodeldag
from flowpaths import minflowdecomp
from flowpaths import numpathsoptimization
from flowpaths.utils import solverwrapper as sw
from copy import deepcopy
import flowpaths.utils as utils
import time

class SafetyAbstractPathModelDAG():
    """
    A class computing the safe paths of any model that inherits from AbstractPathModelDAG.
    """

    def __init__(
        self, 
        model_type: abstractpathmodeldag.AbstractPathModelDAG,
        time_limit: float = float("inf"),
        **kwargs,
    ):
        """
        Initialize the SafetyAbstractPathModelDAG with the given arguments.

        Parameters
        ----------
        
        - `model_type: AbstractPathModelDAG`
        
            The type of the model to be used. It should be a subclass of AbstractPathModelDAG.

        - `time_limit: float`
        
            The time limit for the solver, in seconds. Default is infinity.

        - `**kwargs`
        
            Additional arguments to be passed to the model. Include all that are required for the model whose safe paths you are computing.
        """
        self.model_type = model_type
        self.time_limit = time_limit
        self.kwargs = kwargs

        
        if not issubclass(self.model_type, abstractpathmodeldag.AbstractPathModelDAG):
            utils.logger.error(f"{__name__}: The model_type parameter must be a subclass of AbstractPathModelDAG. You passed {self.model_type}.")
            raise TypeError(f"{__name__}: The model_type parameter must be a subclass of AbstractPathModelDAG. You passed {self.model_type}.")
        
        # Some hard-coded checks
        if issubclass(self.model_type, minflowdecomp.MinFlowDecomp) or issubclass(self.model_type, numpathsoptimization.NumPathsOptimization):
            utils.logger.error(f"{__name__}: The model_types MinFlowDecomp and NumPathsOptimization are not supported (you passed {self.model_type}). First find a feasible solution, and pass the k-version of the model, e.g. kFlowDecomp.")
            raise TypeError(f"{__name__}: The model_types MinFlowDecomp and NumPathsOptimization are not supported (you passed {self.model_type}). First find a feasible solution, and pass the k-version of the model, e.g. kFlowDecomp.")

        self.safe_paths = []
        self.__is_solved = False
        self.solve_time_start = None
        self.solve_statistics = {}

        utils.logger.debug(f"{__name__}: SafetyAbstractPathModelDAG initialized with model_type {self.model_type} and kwargs {self.kwargs}.")

    def solve(self):
        
        self.solve_time_start = time.perf_counter()

        # We make a copy of the kwargs since the models may modify them
        kwargs_initial_deepcopy = deepcopy(self.kwargs)
        # We create the model and solve it once to get an initial solution
        initial_model: abstractpathmodeldag.AbstractPathModelDAG = self.model_type(**kwargs_initial_deepcopy)
        initial_model.solve()

        # Handling time limit
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
        initial_solution = initial_model.get_solution()
        initial_paths = initial_solution["paths"]
        k = len(initial_paths)

        if k == 0:
            raise Exception(f"{__name__}: The model of type {self.model_type} with parameters {self.kwargs} has no solution paths. We cannot compute the safe paths.")

        # We apply the group testing approach to find the safe paths
        # Here is an example of testing whether the entire first solution path is safe
        ########### BEGIN ###########
        candidate_path = initial_paths[0]
        utils.logger.info(f"{__name__}: Testing the candidate path {candidate_path}.")
        utils.logger.info(f"{__name__}: The candidate path has edges {list(zip(candidate_path[:-1], candidate_path[1:]))}.")
        utils.logger.info(f"{__name__}: The candidate path has {len(candidate_path)} nodes and {len(candidate_path) - 1} edges.")

        
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

        # Handling time limit. In the group testing method, this should be placed in the proper place
        if self.__solve_time_elapsed > self.time_limit:
            self.solve_statistics = {
                "solve_status": SafetyAbstractPathModelDAG.timeout_status_name,
                "solve_time": self.__solve_time_elapsed,
            }
            return

        is_safe = False
        if tmp_model.is_solved():
            self.__is_solved = True
            utils.logger.debug(f"{__name__}: The objective value of tmp_model is {tmp_model.get_objective_value()}.")
            if tmp_model.get_objective_value() > k:
                is_safe = True
        elif tmp_model.solver.get_model_status() == 'kInfeasible':
            is_safe = True
            self.__is_solved = True
        elif tmp_model.solver.get_model_status() not in ['kOptimal', 'kInfeasible']:
            utils.logger.debug(f"{__name__}: The model has status {tmp_model.solver.get_model_status()}, thus we report it as unsolved.")
            # TODO: if the status is not optimal, we cannot say anything about the safety of the path, so we mark the instance as unsolved
            self.__is_solved = False

        if is_safe:
            utils.logger.debug(f"{__name__}: The candidate path {candidate_path} is safe.")
            self.safe_paths.append(candidate_path)
        
        self.solve_statistics = {
                "solve_status": tmp_model.solver.get_model_status(),
                "solve_time": self.__solve_time_elapsed,
            }
        ########### END ###########

    def is_solved(self):
        return self.__is_solved
    
    def check_is_solved(self):
        if not self.is_solved():
            utils.logger.error(f"{__name__}: Model not solved. If you want to solve it, call the `solve` method first. If you already ran the `solve` method, then the model is infeasible, or you need to increase parameter time_limit.")
            raise Exception(
                "Model not solved. If you want to solve it, call the `solve` method first. \
                  If you already ran the `solve` method, then the model is infeasible, or you need to increase parameter time_limit.")

    def get_solution(self):
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


            



