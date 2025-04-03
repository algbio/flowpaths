import flowpaths as fp

def example1():
    numbers = [2,4,6,7,9]
    total=13

    mgs_solver = fp.MinGenSet(
        numbers,
        total=total,
        weight_type=int,
        # remove_sums_of_two=False,
        # remove_complement_values=False,
        )
    
    mgs_solver.solve()
    process_solution(mgs_solver)

def example2():
    numbers = [2,4,6,7,9]
    total=13
    partition_constraints = [[6,4,3]]

    mgs_solver = fp.MinGenSet(
        numbers,
        total=total,
        weight_type=int,
        partition_constraints=partition_constraints,
        # remove_sums_of_two=False,
        # remove_complement_values=False,
        )
    
    mgs_solver.solve()
    process_solution(mgs_solver)

def process_solution(model: fp.MinGenSet):
    if model.is_solved():
        print(model.get_solution())
    else:
        print("Model could not be solved.")
    print(model.solve_statistics)

if __name__ == "__main__":
    example1()
    example2()