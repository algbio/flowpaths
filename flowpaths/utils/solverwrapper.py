import highspy

class SolverWrapper:
    """
    A wrapper class for the both the HiGHS (highspy) and Gurobi (gurobipy) solvers.

    This supports the following functionalities:
    - Adding:
        - Variables
        - Constraints
        - Product Constraints, encoding the product of a binary variable and a positive continuous / integer variable
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

    def __init__(self, external_solver="highs", **kwargs):
        self.external_solver = external_solver
        self.tolerance = kwargs.get("tolerance", SolverWrapper.tolerance)  # Default tolerance value
        if self.tolerance < 1e-9:
            raise ValueError("The tolerance value must be smaller than 1e-9.")

        self.variable_name_prefixes = []

        if external_solver == "highs":
            self.solver = highspy.Highs()
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

    def add_product_constraint(self, binary_var, product_var, equal_var, bound, name: str):
        """
        This function adds constraints to model the equality:
            binary_var * product_var = equal_var

        Assumptions
        -----------
        - binary_var in [0,1]
        - 0 <= product_var <= bound

        Parameters
        ----------
        binary_var : Variable
            The binary variable.
        product_var : Variable
            The product variable.
        equal_var : Variable
            The variable that should be equal to the product of the binary and product variables.
        bound : float
            The upper bound of the product variable.
        name : str
            The name of the constraint
        """
        self.add_constraint(equal_var <= binary_var * bound, name=name + "_a")
        self.add_constraint(equal_var <= product_var, name=name + "_b")
        self.add_constraint(equal_var >= product_var - (1 - binary_var) * bound, name=name + "_c")

    def set_objective(self, expr, sense="minimize"):

        if sense not in ["minimize", "maximize"]:
            raise ValueError(f"Objective sense {sense} is not supported. Only [\"minimize\", \"maximize\"] are supported.")

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

    def get_model_status(self):
        if self.external_solver == "highs":
            return self.solver.getModelStatus().name
        elif self.external_solver == "gurobi":
            return self.solver.status

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
            binary_values (bool, optional): If True, ensures that the variable values (rounded) are 
                                            binary (0 or 1). Defaults to False.

        Returns:
            dict: A dictionary where the keys are the indices of the variables (as tuples or 
                  single values) and the values are the corresponding variable values.

        Raises:
            Exception: If the length of `index_types` does not match the number of indices 
                       in a variable name.
            Exception: If `binary_values` is True and a variable value (rounded) is not binary.
        """
        varNames = self.get_all_variable_names()
        varValues = self.get_all_variable_values()

        values = dict()

        for index, var in enumerate(varNames):
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
                    if len(index_types) != 1:
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