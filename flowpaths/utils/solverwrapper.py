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
import warnings

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

        # Pending bound updates to apply in batch before solving
        # Stores backend variables directly
        self._pending_fix_vars = []      # list[var]
        self._pending_fix_vals = []      # list[float]
        self._pending_lb_vars = []       # list[var]
        self._pending_lb_vals = []       # list[float]

    def queue_fix_variable(self, var, value: Union[int, float]):
        """Queue a variable to be fixed (LB=UB=value) in a later batch update."""
        self._pending_fix_vars.append(var)
        self._pending_fix_vals.append(float(value))

    def queue_set_var_lower_bound(self, var, lb: Union[int, float]):
        """Queue a variable to have its lower bound raised to ``lb`` in batch."""
        self._pending_lb_vars.append(var)
        self._pending_lb_vals.append(float(lb))

    def _apply_pending_bound_updates(self):
        """Apply any queued bound fixes/updates in a backend-specific batched way."""
        try:
            # Nothing to do fast exit
            if not (self._pending_fix_vars or self._pending_lb_vars):
                return

            if self.external_solver == "gurobi":
                import gurobipy as gp
                if self._pending_fix_vars:
                    self.solver.setAttr(gp.GRB.Attr.LB, self._pending_fix_vars, self._pending_fix_vals)
                    self.solver.setAttr(gp.GRB.Attr.UB, self._pending_fix_vars, self._pending_fix_vals)
                if self._pending_lb_vars:
                    self.solver.setAttr(gp.GRB.Attr.LB, self._pending_lb_vars, self._pending_lb_vals)
                self.solver.update()

            elif self.external_solver == "highs":
                # HiGHS batched updates
                import numpy as np  # local alias to ensure available
                if self._pending_fix_vars:
                    idxs = np.array([v.index for v in self._pending_fix_vars], dtype=np.int32)
                    vals = np.array(self._pending_fix_vals, dtype=np.float64)
                    self.solver.changeColsBounds(len(idxs), idxs, vals, vals)
                if self._pending_lb_vars:
                    idxs = np.array([v.index for v in self._pending_lb_vars], dtype=np.int32)
                    lbs  = np.array(self._pending_lb_vals, dtype=np.float64)
                    # Prefer dedicated lower bound update if available, else fall back to bounds change with UB unchanged
                    if hasattr(self.solver, "changeColsLower"):
                        self.solver.changeColsLower(len(idxs), idxs, lbs)
                    else:
                        # As a conservative fallback, raise LB via changeColsBounds using current UBs fetched via getCols
                        status, nret, lowers, uppers, costs, nnz = self.solver.getCols(len(idxs), idxs)
                        # Use returned uppers in the same order as idxs
                        current_ubs = uppers.astype(np.float64, copy=False)
                        self.solver.changeColsBounds(len(idxs), idxs, lbs, current_ubs)

        finally:
            # Clear queues regardless of success
            self._pending_fix_vars.clear()
            self._pending_fix_vals.clear()
            self._pending_lb_vars.clear()
            self._pending_lb_vals.clear()

    def add_variables(self, indexes, name_prefix: str, lb=0, ub=1, var_type="integer"):
        """Create a set of variables sharing a common name prefix.

        !!! warning "Important: Avoid collisions!"
        
            This function does not track or enforce unique/non-overlapping
            prefixes. The caller is responsible for choosing prefixes that do not
            create ambiguous names when mixed with other variables.

        Parameters
        ----------
        indexes : iterable
            Iterable of index labels (numbers or hashables) used *only* to
            suffix the variable names for uniqueness.
        name_prefix : str
            Prefix for each created variable (e.g. ``x_``). Must be unique with
            respect to existing prefixes (no prefix / super-prefix relations).
        lb, ub : float | dict | sequence, default (0, 1)
            Lower and upper bounds for created variables. Can be:
            - scalars (applied to all indexes), or
            - dicts mapping each index -> bound, or
            - sequences aligned with ``indexes`` order (same length).
        var_type : {"integer", "continuous"}, default "integer"
            Variable domain type.

        Returns
        -------
        dict | list
            Mapping from provided index to underlying solver variable objects
            (HiGHS returns an internal structure; Gurobi returns a dict).

        """
        
    # No internal tracking of prefixes; caller must avoid collisions.
        
        # Normalize bounds to per-index arrays when necessary
        def _materialize_bounds(param, default_value, param_name):
            # scalar
            if isinstance(param, (int, float)):
                return [float(param)] * len(indexes)
            # dict mapping index -> value
            if isinstance(param, dict):
                vals = []
                missing = []
                for idx in indexes:
                    if idx in param:
                        vals.append(float(param[idx]))
                    else:
                        missing.append(idx)
                if missing:
                    utils.logger.error(f"{__name__}: Missing {param_name} for indexes: {missing[:3]}{'...' if len(missing)>3 else ''}")
                    raise ValueError(f"Missing {param_name} for some indexes")
                return vals
            # sequence aligned with indexes
            try:
                seq = list(param)
                if len(seq) != len(indexes):
                    utils.logger.error(f"{__name__}: Length of {param_name} ({len(seq)}) does not match number of indexes ({len(indexes)}).")
                    raise ValueError(f"Length of {param_name} does not match number of indexes.")
                return [float(x) for x in seq]
            except TypeError:
                # Not iterable; fall back to default scalar for all
                return [float(default_value)] * len(indexes)

        lbs = _materialize_bounds(lb, 0.0, "lb")
        ubs = _materialize_bounds(ub, 1.0, "ub")

        if self.external_solver == "highs":

            var_type_map = {
                "integer": highspy.HighsVarType.kInteger,
                "continuous": highspy.HighsVarType.kContinuous,
            }
            return self.solver.addVariables(
                indexes, 
                lb=lbs, 
                ub=ubs, 
                type=var_type_map[var_type], 
                name_prefix=name_prefix)
        elif self.external_solver == "gurobi":
            import gurobipy

            var_type_map = {
                "integer": gurobipy.GRB.INTEGER,
                "continuous": gurobipy.GRB.CONTINUOUS,
            }
            # Single batched call using keys with per-index bounds
            keys = list(indexes)
            lb_map = {idx: float(lbs[pos]) for pos, idx in enumerate(keys)}
            ub_map = {idx: float(ubs[pos]) for pos, idx in enumerate(keys)}

            vars_td = self.solver.addVars(
                keys,
                lb=lb_map,
                ub=ub_map,
                vtype=var_type_map[var_type],
                name=name_prefix,
            )
            # Keep model in a consistent state
            self.solver.update()
            return vars_td

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
        # Apply any queued bound updates right before solving
        self._apply_pending_bound_updates()

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
        """Parse a variable name and extract indices inside parentheses or brackets.

        Supported forms:
        - ``<prefix>(i,j,...)`` (HiGHS style / tuple repr)
        - ``<prefix>[i,j,...]`` (Gurobi addVars style)
        - Single-suffix names ``<prefix><i>`` are handled elsewhere.

    Returns a list of raw index components as strings (quotes stripped).
    Commas inside nested parentheses/brackets are treated as part of the
    component, e.g. ``var((a,b))`` -> ["(a,b)"].
        """
        # Try parentheses first
        match = re.match(rf"{re.escape(name_prefix)}\(\s*(.*?)\s*\)$", string)
        if match:
            components_str = match.group(1)
        else:
            # Try square brackets (Gurobi addVars style)
            match = re.match(rf"{re.escape(name_prefix)}\[\s*(.*?)\s*\]$", string)
            if match:
                components_str = match.group(1)
            else:
                # Not a structured name for this prefix
                return None

        # Split at top-level commas only; keep commas inside nested () or []
        if components_str.strip() == "":
            return []

        components = []
        buf = []
        in_quote = False
        depth_paren = 0
        depth_brack = 0

        for ch in components_str:
            if in_quote:
                buf.append(ch)
                if ch == "'":
                    in_quote = False
                continue

            if ch == "'":
                in_quote = True
                buf.append(ch)
                continue

            if ch == '(':
                depth_paren += 1
                buf.append(ch)
                continue
            if ch == ')' and depth_paren > 0:
                depth_paren -= 1
                buf.append(ch)
                continue
            if ch == '[':
                depth_brack += 1
                buf.append(ch)
                continue
            if ch == ']' and depth_brack > 0:
                depth_brack -= 1
                buf.append(ch)
                continue

            if ch == ',' and depth_paren == 0 and depth_brack == 0:
                token = ''.join(buf).strip()
                if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
                    token = token[1:-1]
                components.append(token)
                buf = []
            else:
                buf.append(ch)

        # Flush last token
        token = ''.join(buf).strip()
        if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
            token = token[1:-1]
        if token != "" or components_str.strip() != "":
            components.append(token)

        return components


    def get_variable_values(
        self, name_prefix, index_types: list, binary_values: bool = False 
    ) -> dict:
        """
        !!! warning "Deprecated"

            Use `get_values(...)` instead.

        Retrieve the values of variables belonging to a given prefix.

        This method matches variables using one of these forms for the given
        ``name_prefix``:
        - Structured names: ``<prefix>(i, j, ...)`` or ``<prefix>[i, j, ...]``
        - Legacy single numeric suffix: ``<prefix>k`` or ``<prefix>_k``
        - Exact scalar variable name: ``<prefix>`` (when ``index_types`` is empty)

        Under these rules, overlapping prefixes (e.g., ``x`` and ``x_long``)
        won't interfere with each other. Callers must still avoid custom ad-hoc
        naming that mimics these patterns for different variables.

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
        # Emit a deprecation warning (hidden by default unless enabled by filters)
        warnings.warn(
            "SolverWrapper.get_variable_values is deprecated and will be removed in a future release. "
            "Use SolverWrapper.get_values(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        varNames = self.get_all_variable_names()
        varValues = self.get_all_variable_values()

        values: dict = {}

        def _cast_components(comps, types):
            casted = []
            for c, t in zip(comps, types):
                if t is int:
                    casted.append(int(c))
                elif t is float:
                    casted.append(float(c))
                elif t is str:
                    casted.append(str(c))
                else:
                    casted.append(t(c))
            if len(casted) == 0:
                return ()
            if len(casted) == 1:
                return casted[0]
            return tuple(casted)

        simple_numeric = re.compile(r"^-?\d+$")

        for i, var in enumerate(varNames):
            val = varValues[i]

            # Scalar exact name
            if not index_types:
                if var == name_prefix:
                    values[0] = val
                    if binary_values:
                        rv = int(round(values[0]))
                        if rv not in (0, 1):
                            raise Exception(f"Variable {var} has value {values[0]}, which is not binary.")
                        values[0] = rv
                    # exact scalar match is unique
                    continue
                else:
                    continue

            # Structured prefix(name) or prefix[name]
            comps = self.parse_var_name(var, name_prefix)
            if comps is not None:
                if len(comps) != len(index_types):
                    # Ignore mismatched arity
                    continue
                try:
                    key = _cast_components(comps, index_types)
                except Exception:
                    # Skip if casting fails
                    continue
                values[key] = val
                continue

            # Legacy numeric suffix: prefix<idx> or prefix_<idx>
            if len(index_types) == 1 and var.startswith(name_prefix):
                suffix = var[len(name_prefix):]
                if suffix.startswith("_"):
                    suffix_try = suffix[1:]
                else:
                    suffix_try = suffix
                if simple_numeric.match(suffix_try):
                    try:
                        key = _cast_components([suffix_try], index_types)
                        values[key] = val
                    except Exception:
                        pass

        if binary_values:
            tol = max(1e-9, getattr(self, "tolerance", 1e-9))
            for k, v in list(values.items()):
                rv = int(round(v))
                if rv not in (0, 1) or abs(v - rv) > tol:
                    raise Exception(f"Variable {name_prefix}{k if k!=0 else ''} has non-binary value {v}")
                values[k] = rv

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

    def get_values(self, variables, binary_values: bool = False) -> dict:
        """Return solution values for variables without name parsing.

        Parameters
        ----------
        variables : iterable | mapping
            Either an iterable of (index, variable) pairs, or a mapping where
            keys are indices and values are variable objects (e.g., a dict or
            a Gurobi tupledict).
        binary_values : bool, default False
            If True, round values to 0/1 and validate against tolerance.

        Returns
        -------
        dict
            Dictionary mapping each provided index to its solution value.

        Notes
        -----
        - For HiGHS, values are retrieved using the internal column index of each
          variable via a single call to ``allVariableValues``.
        - For Gurobi, values are read from ``Var.X``.
        - Indices are taken from the first element of each tuple in ``variables``
          (when an iterable of pairs is supplied). If a mapping is supplied,
          its items() are used.
        """
        # Prepare a value accessor per backend
        if self.external_solver == "highs":
            all_vals = self.get_all_variable_values()

            def _val_of(v):
                idx = getattr(v, "index", None)
                if idx is None:
                    raise Exception("HiGHS variable object missing 'index' attribute.")
                return all_vals[idx]
        elif self.external_solver == "gurobi":
            def _val_of(v):
                return v.X
        else:
            raise ValueError(f"Unsupported solver type '{self.external_solver}'.")

        def _maybe_round_binary(val):
            if not binary_values:
                return val
            tol = max(1e-9, getattr(self, "tolerance", 1e-9))
            rv = int(round(val))
            if rv not in (0, 1) or abs(val - rv) > tol:
                raise Exception(f"Variable has non-binary value {val}")
            return rv

        # Build an iterator of (index, variable) pairs
        try:
            pair_iter = variables.items()
        except AttributeError:
            # variables may already be an iterable of pairs or a mapping that
            # doesn't expose items(); handle both
            def _pair_gen():
                for elem in variables:
                    if isinstance(elem, tuple) and len(elem) == 2:
                        yield elem  # (index, var)
                    else:
                        # Assume elem is a key into a mapping supporting __getitem__
                        yield (elem, variables[elem])
            pair_iter = _pair_gen()

        result = {}
        for key, var in pair_iter:
            value = _val_of(var)
            result[key] = _maybe_round_binary(value)
        return result

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
                self.solver.changeColsBounds(
                    1,
                    np.array([var.index], dtype=np.int32),
                    np.array([value], dtype=np.float64 if isinstance(value, float) else np.int64),
                    np.array([value], dtype=np.float64 if isinstance(value, float) else np.int64),
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