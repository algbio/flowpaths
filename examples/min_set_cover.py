import flowpaths as fp

def main():
    universe = [1,2,3,4,5]
    subsets = [{1,2,3}, {2,4}, {3,5}, {1,4,5}]
    subset_weights = [1,2,1,1]

    msc_solver = fp.MinSetCover(
        universe=universe,
        subsets=subsets,
        subset_weights=subset_weights
        )
    
    msc_solver.solve()
    process_solution(msc_solver)

def process_solution(model: fp.MinGenSet):
    if model.is_solved():
        print(model.get_solution(as_subsets=True))
    else:
        print("Model could not be solved.")
    print(model.solve_statistics)

if __name__ == "__main__":
    main()