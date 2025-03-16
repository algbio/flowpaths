import flowpaths.utils.solverwrapper as sw

class MinGenSet():
    def __init__(
            self, 
            numbers: list,
            total,
            weight_type: type = float,
            lowerbound: int = 1,
            remove_sums_of_two: bool = True,
            remove_complement_values: bool = True
            ):
        """
        This class solves the minimum generating set problem. Given a list of numbers `a` and a total value `total`, 
        the goal is to find the smallest list of numbers `generating_set` such that:
        
        - the sum of the elements in `generating_set` equals `total`, and
        - every element in `a` can be expressed as the sum of some elements in `generating_set`.
        
        Parameters
        ----------

        - `a` : list
            A list of numbers.
        - `total` : int | float
            The total value that the sum of the elements in the generating set should equal.
        - `weight_type` : type
            The type of the numbers in `generating_set`. Default is `float`. Other option is `int`.
        - `lowerbound` : int
            The minimum number of elements in the generating set. Default is 1.
        - `remove_sums_of_two` : bool
            If True, it removes elements from `a` that are the sum of two other elements in `a`. Default is `True`.
        - `remove_complement_values` : bool
            If True, if `a` contains both `x` and `total - x`, it keeps only the smallest of them. Default is `True`.
        """
        
        self.numbers = list(numbers) # Make a copy of the list
        self.initial_numbers = numbers
        self.total = total
        self.weight_type = weight_type
        self.lowerbound = lowerbound

        self.__is_solved = False
        self.__solution = None

        if self.weight_type not in [int, float]:
            raise ValueError("weight_type must be either `int` or `float`.")

        if remove_sums_of_two:
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
        
        print(f"Numbers: {self.numbers}")
        
    def solve(self):
        """
        Solves the minimum generating set problem.

        Returns
        -------
        
        - `bool`
            True if the model was solved, False otherwise.
        """
        
        # Solve for increasing numbers of elements in the generating set
        for k in range(self.lowerbound, len(self.initial_numbers)):
            print(f"Trying with {k} elements in the generating set.")
            self.solver = sw.SolverWrapper()

            self.b_indexes = [(i)   for i in range(k)]
            self.x_indexes = [(i,j) for i in range(k) for j in range(len(self.numbers))]

            self.genset_vars = self.solver.add_variables(
                self.b_indexes, 
                name_prefix="gen_set", 
                lb=0, 
                ub=self.total,
                var_type="integer" if self.weight_type == int else "continuous"
            )

            self.x_vars = self.solver.add_variables(
                self.x_indexes, 
                name_prefix="x", 
                lb=0, 
                ub=1, 
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

            # Sum of elements in the base set equals total
            self.solver.add_constraint(
                self.solver.quicksum(
                    self.genset_vars[i]
                    for i in self.b_indexes
                )
                == self.total,
                name=f"total",
            )

            for j in range(len(self.numbers)):                

                # pi_vars[(i, j)] = x_vars[(i, j)] * b_vars[i]
                for i in range(k):
                    self.solver.add_binary_continuous_product_constraint(
                        binary_var=self.x_vars[(i, j)],
                        continuous_var=self.genset_vars[(i)],
                        product_var=self.pi_vars[(i, j)],
                        lb=0,
                        ub=self.total,
                        name=f"pi_i={i}_j={j}",
                    )

                # Sum of pi_vars[(i, j)] for all i is a[j]
                self.solver.add_constraint(
                    self.solver.quicksum(
                        self.pi_vars[(i, j)]
                        for i in self.b_indexes
                    )
                    == self.numbers[j],
                    name=f"sum_pi_j={j}",
                )

            # Symmetry breaking
            for i in range(k - 2):
                self.solver.add_constraint(
                    self.genset_vars[i] <= self.genset_vars[i+1],
                    name=f"b_{i}_leq_b_{i+1}",
                )

            self.solver.optimize()
            if self.solver.get_model_status() == "kOptimal":
                genset_sol = self.solver.get_variable_values("gen_set", [int])
                self.__solution = sorted(self.weight_type(genset_sol[i]) for i in range(k))
                self.__is_solved = True
                return True
            
        return False

    def is_solved(self):
        """
        Returns True if the model was solved, False otherwise.
        """
        if self.__is_solved is None:
            raise Exception("Model not yet solved. If you want to solve it, call the `solve` method first.")
        
        return self.__is_solved
    
    def check_is_solved(self):
        if not self.is_solved():
            raise Exception(
                "Model not solved. If you want to solve it, call the solve method first. \
                  If you already ran the solve method, then the model is infeasible, or you need to increase parameter time_limit."
            )

    def get_solution(self):
        """
        Returns the solution to the minimum generating set problem, if the model was solved. Call `solve` method first.
        """
        if self.__solution is not None:
            return self.__solution
        
        self.check_is_solved()

        return self.__solution  

        