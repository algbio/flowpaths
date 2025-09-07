import flowpaths.utils.solverwrapper as sw
import flowpaths.utils as utils
import time

class MinGenSet():
    def __init__(
            self, 
            numbers: list,
            total: int | float,
            weight_type: int | float = float,
            max_multiplicity: int = 1,
            lowerbound: int = 1,
            partition_constraints: list = None,
            remove_complement_values: bool = True,
            remove_sums_of_two: bool = False,
            solver_options: dict = {}
            ):
        """
        This class solves the minimum generating set problem. Given a list of numbers `a` and a total value `total`, 
        the goal is to find the smallest list of numbers `generating_set` such that:
        
        - the sum of the elements in `generating_set` equals `total`, and
        - every element in `a` can be expressed as the sum of some elements in `generating_set`.

        This class solves a more general problem, in which we are also given `max_multiplicity`, 
        the maximum number of times each element in `generating_set` can be used to represent elements in `a`.

        Parameters
        ----------

        - `a` : list

            A list of numbers.

        - `total` : int | float

            The total value that the sum of the elements in the generating set should equal.
            
        - `weight_type` : type

            The type of the numbers in `generating_set`. Default is `float`. The other option is `int`.

        - `max_multiplicity` : int

            The maximum number of times each element in the generating set can be used to represent elements in `a`. Default is 1.

        - `lowerbound` : int

            The minimum number of elements in the generating set. Default is 1.

        - `partition_constraints` : list

            A list of lists, where each inner list is made up of numbers, such that the sum of the numbers in each inner list is equal to `total`.
            That is, each inner list is a number partition of `total`.
            These constraints are imposed as:
            - each number in an inner list must be obtained by summing up a subset of numbers in the generating set, and
            - each number in the generating set must be used exactly once to obtain the numbers in the inner list.

            You cannot set this if `max_multiplicity > 1`.

        - `remove_complement_values` : bool

            If `True`, if `a` contains both `x` and `total - x`, it keeps only the smallest of them. Default is `True`.
            This is always correct to do. If say the generating set is $g_1, g_2, g_3, g_4$, with $g_1 + g_2 + g_3 + g_4 = total$.
            If $x = g_1 + g_3$, then $total - x = g_2 + g_4$. So $total - x$ is expressed as a sum of values in the generating set.
        
        - `remove_sums_of_two` : bool

            If `True`, it removes elements from `a` that are the sum of two other elements in `a`. Default is `False`.
            This is not always correct to do, as it might lead to a smaller generating set. For example, suppose the generating set is $g_1, g_2, g_3, g_4$, with $g_1$ different from $g_4$ 
            Suppose $x = g_1 + g_2$, $y = g_1 + g_3$ and $x+y \in a$. Then $x+y$ is expressed as $2 g_1 + g_2 + g_3$, 
            thus it needs repeating $g_1$ **twice**. So $x+y$ cannot be expressed as a sum of elements in the generating set. 

            You cannot set this to `True` if `max_multiplicity > 1`.
            
            !!! note "Note"
                Setting this to `True` always gives a generating set smaller or of the same size (i.e., not larger) as setting it to `False`. 
                Thus, the size of the former generating set can be used as a lower bound for the size of the latter generating set.

        - `solver_options : dict`, optional
            
            Dictionary with the solver options. Default is `{}`. See [solver options documentation](solver-options-optimizations.md).
        """
        
        self.numbers = list(numbers) # Make a copy of the list
        utils.logger.debug(f"{__name__}: Initial numbers: {self.numbers}")
        self.initial_numbers = numbers
        self.total = total
        utils.logger.debug(f"{__name__}: Generating set sum = {self.total}")
        self.weight_type = weight_type
        self.max_multiplicity = max_multiplicity
        if self.max_multiplicity < 1:
            utils.logger.error(f"{__name__}: `max_multiplicity` must be at least 1.")
            raise ValueError("`max_multiplicity` must be at least 1.")
        self.lowerbound = lowerbound
        self.partition_constraints = partition_constraints
        if self.partition_constraints is not None and self.max_multiplicity > 1:
            utils.logger.error(f"{__name__}: `partition_constraints` is set, but `max_multiplicity > 1`. This is not allowed.")
            raise ValueError("`partition_constraints` is not allowed when `max_multiplicity > 1`.")

        self._is_solved = False
        self._solution = None
        self.solver = None
        self.solve_statistics = {}
        self.solver_options = solver_options

        if self.weight_type not in [int, float]:
            utils.logger.error(f"{__name__}: weight_type must be either `int` or `float`.")
            raise ValueError("weight_type must be either `int` or `float`.")
        
        if self.partition_constraints is not None:
            if not all(isinstance(constraint, list) for constraint in self.partition_constraints):
                utils.logger.error(f"{__name__}: partition_constraints must be a list of lists.")
                raise ValueError("partition_constraints must be a list of lists.")        
            if not all(sum(constraint) == self.total for constraint in self.partition_constraints):
                utils.logger.error(f"{__name__}: The sum of the numbers inside each subset constraint must equal the total value.")
                raise ValueError("The sum of the numbers inside each subset constraint must equal the total value.")

        if False and remove_sums_of_two:
            if self.max_multiplicity > 1:
                utils.logger.error(f"{__name__}: `remove_sums_of_two` is set to True, but `max_multiplicity > 1`. This is not allowed.")
                raise ValueError("`remove_sums_of_two` is not allowed when `max_multiplicity > 1`.")

            elements_to_remove = set()
            for val1 in self.numbers:
                for val2 in self.numbers:
                    if val1 + val2 in self.numbers:
                        elements_to_remove.add(val1 + val2)

            self.numbers = list(set(self.numbers) - elements_to_remove)

        if remove_complement_values:
            elements_to_remove = set()
            for val in self.numbers:
                if total - val in self.numbers and total - val > val:
                    elements_to_remove.add(total - val)
                if val == total or val == 0:
                    elements_to_remove.add(val)

            self.numbers = list(set(self.numbers) - elements_to_remove)

        utils.logger.debug(f"{__name__}: Numbers after removing values: {self.numbers}")

    def _create_solver(self, k):

        self.solver = sw.SolverWrapper(**self.solver_options)

        self.genset_indexes = [(i)   for i in range(k)]
        self.x_indexes = [(i,j) for i in range(k) for j in range(len(self.numbers))]

        self.genset_vars = self.solver.add_variables(
            self.genset_indexes, 
            name_prefix="gen_set", 
            lb=0, 
            ub=self.total,
            var_type="integer" if self.weight_type == int else "continuous"
        )

        # x_vars[(i, j)] is the number of times the i-th element of the generating set is used to express the j-th number in a
        if self.max_multiplicity == 1:            
            # If max_multiplicity is 1, x_vars[(i, j)] is binary
            self.x_vars = self.solver.add_variables(
                self.x_indexes, 
                name_prefix="x", 
                lb=0, 
                ub=1, 
                var_type="integer"
            )
        else:
            # Otherwise, it is an arbitrary integer
            self.x_vars = self.solver.add_variables(
                self.x_indexes, 
                name_prefix="x", 
                lb=0, 
                ub=self.max_multiplicity, 
                var_type="integer"
            )

        self.pi_vars = self.solver.add_variables(
            self.x_indexes, 
            name_prefix="pi", 
            lb=0, 
            ub=self.total, 
            var_type="integer" if self.weight_type == int else "continuous"
        )

        # Constraints

        # Sum of elements in the generating set equals total
        self.solver.add_constraint(
            self.solver.quicksum(
                self.genset_vars[i]
                for i in self.genset_indexes
            )
            == self.total,
            name=f"total",
        )

        for j in range(len(self.numbers)):              

            # pi_vars[(i, j)] = x_vars[(i, j)] * genset_vars[i]
            if self.max_multiplicity == 1:
                # If max_multiplicity is 1, we can use binary constraints
                for i in range(k):
                    self.solver.add_binary_continuous_product_constraint(
                        binary_var=self.x_vars[(i, j)],
                        continuous_var=self.genset_vars[(i)],
                        product_var=self.pi_vars[(i, j)],
                        lb=0,
                        ub=self.total,
                        name=f"pi_i={i}_j={j}",
                    )
            else:  
                for i in range(k):
                    self.solver.add_integer_continuous_product_constraint(
                            integer_var=self.x_vars[(i, j)],
                            continuous_var=self.genset_vars[(i)],
                            product_var=self.pi_vars[(i, j)],
                            lb=0,
                            ub=self.total,
                            name=f"pi_i={i}_j={j}",
                        )

            # Sum of pi_vars[(i, j)] for all i is self.numbers[j]
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.pi_vars[(i, j)]
                    for i in self.genset_indexes
                )
                == self.numbers[j],
                name=f"sum_pi_j={j}",
            )

        # Encoding the symmetry breaking constraints
        self._encode_symmetry_breaking(k)

        # Encoding the subset constraints
        if self.partition_constraints is not None:
            self._encode_partition_constraints(k)

    def _encode_symmetry_breaking(self, k):
        for i in range(k - 2):
            self.solver.add_constraint(
                self.genset_vars[i] <= self.genset_vars[i+1],
                name=f"b_{i}_leq_b_{i+1}",
            )

    def _encode_partition_constraints(self, k):

        if self.partition_constraints is None:
            return

        if len(self.partition_constraints) == 0:
            return

        # t is maximum number of subsets in a subset constraint
        t = max(len(c) for c in self.partition_constraints)            

        # The indices of the y_vars
        y_indexes = [(i, j, c) for i in range(k) for j in range(t) for c in range(len(self.partition_constraints))]

        # y_vars[(i, j, c)] = 1 iff the i-th element of the generating set is used in the j-th subset of the c-th constraint
        y_vars = self.solver.add_variables(
            y_indexes, 
            name_prefix="y", 
            lb=0, 
            ub=1, 
            var_type="integer"
        )
        # pi_y_vars[(i, j, c)] = y_vars[(i, j, c)] * genset_vars[i]
        pi_y_vars = self.solver.add_variables(
            y_indexes, 
            name_prefix="product_y", 
            lb=0, 
            ub=self.total, 
            var_type="integer" if self.weight_type == int else "continuous"
        )
        for i in range(k):
            for j in range(t):
                for c in range(len(self.partition_constraints)):
                    self.solver.add_binary_continuous_product_constraint(
                        binary_var=y_vars[(i, j, c)],
                        continuous_var=self.genset_vars[(i)],
                        product_var=pi_y_vars[(i, j, c)],
                        lb=0,
                        ub=self.total,
                        name=f"pi_y_i={i}_j={j}_c={c}",
                    )

        # Every element in the generating set must be used exactly once to obtain the numbers in each subset
        for i in range(k):
            for c in range(len(self.partition_constraints)):
                self.solver.add_constraint(
                    self.solver.quicksum(
                        y_vars[(i, j, c)]
                        for j in range(t)
                    )
                    == 1,
                    name=f"used_exactly_once_constr={c}_i={j}",
                )

        # Imposing the subset constraints
        for c, constraint in enumerate(self.partition_constraints):
            for j in range(len(constraint)):
                self.solver.add_constraint(
                    self.solver.quicksum(
                        pi_y_vars[(i, j, c)]
                        for i in range(k)
                    )
                    == constraint[j],
                    name=f"subset_sum_constr={c}_subset_j={j}",
                )
                
    def solve(self):
        """
        Solves the minimum generating set problem. Returns `True` if the model was solved, `False` otherwise.
        """
        start_time = time.perf_counter()

        # Solve for increasing numbers of elements in the generating set
        for k in range(self.lowerbound, max(self.lowerbound+1, len(self.initial_numbers))):
            self._create_solver(k=k)
            self.solver.optimize()

            if self.solver.get_model_status() == "kOptimal":
                genset_sol = self.solver.get_values(self.genset_vars)
                self._solution = sorted(self.weight_type(genset_sol[i]) for i in range(k))
                self._is_solved = True
                self.solve_statistics = {
                    "solve_time": time.perf_counter() - start_time,
                    "num_elements": k,
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
            utils.logger.error(f"{__name__}: Model not yet solved. If you want to solve it, call the `solve` method first.")
            raise Exception("Model not yet solved. If you want to solve it, call the `solve` method first.")
        
        return self._is_solved
    
    def check_is_solved(self):
        if not self.is_solved():
            raise Exception(
                "Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit."
            )

    def get_solution(self):
        """
        Returns the solution to the minimum generating set problem, if the model was solved. 
        
        !!! warning "Warning"
            Call the `solve` method first.
        """
        if self._solution is not None:
            return self._solution
        
        self.check_is_solved()

        return self._solution  

        