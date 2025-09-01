# Subset constraints in general graphs

!!! info inline end "See also"

    - [Subpath constraints in DAGs](subpath-constraints.md)

To any of the models on directed graphs (possibly with cycles) that are based on (or inherit from) the [AbstractWalkModelDiGraph](abstract-walk-model.md) class you can add *subset constraints*. As opposed to the [subpath constraints](subpath-constraints.md) that you can add for directed **acyclic** graphs, here they mean the following.

Say that you have prior knowledge of some **set of edges** that *must* appear together in at least one solution walk of you model. These *constrain* the space of possible solution walks.

Let's consider the [Minimum Flow Decomposition](minimum-flow-decomposition-cycles.md) problem in graphs with cycles, and let's take the example graph from there. Let's assume that you want the set `[(a,b),(c,a)]` (which we draw in brown) to appear in at last one solution walk. 

``` mermaid
flowchart LR
    s((s))
    a((a))
    t((t))
    b((b))
    c((c))

    s -->|7| a
    a -->|7| t
    a -->|5| b
    b -->|5| a
    a -->|2| c
    c -->|2| a
    linkStyle 2,5 stroke:brown,stroke-width:3;
```

For example, the following flow decomposition doesn't contain the full set `[(a,b),(c,a)]`, in the sense that neither red nor blue walks contain it.

``` mermaid
flowchart LR
    s((s))
    a((a))
    t((t))
    b((b))
    c((c))

    s -->|5| a
    a -->|5| t
    a -->|5| b
    b -->|5| a


    s -->|2| a
    a -->|2| c
    c -->|2| a
    a -->|2| t
    linkStyle 0,1,2,3 stroke:red,stroke-width:3;
    linkStyle 4,5,6,7 stroke:blue,stroke-width:3;
```

A valid decomposition that contains it, and has the minimum number of walks among these, is the following. Note that `[(a,b),(c,a)]` now appears in the orange walk.

Note also that if the orange walk is $s$, $a$, $c$, $a$, $b$, $a$, $t$ then it does not contain the edges in the order `(a,b),(c,a)`. In fact, the subpath constraints cannot guarantee any order in which the edges in the set appear in a walk containing them.

``` mermaid
flowchart LR
    s((s))
    a((a))
    t((t))
    b((b))
    c((c))

    s -->|3| a
    a -->|3| t
    s -->|2| a
    a -->|2| t
    a -->|2| b
    b -->|2| a
    a -->|3| b
    b -->|3| a


    s -->|2| a
    a -->|2| c
    c -->|2| a
    a -->|2| t
    linkStyle 2,4,5,9,10,3 stroke:orange,stroke-width:3;
    linkStyle 0,6,7,1 stroke:red,stroke-width:3;
    linkStyle 8,11 stroke:blue,stroke-width:3;
```

!!! tip "Note 1"
    Any existing decomposition model based on [AbstractWalkModelDiGraph](abstract-walk-model.md) supports subset constraints.

!!! tip "Note 2" 
    
    - The subset constraints can be any set of edges that don't necessarily share endpoints. 
    - The model does not guarantee that the edges in a subset constraint appear in a solution walk in any given order. It is only guaranteed that at least one solution walk contain this sequence of edges.