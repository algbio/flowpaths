import sys

def create_solver(solver_name):
    """Dynamically import the solver module and create an optimization model."""
    if solver_name == "gurobipy":
        import gurobipy as gp
        return gp.Model(), gp
    elif solver_name == "highspy":
        import highspy as hp
        return hp.Model(), hp
    elif solver_name == "pyscipopt":
        import pyscipopt as sp
        return sp.Model(), sp
    else:
        raise ValueError(f"Unsupported solver: {solver_name}")

def solve_milp(solver_name):
    """Formulate and solve a simple MILP model using the specified solver."""
    model, solver = create_solver(solver_name)
    
    # Define variables
    if solver_name == "gurobipy":
        x = model.addVar(vtype=solver.GRB.BINARY, name="x")
        y = model.addVar(vtype=solver.GRB.INTEGER, lb=0, name="y")
    else:
        x = model.addVar(vtype=solver.VarType.BINARY, name="x")
        y = model.addVar(vtype=solver.VarType.INTEGER, lb=0, name="y")
    
    # Set objective: maximize x + 2y
    model.setObjective(x + 2 * y, solver.GRB.MAXIMIZE if solver_name == "gurobipy" else solver.ObjectiveSense.MAXIMIZE)
    
    # Add constraint: x + y <= 2
    model.addConstr(x + y <= 2, name="c1")
    
    # Solve model
    model.optimize()
    
    # Output results
    if model.status == (solver.GRB.OPTIMAL if solver_name == "gurobipy" else solver.Status.OPTIMAL):
        print(f"Optimal solution found with {solver_name}:")
        print(f"x = {x.X}, y = {y.X}")
    else:
        print("No optimal solution found.")

if __name__ == "__main__":
    
    solver_name = "pyscipopt"
    solve_milp(solver_name)