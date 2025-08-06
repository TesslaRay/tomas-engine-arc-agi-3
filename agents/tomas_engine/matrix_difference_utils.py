import numpy as np
from typing import List


def calculate_matrix_difference(
    matrix_before: List[List[int]], matrix_after: List[List[int]]
) -> np.ndarray:
    """Calculate the difference between two matrices.
    
    Args:
        matrix_before: State before the change
        matrix_after: State after the change
        
    Returns:
        Numpy array representing the difference (after - before)
    """
    try:
        before = np.array(matrix_before, dtype=np.int32).squeeze()
        after = np.array(matrix_after, dtype=np.int32).squeeze()

        if before.shape != after.shape:
            print(
                f"❌ Error: Matrices have different dimensions - Before: {before.shape}, After: {after.shape}"
            )
            min_rows = (
                min(before.shape[0], after.shape[0])
                if before.ndim >= 1 and after.ndim >= 1
                else 1
            )
            min_cols = (
                min(before.shape[1], after.shape[1])
                if before.ndim >= 2 and after.ndim >= 2
                else 1
            )

            if before.ndim == 2 and after.ndim == 2:
                before = before[:min_rows, :min_cols]
                after = after[:min_rows, :min_cols]
            else:
                print("❌ Cannot reconcile dimensions, using default matrices")
                return np.zeros((64, 64), dtype=np.int32)

        if before.ndim != 2 or after.ndim != 2:
            print(
                f"❌ Error: Matrices are not 2D after processing - Before: {before.ndim}D, After: {after.ndim}D"
            )
            return np.zeros((64, 64), dtype=np.int32)

        return after - before

    except Exception as e:
        print(f"❌ Error calculating matrix difference: {e}")
        return np.zeros((64, 64), dtype=np.int32)