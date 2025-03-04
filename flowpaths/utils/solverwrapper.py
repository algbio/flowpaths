from math import log2
from math import ceil
import highspy

class SolverWrapper:
    """
    A wrapper class for the both the [HiGHS (highspy)](https://highs.dev) and 
    [Gurobi](https://www.gurobi.com/solutions/gurobi-optimizer/) 
    ([gurobipy](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python)) solvers.

    This supports the following functionalities:

    - Adding:
        - Variables
        - Constraints
        - Product Constraints, encoding the product of a binary / integer variable and a positive continuous / integer variable
        - Piecewise constant constraints
    - Setting the objective
    - Optimizing, and getting the model status
    - Writing the model to a file
    - Getting variable names and values
    - Getting the objective value
    """
    # storing some defaults
    threads = 4
    time_limit = 300
    presolve = "choose"
    log_to_console = "false"
    external_solver = "highs"
    tolerance = 1e-9
    optimization_sense = "minimize"

    # We try to map gurobi status codes to HiGHS status codes when there is a clear correspondence
    gurobi_status_to_highs = {
        2: "kOptimal",
        3: "kInfeasible",
        4: "kUnboundedOrInfeasible",
        5: "kUnbounded",
        7: "kIterationLimit",
        9: "kTimeLimit",
        10: "kSolutionLimit",
        17: "kMemoryLimit",
    }

    def __init__(
        self, 
        external_solver="highs", 
        **kwargs
        ):

        self.external_solver = external_solver
        self.tolerance = kwargs.get("tolerance", SolverWrapper.tolerance)  # Default tolerance value
        if self.tolerance < 1e-9:
            raise ValueError("The tolerance value must be >=1e-9.")
        
        self.optimization_sense = kwargs.get("optimization_sense", SolverWrapper.optimization_sense)  # Default optimization sense
        if self.optimization_sense not in ["minimize", "maximize"]:
            raise ValueError(f"Optimization sense {self.optimization_sense} is not supported. Only [\"minimize\", \"maximize\"] are supported.")

        self.variable_name_prefixes = []

        if external_solver == "highs":
            self.solver = highspy.Highs()
            self.solver.setOptionValue("solver", "choose")
            self.solver.setOptionValue("threads", kwargs.get("threads", SolverWrapper.threads))
            self.solver.setOptionValue("time_limit", kwargs.get("time_limit", SolverWrapper.time_limit))
            self.solver.setOptionValue("presolve", kwargs.get("presolve", SolverWrapper.presolve))
            self.solver.setOptionValue("log_to_console", kwargs.get("log_to_console", SolverWrapper.log_to_console))
            self.solver.setOptionValue("mip_rel_gap", self.tolerance)
            self.solver.setOptionValue("mip_feasibility_tolerance", self.tolerance)
            self.solver.setOptionValue("mip_abs_gap", self.tolerance)
            self.solver.setOptionValue("mip_rel_gap", self.tolerance)
            self.solver.setOptionValue("primal_feasibility_tolerance", self.tolerance)
        elif external_solver == "gurobi":
            import gurobipy

            self.env = gurobipy.Env(empty=True)
            self.env.setParam("OutputFlag", 0)
            self.env.setParam("LogToConsole", 1 if kwargs.get("log_to_console", SolverWrapper.log_to_console) == "true" else 0)
            self.env.setParam("OutputFlag", 1 if kwargs.get("log_to_console", SolverWrapper.log_to_console) == "true" else 0)
            self.env.setParam("TimeLimit", kwargs.get("time_limit", SolverWrapper.time_limit))
            self.env.setParam("Threads", kwargs.get("threads", SolverWrapper.threads))
            self.env.setParam("MIPGap", self.tolerance)
            self.env.setParam("IntFeasTol", self.tolerance)
            self.env.setParam("FeasibilityTol", self.tolerance)
            
            self.env.start()
            self.solver = gurobipy.Model(env=self.env)
        else:
            raise ValueError(
                f"Unsupported solver type `{external_solver}`, supported solvers are `highs` and `gurobi`."
            )

    def add_variables(self, indexes, name_prefix: str, lb=0, ub=1, var_type="integer"):
        
        # Check if there is already a variable name prefix which has as prefix the current one
        # of if the current one has as prefix an existing one
        for prefix in self.variable_name_prefixes:
            if prefix.startswith(name_prefix) or name_prefix.startswith(prefix):
                raise ValueError(
                    f"Variable name prefix {name_prefix} conflicts with existing variable name prefix {prefix}. Use a different name prefix."
                )
            
        self.variable_name_prefixes.append(name_prefix)
        
        if self.external_solver == "highs":

            var_type_map = {
                "integer": highspy.HighsVarType.kInteger,
                "continuous": highspy.HighsVarType.kContinuous,
            }
            return self.solver.addVariables(
                indexes,
                lb=lb,
                ub=ub,
                type=var_type_map[var_type],
                name_prefix=name_prefix,
            )
        elif self.external_solver == "gurobi":
            import gurobipy

            var_type_map = {
                "integer": gurobipy.GRB.INTEGER,
                "continuous": gurobipy.GRB.CONTINUOUS,
            }
            vars = {}
            for index in indexes:
                vars[index] = self.solver.addVar(
                    lb=lb,
                    ub=ub,
                    vtype=var_type_map[var_type],
                    name=f"{name_prefix}{index}",
                )
            self.solver.update()
            return vars

    def add_constraint(self, expr, name=""):
        if self.external_solver == "highs":
            self.solver.addConstr(expr, name=name)
        elif self.external_solver == "gurobi":
            self.solver.addConstr(expr, name=name)

    def add_binary_continuous_product_constraint(self, binary_var, continuous_var, product_var, lb, ub, name: str):
        """
        Description
        -----------
        This function adds constraints to model the equality: `binary_var` * `continuous_var` = `product_var`.

        Assumptions:
            - `binary_var` $\in [0,1]$
            - lb ≤ `continuous_var` ≤ ub

        Note:
            This works correctly also if `continuous_var` is an integer variable.

        Args:
            binary_var (variable): The binary variable.
            continuous_var (variable): The continuous variable (can also be integer).
            product_var (variable): The variable that should be equal to the product of the binary and continous variables.
            lb (float): The lower bound of the continuous variable.
            ub (float): The upper bound of the continuous variable.
            name (str): The name of the constraint.
        """
        self.add_constraint(product_var <= ub * binary_var, name=name + "_a")
        self.add_constraint(product_var >= lb * binary_var, name=name + "_b")
        self.add_constraint(product_var <= continuous_var - lb * (1 - binary_var), name=name + "_c")
        self.add_constraint(product_var >= continuous_var - ub * (1 - binary_var), name=name + "_d")

    def add_integer_continuous_product_constraint(self, integer_var, continuous_var, product_var, lb, ub, name: str):
        """
        This function adds constraints to model the equality:
            integer_var * continuous_var = product_var

        Assumptions
        -----------
        lb <= product_var <= ub

        !!!tip "Note"
            This works correctly also if `continuous_var` is an integer variable.

        Parameters
        ----------
        binary_var : Variable
            The binary variable.
        continuous_var : Variable
            The continuous variable (can also be integer).
        product_var : Variable
            The variable that should be equal to the product of the binary and continous variables.
        lb, ub : float
            The lower and upper bounds of the continuous variable.
        name : str
            The name of the constraint
        """

        num_bits = ceil(log2(ub + 1))
        bits = list(range(num_bits))

        binary_vars = self.add_variables(
            indexes=bits,
            name_prefix=f"binary_{name}",
            lb=0,
            ub=1,
            var_type="integer"
        )

        # We encode integer_var == sum(binary_vars[i] * 2^i)
        self.add_constraint(
            self.quicksum(binary_vars[i] * 2**i for i in bits) 
            == integer_var, 
            name=f"{name}_int_eq"
        )

        comp_vars = self.add_variables(
            indexes=bits,
            name_prefix=f"comp_{name}",
            lb=lb,
            ub=ub,
            var_type="continuous"
        )

        # We encode comp_vars[i] == binary_vars[i] * continuous_var
        for i in bits:
            self.add_binary_continuous_product_constraint(
                binary_var=binary_vars[i],
                continuous_var=continuous_var,
                product_var=comp_vars[i],
                lb=lb,
                ub=ub,
                name=f"product_{i}_{name}"
            )

        # We encode product_var == sum_{i in bits} comp_vars[i] * 2^i
        self.add_constraint(
            self.quicksum(comp_vars[i] * 2**i for i in bits) 
            == product_var, 
            name=f"{name}_prod_eq"
        )

    def quicksum(self, expr):
        if self.external_solver == "highs":
            return self.solver.qsum(expr)
        elif self.external_solver == "gurobi":
            import gurobipy

            return gurobipy.quicksum(expr)

    def set_objective(self, expr, sense="minimize"):

        if sense not in ["minimize", "maximize"]:
            raise ValueError(f"Objective sense {sense} is not supported. Only [\"minimize\", \"maximize\"] are supported.")
        self.optimization_sense = sense

        if self.external_solver == "highs":
            if sense == "minimize":
                self.solver.minimize(expr)
            else:
                self.solver.maximize(expr)
        elif self.external_solver == "gurobi":
            import gurobipy

            self.solver.setObjective(
                expr,
                gurobipy.GRB.MINIMIZE if sense == "minimize" else gurobipy.GRB.MAXIMIZE,
            )

    def optimize(self):
        if self.external_solver == "highs":
            self.solver.optimize()
        elif self.external_solver == "gurobi":
            self.solver.optimize()

    def write_model(self, filename):
        if self.external_solver == "highs":
            self.solver.writeModel(filename)
        elif self.external_solver == "gurobi":
            self.solver.write(filename)

    def get_model_status(self, raw = False):
        if self.external_solver == "highs":
            return self.solver.getModelStatus().name
        elif self.external_solver == "gurobi":
            return SolverWrapper.gurobi_status_to_highs.get(self.solver.status, self.solver.status) if not raw else self.solver.status

    def get_all_variable_values(self):
        if self.external_solver == "highs":
            return self.solver.allVariableValues()
        elif self.external_solver == "gurobi":
            return [var.X for var in self.solver.getVars()]

    def get_all_variable_names(self):
        if self.external_solver == "highs":
            return self.solver.allVariableNames()
        elif self.external_solver == "gurobi":
            return [var.VarName for var in self.solver.getVars()]

    def print_variable_names_values(self):
        varNames = self.get_all_variable_names()
        varValues = self.get_all_variable_values()

        for index, var in enumerate(varNames):
            print(f"{var} = {varValues[index]}")

    def get_variable_values(
        self, name_prefix, index_types: list, binary_values: bool = False 
    ) -> dict:
        """
        Retrieve the values of variables whose names start with a given prefix.

        This method extracts variable values from the solver, filters them based on a 
        specified prefix, and returns them in a dictionary with appropriate indexing.

        Args:
            name_prefix (str): The prefix of the variable names to filter.
            index_types (list): A list of types corresponding to the indices of the variables.
                                Each type in the list is used to cast the string indices to 
                                the appropriate type.
                                If empty, then it is assumed that the variable has no index, and does exact matching with the variable name.
            binary_values (bool, optional): If True, ensures that the variable values (rounded) are 
                                            binary (0 or 1). Defaults to False.

        Returns:
            values: A dictionary where the keys are the indices of the variables (as tuples or 
                  single values) and the values are the corresponding variable values.
                  If index_types is empty, then the unique key is 0 and the value is the variable value.

        Raises:
            Exception: If the length of `index_types` does not match the number of indices 
                       in a variable name.
            Exception: If `binary_values` is True and a variable value (rounded) is not binary.
        """
        varNames = self.get_all_variable_names()
        varValues = self.get_all_variable_values()

        values = dict()

        for index, var in enumerate(varNames):
            # print(f"Checking variable {var} against prefix {name_prefix}")
            if var == name_prefix:
                if len(index_types) > 0:
                    raise Exception(
                        f"We are getting the value of variable {var}, but the provided list of var_types is not empty ({index_types})."
                    )
                values[0] = varValues[index]
                if binary_values and round(values[0]) not in [0,1]:
                    raise Exception(f"Variable {var} has value {values[0]}, which is not binary.")
                # We return already, because we are supposed to match only one variable name
                # print("Returning values", values)
                return values

            if var.startswith(name_prefix):
                if var.count("(") == 1:
                    elements = [
                        elem.strip(" '")
                        for elem in var.replace(name_prefix, "", 1)
                        .replace("(", "")
                        .replace(")", "")
                        .split(",")
                    ]
                    tuple_index = tuple(
                        [index_types[i](elements[i]) for i in range(len(elements))]
                    )

                    if len(index_types) != len(elements):
                        raise Exception(
                            f"We are getting the value of variable {var}, indexed by ({tuple_index}), but the provided list of var_types ({index_types}) has different length."
                        )

                    values[tuple_index] = varValues[index]
                    if (
                        binary_values
                        and round(values[tuple_index]) not in [0,1]
                    ):
                        raise Exception(
                            f"Variable {var} has value {values[tuple_index]}, which is not binary."
                        )
                else:
                    element = var.replace(name_prefix, "", 1)
                    if len(index_types) > 1:
                        raise Exception(
                            f"We are getting the value of variable {var}, with only one index ({element}), but the provided list of var_types is not of length one ({index_types})."
                        )

                    elem_index = index_types[0](element)
                    values[elem_index] = varValues[index]
                    if (
                        binary_values 
                        and round(values[elem_index]) not in [0,1]
                    ):
                        raise Exception(
                            f"Variable {var} has value {values[elem_index]}, which is not binary."
                        )

        if binary_values:
            for key in values.keys():
                values[key] = round(values[key])

        return values

    def get_objective_value(self):
        if self.external_solver == "highs":
            return self.solver.getObjectiveValue()
        elif self.external_solver == "gurobi":
            return self.solver.objVal

    def add_piecewise_constant_constraint(
        self, x, y, ranges: list, constants: list, name_prefix: str
    ):
        """
        Enforces that variable `y` equals a constant from `constants` depending on the range that `x` falls into.
        
        For each piece i:
            if x in [ranges[i][0], ranges[i][1]] then y = constants[i].

        Assumptions:
            - The ranges must be non-overlapping. Otherwise, if x belongs to more ranges, the solver will choose one arbitrarily.
            - The value of x must be within the union of the ranges. Otherwise the solver will not find a feasible solution.
        
        This is modeled by:
        - introducing binary variables z[i] with sum(z) = 1,
        - for each piece i:
                x >= L_i - M*(1 - z[i])
                x <= U_i + M*(1 - z[i])
                y <= constant[i] + M*(1 - z[i])
                y >= constant[i] - M*(1 - z[i])
        
        Parameters
        ----------
        x: The continuous variable (created earlier) whose value determines the segment.
        y: The continuous variable whose value equals the corresponding constant.
        ranges: List of tuples [(L0, U0), (L1, U1), ...]
        constants: List of constants [c0, c1, ...] for each segment.
        name_prefix: A prefix for naming the added variables and constraints.
        
        Returns
        -------
        y: The created piecewise output variable.
        """
        if len(ranges) != len(constants):
            raise ValueError("`ranges` and `constants` must have the same length.")

        pieces = len(ranges)
        Ls = [r[0] for r in ranges]
        Us = [r[1] for r in ranges]
        M = (max(Us) - min(Ls)) * 2

        # Create binary variables z[i] for each piece.
        z = self.add_variables(
            [(i) for i in range(pieces)],
            name_prefix=f"z_{name_prefix}",
            lb=0,
            ub=1,
            var_type="integer"
        )

        # Enforce that exactly one piece is active: sum_i z[i] == 1.
        self.add_constraint(self.quicksum(z[i] for i in range(pieces)) == 1, name=f"sum_z_{name_prefix}")

        # For each piece i, add the constraints:
        for i in range(pieces):
            L = Ls[i]
            U = Us[i]
            c = constants[i]
            # Link x with the range [L, U] if piece i is active.
            self.add_constraint(x >= L - M * (1 - z[i]), name=f"{name_prefix}_L_{i}")
            self.add_constraint(x <= U + M * (1 - z[i]), name=f"{name_prefix}_U_{i}")
            self.add_constraint(y <= c + M * (1 - z[i]), name=f"{name_prefix}_yU_{i}")
            self.add_constraint(y >= c - M * (1 - z[i]), name=f"{name_prefix}_yL_{i}")