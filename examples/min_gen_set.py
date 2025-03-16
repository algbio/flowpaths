import flowpaths as fp

def main():
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

def process_solution(model: fp.MinGenSet):
    if model.is_solved():
        print(model.get_solution())
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()