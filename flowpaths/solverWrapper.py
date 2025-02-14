class solverWrapper:
    def __init__(self, solver_type='highs', **kwargs):
        self.solver_type = solver_type
        self.tolerance = kwargs.get('tolerance', 1e-6)  # Default tolerance value

        if solver_type == 'highs':
            import highspy
            self.solver = highspy.Highs()
            self.solver.setOptionValue("threads", kwargs.get('threads', 4))
            self.solver.setOptionValue("time_limit", kwargs.get('time_limit', 300))
            self.solver.setOptionValue("presolve", kwargs.get('presolve', "on"))
            self.solver.setOptionValue("log_to_console", kwargs.get('log_to_console', "false"))
            self.solver.setOptionValue("mip_rel_gap", self.tolerance)
        elif solver_type == 'gurobi':
            import gurobipy
            self.env = gurobipy.Env(empty=True)
            self.env.setParam('OutputFlag', 0)
            self.env.setParam('LogToConsole', 1 if kwargs.get('log_to_console', "false") == "true" else 0)
            self.env.setParam('TimeLimit', kwargs.get('time_limit', 300))
            self.env.setParam('Threads', kwargs.get('threads', 4))
            self.env.setParam('MIPGap', self.tolerance)
            self.env.start()
            self.solver = gurobipy.Model(env=self.env)
        else:
            raise ValueError("Unsupported solver type")

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

    def set_objective(self, expr, sense='minimize'):
        if self.solver_type == 'highs':
            import highspy
            self.solver.setObjective(expr, sense=highspy.HighsObjectiveSense.kMinimize if sense == 'minimize' else highspy.HighsObjectiveSense.kMaximize)
        elif self.solver_type == 'gurobi':
            import gurobipy
            self.solver.setObjective(expr, gurobipy.GRB.MINIMIZE if sense == 'minimize' else gurobipy.GRB.MAXIMIZE)

    def set_minimize(self):
        if self.solver_type == 'highs':
            self.solver.setMinimize()
        elif self.solver_type == 'gurobi':
            import gurobipy
            self.solver.modelSense = gurobipy.GRB.MINIMIZE

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

# Example usage
if __name__ == "__main__":
    solver = SolverWrapper(solver_type='gurobi', threads=4, time_limit=300, log_to_console="true", tolerance=1e-5)
    indexes = [(1, 2), (2, 3), (3, 4)]
    vars = solver.add_variables(indexes, lb=0, ub=1, var_type='integer', name_prefix='e')
    solver.add_constraint(vars[(1, 2)] + vars[(2, 3)] == 1, name="constraint1")
    solver.set_objective(vars[(1, 2)] + vars[(2, 3)] + vars[(3, 4)], sense='minimize')
    solver.optimize()
    print(solver.get_model_status())
    print(solver.get_variable_values())