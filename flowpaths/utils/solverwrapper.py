from math import log2
from math import ceil
import highspy
from typing import Union
import re
import os
import signal
import math
import flowpaths.utils as utils
import numpy as np

class SolverWrapper:
    """Unified MILP/LP modelling convenience layer for HiGHS and Gurobi.

        This class provides *one* API that delegates to either the
        [HiGHS (``highspy``)](https://highs.dev) or
        [Gurobi (``gurobipy``)](https://www.gurobi.com/solutions/gurobi-optimizer/) back-end.
        Only a very small, stable subset of features needed by *flowpaths* is
        wrapped - it is **not** a general purpose replacement for the native APIs.

        Key capabilities
        ----------------
        - Create variables (continuous / integer) in bulk with name prefixing
        - Add linear constraints
        - Add specialized modelling shortcuts:
                - binary * continuous (McCormick) product constraints
                - integer * continuous product constraints (bit expansion + binaries)
                - piecewise constant constraints (one-hot selection)
        - Build linear objectives without triggering a solve (HiGHS) or with native
            semantics (Gurobi)
        - Optimize with optional *custom* wall clock timeout (in addition to the
            solver internal time limit)
        - Retrieve objective, variable names, variable values (optionally enforcing
            integrality for binaries), status (mapped to HiGHS style codes)
        - Persist model to disk (``.lp`` / ``.mps`` depending on backend support)

        Design notes
        ------------
        - A minimal set of solver parameters is exposed via keyword arguments in
            ``__init__`` to keep call sites clean.
        - Status codes for Gurobi are mapped onto HiGHS style names where a clear
            1-to-1 mapping exists (see ``gurobi_status_to_highs``).
        - A *secondary* timeout based on POSIX signals can be enabled to guard
            against situations where the native solver time limit is not obeyed
            precisely. When this fires ``did_timeout`` is set and the reported status
            becomes ``kTimeLimit``.

        Parameters
        ----------
        **kwargs :
            Flexible configuration. Recognised keys (all optional):
            - ``external_solver`` (str): ``"highs"`` (default) or ``"gurobi"``.
            - ``threads`` (int): Thread limit for solver (default: ``4``).
            - ``time_limit`` (float): Internal solver time limit in seconds
                (default: ``inf`` = no limit).
            - ``use_also_custom_timeout`` (bool): If ``True`` activate an *extra*
                signal based timeout equal to ``time_limit`` (default ``False``).
            - ``presolve`` (str): HiGHS presolve strategy (default ``"choose"``).
            - ``log_to_console`` (str): ``"true"`` / ``"false"`` (default
                ``"false"``) - normalized to solver specific flags.
            - ``tolerance`` (float): MIP gap, feasibility, integrality tolerance
                applied uniformly (default ``1e-9``; must be >= 1e-9).
            - ``optimization_sense`` (str): ``"minimize"`` or ``"maximize``
                (default ``"minimize"``).

        Attributes
        ----------
        external_solver : str
                Active backend (``"highs"`` or ``"gurobi"``).
        solver : object
                Underlying solver object (``highspy.Highs`` or ``gurobipy.Model``).
        time_limit : float
                Configured internal solver time limit (seconds).
        use_also_custom_timeout : bool
                Whether the secondary POSIX signal timeout is enabled.
        tolerance : float
                Unified tolerance applied to various solver parameters.
        optimization_sense : str
                ``"minimize"`` or ``"maximize"`` as last set on the objective.
        did_timeout : bool
                Flag set to ``True`` only when the *custom* timeout fired.
        variable_name_prefixes : list[str]
                Record of prefixes used to detect accidental collisions.

    Raises
    ------
    ValueError
        If unsupported solver name, invalid optimization sense or an invalid
        tolerance (< 1e-9) is supplied.
    """
    # storing some defaults
    threads = 4
    time_limit = float('inf')
    presolve = "choose"
    log_to_console = "false"
    external_solver = "highs"
    tolerance = 1e-9
    optimization_sense = "minimize"
    infeasible_status = "kInfeasible"
    use_also_custom_timeout = False

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
        **kwargs
        ):

        self.external_solver = kwargs.get("external_solver", SolverWrapper.external_solver)  # Default solver
        self.time_limit = kwargs.get("time_limit", SolverWrapper.time_limit)
        self.use_also_custom_timeout = kwargs.get("use_also_custom_timeout", SolverWrapper.use_also_custom_timeout)
        self.tolerance = kwargs.get("tolerance", SolverWrapper.tolerance)  # Default tolerance value
        if self.tolerance < 1e-9:
            utils.logger.error(f"{__name__}: The tolerance value must be >=1e-9.")
            raise ValueError("The tolerance value must be >=1e-9.")
        
        self.optimization_sense = kwargs.get("optimization_sense", SolverWrapper.optimization_sense)  # Default optimization sense
        if self.optimization_sense not in ["minimize", "maximize"]:
            utils.logger.error(f"{__name__}: The optimization sense must be either `minimize` or `maximize`.")
            raise ValueError(f"Optimization sense {self.optimization_sense} is not supported. Only [\"minimize\", \"maximize\"] are supported.")

        self.variable_name_prefixes = []

        self.did_timeout = False

        if self.external_solver == "highs":
            self.solver = HighsCustom()
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
        elif self.external_solver == "gurobi":
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
            utils.logger.error(f"{__name__}: Unsupported solver type `{self.external_solver}`. Supported solvers are `highs` and `gurobi`.")
            raise ValueError(
                f"Unsupported solver type `{self.external_solver}`, supported solvers are `highs` and `gurobi`."
            )
        
        utils.logger.debug(f"{__name__}: solver_options (kwargs) = {kwargs}")

    def add_variables(self, indexes, name_prefix: str, lb=0, ub=1, var_type="integer"):
        """Create a set of variables sharing a common name prefix.

        A *collision* check ensures no prefix is a prefix of an existing one to
        avoid ambiguous parsing later when values are retrieved.

        Parameters
        ----------
        indexes : iterable
            Iterable of index labels (numbers or hashables) used *only* to
            suffix the variable names for uniqueness.
        name_prefix : str
            Prefix for each created variable (e.g. ``x_``). Must be unique with
            respect to existing prefixes (no prefix / super-prefix relations).
        lb, ub : float, default (0, 1)
            Lower and upper bounds for every created variable.
        var_type : {"integer", "continuous"}, default "integer"
            Variable domain type.

        Returns
        -------
        dict | list
            Mapping from provided index to underlying solver variable objects
            (HiGHS returns an internal structure; Gurobi returns a dict).

        Raises
        ------
        ValueError
            If ``name_prefix`` conflicts with an existing prefix.
        """
        
        # Check if there is already a variable name prefix which has as prefix the current one
        # of if the current one has as prefix an existing one
        for prefix in self.variable_name_prefixes:
            if prefix.startswith(name_prefix) or name_prefix.startswith(prefix):
                utils.logger.error(f"{__name__}: Variable name prefix {name_prefix} conflicts with existing variable name prefix {prefix}. Use a different name prefix.")
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
        """Add a linear (in)equation to the model.

        Parameters
        ----------
        expr : linear expression / bool
            The solver specific constraint expression.
        name : str, optional
            Optional identifier for the constraint.
        """
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
            product_var (variable): The variable that should be equal to the product of the binary and continuous variables.
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
            The variable that should be equal to the product of the binary and continuous variables.
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
        """Backend agnostic fast summation of linear terms.

        Parameters
        ----------
        expr : iterable
            Iterable of linear terms.

        Returns
        -------
        linear expression
            A solver specific linear expression representing the sum.
        """
        if self.external_solver == "highs":
            return self.solver.qsum(expr)
        elif self.external_solver == "gurobi":
            import gurobipy

            return gurobipy.quicksum(expr)

    def set_objective(self, expr, sense="minimize"):
        """Set (and replace) the linear objective.

        For HiGHS this delegates to ``HighsCustom.set_objective_without_solving``
        (i.e. does not trigger a solve). For Gurobi it uses the native
        ``setObjective`` method.

        Parameters
        ----------
        expr : linear expression
            Objective linear expression.
        sense : {"minimize", "min", "maximize", "max"}, default "minimize"
            Optimization direction.

        Raises
        ------
        ValueError
            If ``sense`` is invalid.
        """

        if sense not in ["minimize", "min", "maximize", "max"]:
            utils.logger.error(f"{__name__}: The objective sense must be either `minimize` or `maximize`.")
            raise ValueError(f"Objective sense {sense} is not supported. Only [\"minimize\", \"min\", \"maximize\", \"max\"] are supported.")
        self.optimization_sense = sense

        if self.external_solver == "highs":
            self.solver.set_objective_without_solving(expr, sense=sense)
        elif self.external_solver == "gurobi":
            import gurobipy

            self.solver.setObjective(
                expr,
                gurobipy.GRB.MINIMIZE if sense in ["minimize", "min"] else gurobipy.GRB.MAXIMIZE,
            )

    def optimize(self):
        """Run the solver.

        Behaviour:
        - If ``time_limit`` is infinity OR ``use_also_custom_timeout`` is
            ``False`` we rely solely on the backend's time limit handling.
        - Otherwise we also arm a POSIX signal based timeout (coarse, whole
            seconds) which, when firing, sets ``did_timeout``. The underlying
            solver is not forcibly terminated beyond the signal alarm; we rely on
            cooperative interruption.
        """
        # Resetting the timeout flag
        self.did_timeout = False

        # For both solvers, we have the same function to call
        # If the time limit is infinite, we call the optimize function directly
        # Otherwise, we call the function with a timeout
        if self.time_limit == float('inf') or (not self.use_also_custom_timeout):
            self.solver.optimize()
        else:
            utils.logger.debug(f"{__name__}: Running also with use_also_custom_timeout ({self.time_limit} sec)")
            self._run_with_timeout(self.time_limit, self.solver.optimize)
    
    def write_model(self, filename):
        """Persist model to a file supported by the backend.

        Parameters
        ----------
        filename : str | os.PathLike
            Target path. HiGHS chooses format based on extension; Gurobi uses
            native ``write`` method behaviour.
        """
        if self.external_solver == "highs":
            self.solver.writeModel(filename)
        elif self.external_solver == "gurobi":
            self.solver.write(filename)

    def get_model_status(self, raw = False):
        """Return HiGHS style model status string (or raw Gurobi code).

        If the *custom* timeout was triggered the synthetic status ``kTimeLimit``
        is returned irrespective of the underlying solver state.

        Parameters
        ----------
        raw : bool, default False
            When using Gurobi: if ``True`` return the untouched integer status
            code; otherwise attempt to map to a HiGHS style enum name.

        Returns
        -------
        str | int
            Status name (always a string for HiGHS). Integer code for Gurobi
            only when ``raw=True``.
        """
        
        # If the solver has timed out with our custom time limit, we return the timeout status
        # This is set in the __run_with_timeout function
        if self.did_timeout:
            return "kTimeLimit"
        
        # If the solver has not timed out, we return the model status
        if self.external_solver == "highs":
            return self.solver.getModelStatus().name
        elif self.external_solver == "gurobi":
            return SolverWrapper.gurobi_status_to_highs.get(self.solver.status, self.solver.status) if not raw else self.solver.status

    def get_all_variable_values(self):
        """Return values for all variables in solver insertion order."""
        if self.external_solver == "highs":
            return self.solver.allVariableValues()
        elif self.external_solver == "gurobi":
            return [var.X for var in self.solver.getVars()]

    def get_all_variable_names(self):
        """Return names for all variables in solver insertion order."""
        if self.external_solver == "highs":
            return self.solver.allVariableNames()
        elif self.external_solver == "gurobi":
            return [var.VarName for var in self.solver.getVars()]

    def print_variable_names_values(self):
        """Print ``name = value`` lines for every variable (debug helper)."""
        varNames = self.get_all_variable_names()
        varValues = self.get_all_variable_values()

        for index, var in enumerate(varNames):
            print(f"{var} = {varValues[index]}")

    # def parse_var_name(self, string, name_prefix):
    #     pattern = rf"{name_prefix}\(\s*('?[\w(),]+'?|[0-9]+)\s*,\s*('?[\w(),]+'?|[0-9]+)\s*,\s*([0-9]+)\s*\)"
    #     match = re.match(pattern, string)

    #     return match.groups()

    def parse_var_name(self, string, name_prefix):
        """Parse a variable name and extract indices inside parentheses.

        Variable names follow one of two patterns:

        1. ``<prefix>(i,j,...)`` - parenthesised, comma separated indices
           where elements may be quoted strings or integers.
        2. ``<prefix><i>`` - single suffix index (handled elsewhere).

        Parameters
        ----------
        string : str
            Full variable name.
        name_prefix : str
            Expected prefix.

        Returns
        -------
        list[str]
            Raw index components (still strings, quotes stripped).

        Raises
        ------
        ValueError
            If the name does not match the expected pattern.
        """
        # Dynamic regex pattern to extract components inside parentheses
        pattern = rf"{name_prefix}\(\s*(.*?)\s*\)$"
        match = re.match(pattern, string)

        if not match:
            utils.logger.error(f"{__name__}: Invalid format for variable name: {string}")
            raise ValueError(f"Invalid format: {string}")

        # Extract the component list inside parentheses
        components_str = match.group(1)

        # Split components while handling quoted strings
        components = re.findall(r"'[^']*'|\d+", components_str)

        return components

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
                    utils.logger.error(f"{__name__}: We are getting the value of variable `{var}`, but the provided list of var_types is not empty `{index_types}`.")
                    raise Exception(
                        f"We are getting the value of variable `{var}`, but the provided list of var_types is not empty `{index_types}`."
                    )
                values[0] = varValues[index]
                if binary_values and round(values[0]) not in [0,1]:
                    utils.logger.error(f"{__name__}: Variable {var} has value {values[0]}, which is not binary.")
                    raise Exception(f"Variable {var} has value {values[0]}, which is not binary.")
                # We return already, because we are supposed to match only one variable name
                # print("Returning values", values)
                return values

            if var.startswith(name_prefix):
                
                # If there are some parentheses in the variable name, we assume that the variable is indexed as var(0,...), var(1,...), ...
                if var.count("(") > 0:
                    # We extract the elements inside the parentheses, and remove the ' character from the elements
                    elements = [elem.strip("'") for elem in self.parse_var_name(var, name_prefix)]

                    if len(index_types) != len(elements):
                        raise Exception(f"We are getting the value of variable `{var}`, but the provided list of var_types `{index_types}` has different length.")

                    # We cast the elements to the appropriate types
                    tuple_index = tuple([index_types[i](elements[i]) for i in range(len(elements))])

                    values[tuple_index] = varValues[index]
                    if binary_values and round(values[tuple_index]) not in [0,1]:
                        utils.logger.error(f"{__name__}: Variable {var} has value {values[tuple_index]}, which is not binary.")
                        raise Exception(f"Variable {var} has value {values[tuple_index]}, which is not binary.")
                
                # If there are no parentheses in the variable name, we assume that the variable is indexed as var0, var1, ...
                else:
                    element = var.replace(name_prefix, "", 1)
                    if len(index_types) > 1:
                        utils.logger.error(f"{__name__}: We are getting the value of variable `{var}` for name_prefix `{name_prefix}`, with only one index `{element}`, but the provided list of var_types is not of length one `{index_types}`.")
                        raise Exception(f"We are getting the value of variable `{var}` for name_prefix `{name_prefix}`, with only one index `{element}`, but the provided list of var_types is not of length one `{index_types}`.")

                    elem_index = index_types[0](element)
                    values[elem_index] = varValues[index]
                    if (
                        binary_values 
                        and round(values[elem_index]) not in [0,1]
                    ):
                        utils.logger.error(f"{__name__}: Variable {var} has value {values[elem_index]}, which is not binary.")
                        raise Exception(f"Variable {var} has value {values[elem_index]}, which is not binary.")

        if binary_values:
            for key in values.keys():
                values[key] = round(values[key])

        return values

    def get_objective_value(self):
        """Return objective value of last solve.

        Returns
        -------
        float
            Objective value according to the configured optimization sense.
        """
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
            `if x in [ranges[i][0], ranges[i][1]] then y = constants[i].`

        Assumptions:
            - The ranges must be non-overlapping. Otherwise, if x belongs to more ranges, the solver will choose one arbitrarily.
            - The value of x must be within the union of the ranges. Otherwise the solver will not find a feasible solution.
        
        This is modeled by:
        - introducing binary variables z[i] with sum(z) = 1,
        - for each piece i:
                `x >= L_i - M*(1 - z[i])`
                `x <= U_i + M*(1 - z[i])`
                `y <= constant[i] + M*(1 - z[i])`
                `y >= constant[i] - M*(1 - z[i])`

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
            utils.logger.error(f"{__name__}: The length of `ranges` and `constants` must be the same.")
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

    def _timeout_handler(self, signum, frame):
        """Internal: mark *custom* timeout occurrence.

        Sets ``did_timeout`` which is later consulted by ``get_model_status``.
        """
        self.did_timeout = True
        # raise TimeoutException("Function timed out!")

    def fix_variable(self, var, value: Union[int, float]):
        """Fix an existing variable to a constant value by tightening its bounds.

        This avoids adding an explicit equality constraint (var == value) which can
        slow down solving compared to changing bounds directly.

        Parameters
        ----------
        var : backend variable object
            The variable returned previously by ``add_variables``.
        value : int | float
            The value to which the variable should be fixed.
        """
        # Normalize to float for solvers expecting floating bounds
        value = float(value)
        if self.external_solver == "gurobi":
            # Gurobi exposes direct LB / UB attributes
            try:
                var.LB = value
                var.UB = value
            except Exception as e:
                utils.logger.error(f"{__name__}: Could not fix gurobi variable: {e}")
                raise
        elif self.external_solver == "highs":
            # HiGHS: change column bounds using internal index of variable
            try:
                # Attempt a few common attribute names to locate the column index
                idx = None
                for cand in ["index", "col", "idx"]:
                    if hasattr(var, cand):
                        idx = getattr(var, cand)
                        break
                if idx is None:
                    raise AttributeError("Variable has no index attribute among ['index','col','idx']")
                # Ensure numpy imported (already imported as np at top)
                self.solver.changeColsBounds(
                    1,
                    np.array([idx], dtype=np.int32),
                    np.array([value], dtype=np.float64 if isinstance(value, float) else np.int32),
                    np.array([value], dtype=np.float64 if isinstance(value, float) else np.int32),
                )
            except Exception as e:
                utils.logger.error(f"{__name__}: Could not fix highs variable: {e}")
                raise

    def _run_with_timeout(self, timeout, func):
        """Execute ``func`` with an additional coarse timeout.

        A POSIX ``SIGALRM`` is armed for ``timeout`` (ceil) seconds. When it
        triggers we simply set ``did_timeout`` and allow control to return.
        Non-POSIX platforms currently fall back silently to just running the
        function (because signals are not available under Windows).

        Parameters
        ----------
        timeout : float
            Seconds before alarm.
        func : callable
            Zero-argument function (typically ``self.solver.optimize``).
        """
        # Use signal-based timeout on Unix-like systems
        if os.name == 'posix':
            signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(math.ceil(timeout))  # Schedule the timeout alarm
            try:
                utils.logger.debug(f"{__name__}: Running the solver with integer timeout from the signal module (timeout {math.ceil(timeout)} sec)")
                func()
            except Exception as e:
                pass
            finally:
                signal.alarm(0)  # Disable alarm after execution



class HighsCustom(highspy.Highs):
    """Thin subclass of ``highspy.Highs`` exposing a no-solve objective setter.

    The stock ``Highs`` object couples ``minimize`` / ``maximize`` with an
    immediate solve. For modelling convenience we sometimes want to *build* a
    model incrementally and set/replace an objective multiple times before the
    first solve. ``set_objective_without_solving`` mirrors the internal logic of
    ``Highs.minimize`` / ``Highs.maximize`` sans the final call to ``solve``.
    """

    def __init__(self):
        super().__init__()

    def set_objective_without_solving(self, obj, sense: str = "minimize") -> None:
        """Set objective coefficients and sense without triggering ``solve``.

        Parameters
        ----------
        obj : linear expression
            Must be a linear expression (a single variable should be wrapped
            by the caller). Inequality expressions are rejected.
        sense : {"minimize", "min", "maximize", "max"}, default "minimize"
            Optimization direction.

        Raises
        ------
        Exception
            If the provided expression encodes an inequality.
        ValueError
            If ``sense`` is invalid.
        """

        if obj is not None:
            # if we have a single variable, wrap it in a linear expression
            # expr = highspy.highs_linear_expression(obj) if isinstance(obj, highspy.highs_var) else obj
            expr = obj

            if expr.bounds is not None:
                raise Exception("Objective cannot be an inequality")

            # reset objective
            super().changeColsCost(
                self.numVariables,
                np.arange(self.numVariables, dtype=np.int32),
                np.full(self.numVariables, 0, dtype=np.float64),
            )

            # if we have duplicate variables, add the vals
            idxs, vals = expr.unique_elements()
            super().changeColsCost(len(idxs), idxs, vals)
            super().changeObjectiveOffset(expr.constant or 0.0)

        if sense in ["minimize", "min"]:
            super().changeObjectiveSense(highspy.ObjSense.kMinimize)
        elif sense in ["maximize", "max"]:
            super().changeObjectiveSense(highspy.ObjSense.kMaximize)
        else:
            raise ValueError(f"Invalid objective sense: {sense}. Use 'minimize' or 'maximize'.")