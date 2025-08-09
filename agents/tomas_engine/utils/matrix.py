import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass


# Color names mapping
COLOR_NAMES = {
    0: "white",
    1: "blue",
    2: "gray",
    3: "dark-gray",
    4: "darker-gray",
    5: "black",
    6: "brown",
    7: "light-gray",
    8: "red",
    9: "light-blue",
    10: "green",
    11: "yellow",
    12: "orange",
    13: "magenta",
    14: "light-green",
    15: "purple",
    16: "pink",
}


@dataclass
class SimpleObject:
    """Simple object representation"""

    id: str
    color: str
    positions: List[Tuple[int, int]]
    size: int
    center: Tuple[int, int]
    bounds: Tuple[int, int, int, int]  # (min_row, max_row, min_col, max_col)


def detect_simple_objects(matrix: List[List[int]]) -> List[SimpleObject]:
    """Detect simple objects (connected components) in a matrix."""
    try:
        matrix_array = np.array(matrix)
        if matrix_array.ndim == 3:
            matrix_array = matrix_array.squeeze()

        if matrix_array.ndim != 2:
            return []

        objects = []
        visited = np.zeros_like(matrix_array, dtype=bool)
        object_counter = 1

        for row in range(matrix_array.shape[0]):
            for col in range(matrix_array.shape[1]):
                if not visited[row, col] and matrix_array[row, col] != 0:
                    # Find connected component
                    positions = _flood_fill_simple(
                        matrix_array, visited, row, col, matrix_array[row, col]
                    )

                    if positions:
                        color_value = matrix_array[row, col]
                        color_name = COLOR_NAMES.get(
                            color_value % 17, f"color-{color_value}"
                        )

                        # Calculate bounds and center
                        rows = [pos[0] for pos in positions]
                        cols = [pos[1] for pos in positions]
                        min_row, max_row = min(rows), max(rows)
                        min_col, max_col = min(cols), max(cols)
                        center_row = (min_row + max_row) // 2
                        center_col = (min_col + max_col) // 2

                        obj = SimpleObject(
                            id=f"OBJ_{object_counter}",
                            color=color_name,
                            positions=positions,
                            size=len(positions),
                            center=(center_row, center_col),
                            bounds=(min_row, max_row, min_col, max_col),
                        )
                        objects.append(obj)
                        object_counter += 1

        return objects

    except Exception as e:
        print(f"❌ Error detecting objects: {e}")
        return []


def _flood_fill_simple(
    matrix: np.ndarray,
    visited: np.ndarray,
    start_row: int,
    start_col: int,
    target_color: int,
) -> List[Tuple[int, int]]:
    """Simple flood fill algorithm."""
    if (
        start_row < 0
        or start_row >= matrix.shape[0]
        or start_col < 0
        or start_col >= matrix.shape[1]
        or visited[start_row, start_col]
        or matrix[start_row, start_col] != target_color
    ):
        return []

    positions = []
    stack = [(start_row, start_col)]

    while stack:
        row, col = stack.pop()

        if (
            row < 0
            or row >= matrix.shape[0]
            or col < 0
            or col >= matrix.shape[1]
            or visited[row, col]
            or matrix[row, col] != target_color
        ):
            continue

        visited[row, col] = True
        positions.append((row, col))

        # Add 4-connected neighbors
        stack.extend([(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)])

    return positions


def compare_objects(
    objects_before: List[SimpleObject], objects_after: List[SimpleObject]
) -> Tuple[List[SimpleObject], List[SimpleObject]]:
    """Compare objects between two states."""
    unchanged_objects = []
    changed_objects = []

    def object_signature(obj: SimpleObject) -> str:
        sorted_positions = tuple(sorted(obj.positions))
        return f"{obj.color}_{sorted_positions}"

    before_signatures = {object_signature(obj): obj for obj in objects_before}
    after_signatures = {object_signature(obj): obj for obj in objects_after}

    # Find unchanged objects
    for signature, obj_before in before_signatures.items():
        if signature in after_signatures:
            unchanged_objects.append(after_signatures[signature])
        else:
            changed_objects.append(obj_before)

    # Find new objects
    for signature, obj_after in after_signatures.items():
        if signature not in before_signatures:
            changed_objects.append(obj_after)

    return changed_objects, unchanged_objects


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
        before = np.array(matrix_before, dtype=np.int32)
        after = np.array(matrix_after, dtype=np.int32)

        # Handle 3D arrays by squeezing extra dimensions
        if before.ndim == 3:
            before = before.squeeze()
        if after.ndim == 3:
            after = after.squeeze()

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


def analyze_pixel_changes(
    matrix_before: List[List[int]], matrix_after: List[List[int]]
) -> Dict:
    """Analyze changes between two matrices at pixel level.

    Args:
        matrix_before: State before the change
        matrix_after: State after the change

    Returns:
        Dictionary with change analysis data
    """
    difference_matrix = calculate_matrix_difference(matrix_before, matrix_after)

    if not np.any(difference_matrix != 0):
        return {
            "has_changes": False,
            "total_changes": 0,
            "change_positions": [],
            "appearances": 0,
            "disappearances": 0,
            "transformations": 0,
            "change_details": [],
        }

    # Get change positions
    change_positions = list(zip(*np.where(difference_matrix != 0)))

    # Classify changes
    before_array = np.array(matrix_before)
    after_array = np.array(matrix_after)

    # Fix 3D arrays by squeezing extra dimensions
    if before_array.ndim == 3:
        before_array = before_array.squeeze()
    if after_array.ndim == 3:
        after_array = after_array.squeeze()

    appearances = 0
    disappearances = 0
    transformations = 0
    change_details = []

    for i, (row, col) in enumerate(change_positions):
        if 0 <= row < before_array.shape[0] and 0 <= col < before_array.shape[1]:
            before_val = before_array[row, col]
            after_val = after_array[row, col]

            before_color = COLOR_NAMES.get(before_val % 17, f"color-{before_val}")
            after_color = COLOR_NAMES.get(after_val % 17, f"color-{after_val}")

            if before_val == 0 and after_val != 0:
                appearances += 1
                change_type = "appearance"
            elif before_val != 0 and after_val == 0:
                disappearances += 1
                change_type = "disappearance"
            else:
                transformations += 1
                change_type = "transformation"

            change_details.append(
                {
                    "position": (row, col),
                    "before": before_color,
                    "after": after_color,
                    "type": change_type,
                }
            )

    # Detect objects in both matrices
    objects_before = detect_simple_objects(matrix_before)
    objects_after = detect_simple_objects(matrix_after)

    # Compare objects
    changed_objects, unchanged_objects = compare_objects(objects_before, objects_after)

    return {
        "has_changes": True,
        "total_changes": len(change_positions),
        "change_positions": change_positions,
        "appearances": appearances,
        "disappearances": disappearances,
        "transformations": transformations,
        "change_details": change_details,
        "difference_matrix": difference_matrix,
        "objects_before": objects_before,
        "objects_after": objects_after,
        "changed_objects": changed_objects,
        "unchanged_objects": unchanged_objects,
    }


def get_simple_change_summary(
    matrix_before: List[List[int]], matrix_after: List[List[int]]
) -> str:
    """Get a simple text summary of changes between matrices.

    Args:
        matrix_before: State before the change
        matrix_after: State after the change

    Returns:
        Simple text summary of changes
    """
    analysis = analyze_pixel_changes(matrix_before, matrix_after)

    if not analysis["has_changes"]:
        return "No changes detected"

    summary = f"Detected {analysis['total_changes']} pixel changes:\n"

    if analysis["appearances"] > 0:
        summary += f"• {analysis['appearances']} pixels appeared\n"
    if analysis["disappearances"] > 0:
        summary += f"• {analysis['disappearances']} pixels disappeared\n"
    if analysis["transformations"] > 0:
        summary += f"• {analysis['transformations']} pixels changed color\n"

    # Object analysis
    if "unchanged_objects" in analysis and analysis["unchanged_objects"]:
        summary += (
            f"\n🔒 UNCHANGED OBJECTS ({len(analysis['unchanged_objects'])} total):\n"
        )
        for obj in analysis["unchanged_objects"][:5]:  # Show first 5
            center = obj.center
            bounds = obj.bounds
            summary += f"  • {obj.id}: {obj.color} object ({obj.size} pixels) at center ({center[0]},{center[1]}) bounds ({bounds[0]}-{bounds[1]}, {bounds[2]}-{bounds[3]})\n"
        if len(analysis["unchanged_objects"]) > 5:
            summary += f"  ... and {len(analysis['unchanged_objects']) - 5} more unchanged objects\n"

    if "changed_objects" in analysis and analysis["changed_objects"]:
        summary += f"\n🔄 CHANGED OBJECTS ({len(analysis['changed_objects'])} total):\n"
        for obj in analysis["changed_objects"][:5]:  # Show first 5
            center = obj.center
            bounds = obj.bounds
            summary += f"  • {obj.id}: {obj.color} object ({obj.size} pixels) at center ({center[0]},{center[1]}) bounds ({bounds[0]}-{bounds[1]}, {bounds[2]}-{bounds[3]})\n"
        if len(analysis["changed_objects"]) > 5:
            summary += f"  ... and {len(analysis['changed_objects']) - 5} more changed objects\n"

    # Show first few changes as examples
    if len(analysis["change_details"]) <= 10:
        summary += "\nChanges:\n"
        for i, change in enumerate(analysis["change_details"], 1):
            pos = change["position"]
            summary += (
                f"  {i}. ({pos[0]},{pos[1]}): {change['before']} → {change['after']}\n"
            )
    else:
        summary += f"\nFirst 10 changes:\n"
        for i, change in enumerate(analysis["change_details"][:10], 1):
            pos = change["position"]
            summary += (
                f"  {i}. ({pos[0]},{pos[1]}): {change['before']} → {change['after']}\n"
            )
        summary += f"... and {len(analysis['change_details']) - 10} more changes\n"

    return summary
