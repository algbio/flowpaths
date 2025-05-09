# Abstract Path Model in DAGs

A general approach in developing a model to decompose a weighted graph into weighted paths is to:

1. Fix $k$, the number of paths. 
2. Formulate in ILP the $k$ paths; that is adding a set of $k$ variables and suitable constraints constraints such that the $i$-th set of variables encodes the $i$-th path.
3. Add additional variables, constraints, or set the objective function, that these paths must satisfy.
4. Iterate the above process for different values of $k$, until the "best" one is found ("best" depends on the problem). See [our implementation of a basic routine for this step](numpathsoptimization.md).

For step 2. above we provide the abstract class `AbstractPathModelDAG` which models a given number $k$ of paths in a given acyclic graph $G = (V,E)$. For simplicity, $G$ must have a single source $s$ and a single sink $t$, see our class [stDiGraph](stdigraph.md). (The `stDiGraph` class adds these automatically for any NetworkX DiGraph, and keeps track of their incident edges.) This approach appeared in [this paper](https://doi.org/10.1089/cmb.2022.0257).

More in detail, for every edge $(u,v) \in E$, and for every path index $i \in \{0,\dots,k-1\}$, we add a binary variable $x_{u,v,i} \in \{0,1\}$. We add constraints on these variables to ensure that for every $i$ the variables $x_{u,v,i}$ that equal 1 induce an $s$-$t$ path (i.e., a path from $s$ to $t$). In other words $x_{u,v,i} = 1$ if edge $(u,v)$ belongs to solution path $i$, and 0 otherwise. See [the paper](https://doi.org/10.1089/cmb.2022.0257) on the specific constraints that are added to enforce that they induce an $s$-$t$ path. 

For example, the edges in brown below induce an $s$-$t$ path (for say $i = 3$), and notice that the $x_{u,v,3}$ variables equal 1 only on the edges $(u,v)$ on the path.

``` mermaid
%%{init: {'themeVariables': { 'edgeLabelBackground': 'white'}}}%%
flowchart LR
    s((s))
    a((a))
    b((b))
    c((c))
    d((d))
    t((t))
    s -->|"$$x_{s,a,3} = 1$$"| a
    a -->|"$$x_{a,b,3} = 1$$"| b
    s -->|"$$x_{s,b,3} = 0$$"| b
    a -->|"$$x_{a,c,3} = 0$$"| c
    b -->|"$$x_{b,c,3} = 1$$"| c
    c -->|"$$x_{c,d,3} = 1$$"| d
    d -->|"$$x_{d,t,3} = 1$$"| t
    c -->|"$$x_{c,t,3} = 0$$"| t

    linkStyle 0,1,4,5,6 stroke:brown,stroke-width:3;
```

!!! note "The search for paths"
    
    - Note that we do not have the paths beforehand, and the ILP will search for paths (i.e. assignment of values to the $x_{u,v,i}$ variables, under the constraints that they induce a path). 
    - Once a class inherits from `AbstractPathModelDAG`, it will add other variables and constraints (as in **point 3.** above). The ILP solver will then search for the $k$ paths (i.e. find the values to the $x_{u,v,i}$ variables) to satisfy **all** constraints.

!!! example "Example: Modelling $k$-Flow Decomposition"

    Consider the problem of decomposing a network flow $f : E \rightarrow \mathbb{N}$ over a DAG $G = (V,E)$ into a given number $k$ of $s$-$t$ paths ([k-Flow Decomposition](k-flow-decomposition.md)). Assume we created the $x_{u,v,i}$ variables as above. Thus, we just need to implement **point 3.** above.
    
    - We introduce a variable $w_i$ (integer or continuous) modeling the weight of path $i$, for every $i \in \{0,\dots,k-1\}$.
    - We need to enforce the "flow explanation" constraint:
    $$
    f(u,v) = \sum_{i=0}^{k-1} x_i \cdot w_i, ~~\forall (u,v) \in E.
    $$
    Note that in the above $f(u,v)$ is a constant. Moreover, $x_i \cdot w_i$ is not a linear term (as required by an Integer Linear Program), but it can be easily linearized via additional variables and constraints. However, our `SolverWrapper` class provides the method [`add_binary_continuous_product_constraint()`](solver-wrapper.md#flowpaths.utils.solverwrapper.SolverWrapper.add_binary_continuous_product_constraint) to directly encode such a non-linear constraint, without bothering to manually set up these additional variables and constraints.

!!! info "The $x_{u,v,i}$ variables are implemented as `edge_vars[(u, v, i)]`, see the class documentation below."

::: flowpaths.abstractpathmodeldag
    options:
      filters: 
        - "!^_"
