# An Optimization Routine for the Number of Paths

Models implemented with the class `AbstractPathModelDAG` assume a fixed number `k` of paths. This class provides an automatic method of iterating in an increasing manner over values of `k` to find the best one (i.e., when a stopping criterion has been met).

For example, our custom class for the [Minimum Flow Decomposition problem](minimum-flow-decomposition.md) could be emulated in this manner:

``` python
mfd_model = fp.NumPathsOptimization(
        model_type = fp.kFlowDecomp,
        stop_on_first_feasible=True,
        G=graph, 
        flow_attr="flow",
        )
```

If you want to pass additional parameters to the model, you can just add append them, for example:

``` python
mfd_model = fp.NumPathsOptimization(
        model_type = fp.kFlowDecomp,
        stop_on_first_feasible=True,
        G=graph, 
        flow_attr="flow",
        subpath_constraints=[[("a", "c"),("c", "t")]], 
        subpath_constraints_coverage=0.5, 
        optimization_options={"optimize_with_greedy": False}
        )
```

::: flowpaths.numpathsoptimization