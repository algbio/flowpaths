import pytest
from flowpaths import MinGenSet

class TestMinGenSet:
    def test_init_remove_complement_values(self):
        """Test that complement values are properly removed during initialization."""
        numbers = [1, 2, 3, 4]
        total = 5
        
        # With remove_complement_values=True (default)
        mgs = MinGenSet(numbers=numbers, total=total)
        # Since 1+4=5 and 2+3=5, and 1<4 and 2<3, only 1 and 2 should remain
        assert sorted(mgs.numbers) == [1, 2]
        
    def test_init_remove_total_and_zero(self):
        """Test that values equal to total or 0 are removed."""
        numbers = [0, 2, 5]
        total = 5
        
        mgs = MinGenSet(numbers=numbers, total=total)
        assert sorted(mgs.numbers) == [2]  # 0 and 5 are removed
        
    def test_invalid_weight_type(self):
        """Test that an invalid weight_type raises a ValueError."""
        numbers = [1, 2, 3]
        total = 5
        
        with pytest.raises(ValueError, match="weight_type must be either"):
            MinGenSet(numbers=numbers, total=total, weight_type=str)
            
    def test_init_preserves_original_numbers(self):
        """Test that the original numbers list is preserved."""
        numbers = [1, 2, 3, 4]
        total = 5
        
        mgs = MinGenSet(numbers=numbers, total=total)
        # The numbers list is modified, but initial_numbers should be preserved
        assert mgs.initial_numbers == numbers
        assert mgs.numbers != numbers  # Should be modified due to remove_complement_values
        
    def test_partition_constraints_validation(self):
        """Test that partition constraints are properly validated."""
        numbers = [1, 2, 3]
        total = 6
        
        # Valid partition constraints (sums to total)
        valid_constraints = [[1, 5], [2, 4], [3, 3]]
        mgs1 = MinGenSet(numbers=numbers, total=total, partition_constraints=valid_constraints)
        
        # Invalid partition constraints (not a list of lists)
        invalid_constraints1 = [1, 2, 3]
        with pytest.raises(ValueError):
            MinGenSet(numbers=numbers, total=total, partition_constraints=invalid_constraints1)
        
        # Invalid partition constraints (sums don't equal total)
        invalid_constraints2 = [[1, 2], [2, 3]]  # Sums to 3 and 5, not 6
        with pytest.raises(ValueError, match="The sum of the numbers inside each subset constraint must equal the total value"):
            MinGenSet(numbers=numbers, total=total, partition_constraints=invalid_constraints2)
    
    def test_solve_and_get_solution_small_example(self):
        """Test solving a simple MinGenSet problem."""
        # Simple example with a known solution
        numbers = [1, 2, 3]
        total = 3
        
        mgs = MinGenSet(numbers=numbers, total=total)
        result = mgs.solve()
        
        # Verify the solve method returns True for a solvable problem
        assert result is True
        
        # Check that is_solved returns True
        assert mgs.is_solved() is True
        
        # Get the solution and verify it's correct
        solution = mgs.get_solution()
        assert solution is not None
        
        # The solution should be a generating set that sums to total
        # and can represent all numbers in the input
        assert sum(solution) == total
        
        # Verify the solve_statistics has the expected keys
        assert "solve_time" in mgs.solve_statistics
        assert "num_elements" in mgs.solve_statistics
        assert "status" in mgs.solve_statistics
    
    def test_check_is_solved_exception(self):
        """Test that check_is_solved raises an exception if model is not solved."""
        mgs = MinGenSet(numbers=[1, 2, 3], total=6)
        
        # Without calling solve(), check_is_solved should raise an exception
        with pytest.raises(Exception, match="Model not solved"):
            mgs.check_is_solved()
    
    def test_get_solution_before_solve(self):
        """Test that get_solution returns None before solving and raises an exception when checking."""
        mgs = MinGenSet(numbers=[1, 2, 3], total=6)
        
        # get_solution should call check_is_solved which raises an exception
        with pytest.raises(Exception, match="Model not solved"):
            mgs.get_solution()
    
    def test_int_weight_type(self):
        """Test MinGenSet with integer weight type."""
        numbers = [1, 2, 3]
        total = 3
        
        mgs = MinGenSet(numbers=numbers, total=total, weight_type=int)
        result = mgs.solve()
        
        assert result is True
        solution = mgs.get_solution()
        
        # Verify all elements in the solution are integers
        assert all(isinstance(val, int) for val in solution)