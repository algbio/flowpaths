import highspy

class SolverWrapper:
    def __init__(self, solver_type="highs", **kwargs):
        self.solver_type = solver_type
        self.tolerance = kwargs.get("tolerance", 1e-9)  # Default tolerance value
        if self.tolerance < 1e-9:
            raise ValueError("The tolerance value must be smaller than 1e-9.")

        if solver_type == "highs":

            self.solver = highspy.Highs()
            self.solver.setOptionValue("threads", kwargs.get("threads", 4))
            self.solver.setOptionValue("time_limit", kwargs.get("time_limit", 300))
            self.solver.setOptionValue("presolve", kwargs.get("presolve", "choose"))
            self.solver.setOptionValue("log_to_console", kwargs.get("log_to_console", "false"))
            self.solver.setOptionValue("mip_rel_gap", self.tolerance)
            self.solver.setOptionValue("mip_feasibility_tolerance", self.tolerance)
            self.solver.setOptionValue("mip_abs_gap", self.tolerance)
            self.solver.setOptionValue("mip_rel_gap", self.tolerance)
            self.solver.setOptionValue("primal_feasibility_tolerance", self.tolerance)
        elif solver_type == "gurobi":
            import gurobipy

            self.env = gurobipy.Env(empty=True)
            self.env.setParam("OutputFlag", 0)
            self.env.setParam("LogToConsole", 1 if kwargs.get("log_to_console", "false") == "true" else 0)
            self.env.setParam("OutputFlag", 1 if kwargs.get("log_to_console", "false") == "true" else 0)
            self.env.setParam("TimeLimit", kwargs.get("time_limit", 300))
            self.env.setParam("Threads", kwargs.get("threads", 4))
            self.env.setParam("MIPGap", self.tolerance)
            self.env.setParam("IntFeasTol", self.tolerance)
            self.env.setParam("FeasibilityTol", self.tolerance)
            
            self.env.start()
            self.solver = gurobipy.Model(env=self.env)
        else:
            raise ValueError(
                f"Unsupported solver type `{solver_type}`, supported solvers are `highs` and `gurobi`."
            )

    def add_variables(self, indexes, name_prefix: str, lb=0, ub=1, var_type="integer"):
        if self.solver_type == "highs":

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
        elif self.solver_type == "gurobi":
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
        if self.solver_type == "highs":
            self.solver.addConstr(expr, name=name)
        elif self.solver_type == "gurobi":
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
        if self.solver_type == "highs":
            if sense == "minimize":
                self.solver.minimize(expr)
            else:
                self.solver.maximize(expr)
        elif self.solver_type == "gurobi":
            import gurobipy

            self.solver.setObjective(
                expr,
                gurobipy.GRB.MINIMIZE if sense == "minimize" else gurobipy.GRB.MAXIMIZE,
            )

    def optimize(self):
        if self.solver_type == "highs":
            self.solver.optimize()
        elif self.solver_type == "gurobi":
            self.solver.optimize()

    def write_model(self, filename):
        if self.solver_type == "highs":
            self.solver.writeModel(filename)
        elif self.solver_type == "gurobi":
            self.solver.write(filename)

    def get_model_status(self):
        if self.solver_type == "highs":
            return self.solver.getModelStatus().name
        elif self.solver_type == "gurobi":
            return self.solver.status

    def get_all_variable_values(self):
        if self.solver_type == "highs":
            return self.solver.allVariableValues()
        elif self.solver_type == "gurobi":
            return [var.X for var in self.solver.getVars()]

    def get_all_variable_names(self):
        if self.solver_type == "highs":
            return self.solver.allVariableNames()
        elif self.solver_type == "gurobi":
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
