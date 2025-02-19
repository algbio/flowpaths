class SolverWrapper:
    def __init__(self, solver_type='highs', **kwargs):
        self.solver_type = solver_type
        self.tolerance = kwargs.get('tolerance', 1e-4)  # Default tolerance value

        if solver_type == 'highs':
            import highspy
            self.solver = highspy.Highs()
            self.solver.setOptionValue("threads", kwargs.get('threads', 4))
            self.solver.setOptionValue("time_limit", kwargs.get('time_limit', 300))
            self.solver.setOptionValue("presolve", kwargs.get('presolve', "choose"))
            self.solver.setOptionValue("log_to_console", kwargs.get('log_to_console', "false"))
            self.solver.setOptionValue("mip_rel_gap", self.tolerance)
        elif solver_type == 'gurobi':
            import gurobipy
            self.env = gurobipy.Env(empty=True)
            self.env.setParam('OutputFlag', 0)
            self.env.setParam('LogToConsole', 1 if kwargs.get('log_to_console', "false") == "true" else 0)
            self.env.setParam('OutputFlag', 1 if kwargs.get('log_to_console', "false") == "true" else 0)
            self.env.setParam('TimeLimit', kwargs.get('time_limit', 300))
            self.env.setParam('Threads', kwargs.get('threads', 4))
            self.env.setParam('MIPGap', self.tolerance)
            self.env.start()
            self.solver = gurobipy.Model(env=self.env)
        else:
            raise ValueError(f"Unsupported solver type `{solver_type}`")

    def add_variables(self, indexes, lb=0, ub=1, var_type='integer', name_prefix=''):
        if self.solver_type == 'highs':
            import highspy
            var_type_map = {
                'integer': highspy.HighsVarType.kInteger,
                'continuous': highspy.HighsVarType.kContinuous
            }
            return self.solver.addVariables(indexes, lb=lb, ub=ub, type=var_type_map[var_type], name_prefix=name_prefix)
        elif self.solver_type == 'gurobi':
            import gurobipy
            var_type_map = {
                'integer': gurobipy.GRB.INTEGER,
                'continuous': gurobipy.GRB.CONTINUOUS
            }
            vars = {}
            for index in indexes:
                vars[index] = self.solver.addVar(lb=lb, ub=ub, vtype=var_type_map[var_type], name=f"{name_prefix}{index}")
            self.solver.update()
            return vars

    def add_constraint(self, expr, name=''):
        if self.solver_type == 'highs':
            self.solver.addConstr(expr, name=name)
        elif self.solver_type == 'gurobi':
            self.solver.addConstr(expr, name=name)

    def add_product_constraint(self, binary_var, product_var, equal_var, bound, name):
        self.add_constraint(equal_var <= binary_var * bound, name=name + "_a")
        self.add_constraint(equal_var <= product_var, name=name + "_b")
        self.add_constraint(equal_var >= product_var - (1 - binary_var) * bound, name=name + "_c")

    def set_objective(self, expr, sense='minimize'):
        if self.solver_type == 'highs':
            if sense == 'minimize':
                self.solver.minimize(expr)
            else:
                self.solver.maximize(expr)
        elif self.solver_type == 'gurobi':
            import gurobipy
            self.solver.setObjective(expr, gurobipy.GRB.MINIMIZE if sense == 'minimize' else gurobipy.GRB.MAXIMIZE)

    def optimize(self):
        if self.solver_type == 'highs':
            self.solver.optimize()
        elif self.solver_type == 'gurobi':
            self.solver.optimize()

    def write_model(self, filename):
        if self.solver_type == 'highs':
            self.solver.writeModel(filename)
        elif self.solver_type == 'gurobi':
            self.solver.write(filename)

    def get_model_status(self):
        if self.solver_type == 'highs':
            return self.solver.getModelStatus().name
        elif self.solver_type == 'gurobi':
            return self.solver.status

    def get_variable_values(self):
        if self.solver_type == 'highs':
            return self.solver.allVariableValues()
        elif self.solver_type == 'gurobi':
            return [var.X for var in self.solver.getVars()]

    def get_variable_names(self):
        if self.solver_type == 'highs':
            return self.solver.allVariableNames()
        elif self.solver_type == 'gurobi':
            return [var.VarName for var in self.solver.getVars()]