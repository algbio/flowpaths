import flowpaths.utils.solverwrapper as sw
import time

class MinSetCover():
    def __init__(
        self,
        universe: list,
        subsets: list,
        subset_weights: list = None,
        solver_options: dict = {},
        ):
        """
        This class solves the minimum set cover problem. Given a universe `universe` and a list of subsets `subsets`,
        the goal is to find the minimum-weight list of subsets `set_cover` such that: 
        
        - every element in `universe` is in at least one subset in `set_cover`.
        - the sum of the weights of the subsets in `set_cover` is minimized.

        Parameters
        ----------

        - `universe: list`

            The universe of elements that must be covered.

        - `subsets: list`

            A list of subsets that can be used to cover the universe.

        - `subset_weights: list`

            The weight of each subset, as a list in the same order that the subsets appear in the list `subsets`. 
            If not provided, each subset is assumed to have a weight of 1.

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).
        """
        
        self.universe = universe
        self.subsets = subsets
        self.subset_weights = subset_weights
        self.set_cover = []
        self.set_cover_indices = []
        self.set_cover_weights = []
        self.solver_options = solver_options

        self._is_solved = None
        self._solution = None

        self._encode_set_cover()
        
    def _encode_set_cover(self):
        """
        This function encodes the set cover problem as an integer linear program.
        """
        self.solver = sw.SolverWrapper(**self.solver_options)

        self.subset_indexes = [(i)   for i in range(len(self.subsets))]

        self.subset_vars = self.solver.add_variables(
            self.subset_indexes, 
            name_prefix="subset",
            lb=0, 
            ub=1,
            var_type="integer"
        )

        # Every element of the universe must be in at least one subset
        for element in self.universe:            
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.subset_vars[i]
                    for i in range(len(self.subsets)) if element in self.subsets[i]
                )
                >= 1,
                name=f"total",
            )

        # Objective function
        self.solver.set_objective(
            self.solver.quicksum(
                self.subset_weights[i] * self.subset_vars[i]
                for i in range(len(self.subsets))
            )
        )
        
    def solve(self) -> bool:
        """
        Solves the minimum set cover problem. 

        Returns
        -------
        - bool
            
            `True` if the model was solved, `False` otherwise.
        """
        start_time = time.perf_counter()

        self.solver.optimize()
        if self.solver.get_model_status() == "kOptimal":
            subset_cover_sol = self.solver.get_values(self.subset_vars)
            self._solution = [i for i in range(len(self.subsets)) if subset_cover_sol[i] == 1]
            self._is_solved = True
            self.solve_statistics = {
                "solve_time": time.perf_counter() - start_time,
                "num_elements": len(self._solution),
                "status": self.solver.get_model_status(),
            }
            return True
        else:
            self.solve_statistics = {
                "solve_time": time.perf_counter() - start_time,
                "status": self.solver.get_model_status(),
            }
            return False

    def is_solved(self):
        """
        Returns `True` if the model was solved, `False` otherwise.
        """
        if self._is_solved is None:
            self.solver.logger.error(f"{__name__}: Model not yet solved. If you want to solve it, call the `solve` method first.")
            raise Exception("Model not yet solved. If you want to solve it, call the `solve` method first.")
        
        return self._is_solved
    
    def check_is_solved(self):
        if not self.is_solved():
            self.solver.logger.error(f"{__name__}: Model not solved. If you want to solve it, call the `solve` method first.")
            raise Exception(
                "Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit."
            )

    def get_solution(self, as_subsets: bool = False):
        """
        Returns the solution to the minimum generating set problem, if the model was solved. 

        Parameters
        ----------
        - `as_subsets: bool`
            
            If `True`, returns the subsets themselves. If `False`, returns the indices of the subsets in the list `subsets`.
        
        !!! warning "Warning"
            Call the `solve` method first.
        """
        if self._solution is not None:
            if not as_subsets:
                return self._solution
            else:
                return [self.subsets[i] for i in self._solution]
        
        self.check_is_solved() 