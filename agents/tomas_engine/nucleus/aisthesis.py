import numpy as np
from typing import List, Tuple
from dataclasses import dataclass

from agents.structs import FrameData

# services
from agents.services.gemini_service import GeminiService

# utils
from agents.image_utils import grid_to_image, display_image_in_iterm2

# constants
from agents.tomas_engine.constants import get_action_name


@dataclass
class ObjectInfo:
    """Structure to store object information"""

    object_id: str
    shape: str
    color: str
    positions: List[Tuple[int, int]]
    bounds: Tuple[int, int, int, int]  # (min_row, max_row, min_col, max_col)
    region: str
    size: int


class NucleiAisthesis:
    """Nuclei Aisthesis"""

    # Color mapping from spatial perception module
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

    # Region definitions
    REGION_BOUNDS = {
        "top-left": (0, 21, 0, 21),
        "top-center": (0, 21, 21, 43),
        "top-right": (0, 21, 43, 64),
        "center-left": (21, 43, 0, 21),
        "center": (21, 43, 21, 43),
        "center-right": (21, 43, 43, 64),
        "bottom-left": (43, 64, 0, 21),
        "bottom-center": (43, 64, 21, 43),
        "bottom-right": (43, 64, 43, 64),
    }

    def __init__(self):
        self.gemini_service = GeminiService()

    def analyze_action_effect(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
        executed_actions: List[str] = None,
    ) -> str:
        """Analyze the effect of an action sequence by comparing before and after states using objective object detection."""
        print(f"🏞️ AISTHESIS is analyzing action effect...")

        # Get current state (after all actions)
        current_state = latest_frame.frame

        # Determine how many frames back to compare based on executed actions
        if executed_actions and len(executed_actions) > 1:
            # Multiple actions executed, compare with state before the sequence
            frames_back = (
                len(executed_actions) + 1
            )  # +1 because frames[-1] is latest, frames[-2] is previous
            if len(frames) >= frames_back:
                previous_state = frames[-frames_back].frame
                action_description = f"sequence of {len(executed_actions)} actions: {', '.join(executed_actions)}"
                print(
                    f"🔄 Comparing current state with {frames_back-1} frames ago (before {len(executed_actions)}-action sequence)"
                )
            else:
                # Fallback if not enough frames
                previous_state = frames[-2].frame
                action_description = f"sequence: {', '.join(executed_actions)}"
                print(f"⚠️ Not enough frames for full comparison, using previous frame")
        else:
            # Single action or no action info, use previous frame
            previous_state = frames[-2].frame
            action_description = get_action_name(latest_frame.action_input.id.value)
            print(f"🔄 Comparing current state with previous frame (single action)")

        # Check if this is a level transition by comparing scores
        current_score = latest_frame.score
        previous_score = frames[-2].score
        is_level_transition = current_score > previous_score

        if is_level_transition:
            print(
                f"🎉 Level transition detected! Score: {previous_score} → {current_score}"
            )

            # display the new level state
            print(f"\n🖼️ NEW LEVEL STATE:")
            image_after = grid_to_image(current_state)
            display_image_in_iterm2(image_after)

            # For level transitions, report the new level state without comparison
            return f"🎉 LEVEL UP! Score increased from {previous_score} to {current_score}.\n\nStarted new level - ready for object detection in new environment!"

        else:
            # Normal single-level frame - use spatial perception for objective analysis
            # Normalize matrices to 2D format
            current_state_2d = self._normalize_to_2d(current_state)
            previous_state_2d = self._normalize_to_2d(previous_state)

            print(f"\n🔍 Using objective object detection...")

            # Detect objects in both states
            try:
                objects_before = self._detect_objects_in_matrix(previous_state_2d)
                objects_after = self._detect_objects_in_matrix(current_state_2d)

                # Compare objects to find changes
                changed_objects, unchanged_objects = self._compare_objects(
                    objects_before, objects_after
                )

                # Check if there are any changes
                if not changed_objects and not objects_before and not objects_after:
                    return f"That action ({action_description}) generated no effect on the environment."

                # Generate objective analysis
                objective_analysis = self._generate_object_analysis(
                    changed_objects, unchanged_objects, action_description
                )

                # Build prompt with objective data
                prompt = self._build_aisthesis_prompt(
                    action_description, objective_analysis, executed_actions
                )

                # Generate images for Gemini analysis
                image_before = grid_to_image(previous_state)
                image_after = grid_to_image(current_state)

                print(f"\n🖼️ BEFORE: {action_description}")
                display_image_in_iterm2(image_before)

                print(f"\n🖼️ AFTER: {action_description}")
                display_image_in_iterm2(image_after)

                # Send to Gemini for object-focused analysis
                aisthesis_response = self.gemini_service.generate_with_images_sync(
                    prompt, images=[image_before, image_after]
                )

                # print(f"\n🔍 AISTHESIS RESPONSE:")
                # print(aisthesis_response.content)

                return aisthesis_response.content

            except Exception as e:
                print(f"⚠️ Error in objective object analysis: {e}")
                return f"Error in objective object analysis: {e}"

    def _normalize_to_2d(self, matrix):
        """Normalize matrix to 2D format."""
        if isinstance(matrix[0][0], list):
            # 3D matrix - use first layer
            return matrix[0]
        else:
            # Already 2D matrix
            return matrix

    def _detect_objects_in_matrix(self, matrix: List[List[int]]) -> List[ObjectInfo]:
        """Detect all objects (connected components) in a matrix using flood fill."""
        try:
            matrix_array = np.array(matrix)
            if matrix_array.ndim != 2:
                matrix_array = matrix_array.squeeze()
                if matrix_array.ndim != 2:
                    return []

            objects = []
            visited = np.zeros_like(matrix_array, dtype=bool)
            object_counter = 1

            for row in range(matrix_array.shape[0]):
                for col in range(matrix_array.shape[1]):
                    if (
                        not visited[row, col] and matrix_array[row, col] != 0
                    ):  # Non-background pixel
                        # Find connected component using flood fill
                        positions = self._flood_fill(
                            matrix_array, visited, row, col, matrix_array[row, col]
                        )

                        if positions:  # Only create object if positions found
                            obj_info = self._create_object_info(
                                positions, matrix_array[row, col], object_counter
                            )
                            objects.append(obj_info)
                            object_counter += 1

            return objects

        except Exception as e:
            print(f"❌ Error detecting objects: {e}")
            return []

    def _flood_fill(
        self,
        matrix: np.ndarray,
        visited: np.ndarray,
        start_row: int,
        start_col: int,
        target_color: int,
    ) -> List[Tuple[int, int]]:
        """Flood fill algorithm to find connected components."""
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
            stack.extend(
                [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]
            )

        return positions

    def _create_object_info(
        self, positions: List[Tuple[int, int]], color_value: int, object_id: int
    ) -> ObjectInfo:
        """Create ObjectInfo from positions and color."""
        if not positions:
            return None

        rows = [pos[0] for pos in positions]
        cols = [pos[1] for pos in positions]

        min_row, max_row = min(rows), max(rows)
        min_col, max_col = min(cols), max(cols)

        # Determine shape
        width = max_col - min_col + 1
        height = max_row - min_row + 1
        size = len(positions)

        if size == 1:
            shape = "pixel"
        elif width == 1:
            shape = f"vertical-line-{height}"
        elif height == 1:
            shape = f"horizontal-line-{width}"
        elif size == width * height:
            if width == height:
                shape = f"square-{width}x{height}"
            else:
                shape = f"rectangle-{width}x{height}"
        else:
            shape = f"complex-{size}pixels"

        # Determine region
        center_row = (min_row + max_row) // 2
        center_col = (min_col + max_col) // 2
        region = self._get_region_for_position(center_row, center_col)

        # Get color name
        color_name = self.COLOR_NAMES.get(color_value % 17, f"color-{color_value}")

        return ObjectInfo(
            object_id=f"OBJ_{object_id}",
            shape=shape,
            color=color_name,
            positions=positions,
            bounds=(min_row, max_row, min_col, max_col),
            region=region,
            size=size,
        )

    def _get_region_for_position(self, row: int, col: int) -> str:
        """Get region name for a given position."""
        for region_name, (
            row_start,
            row_end,
            col_start,
            col_end,
        ) in self.REGION_BOUNDS.items():
            if row_start <= row < row_end and col_start <= col < col_end:
                return region_name
        return "unknown"

    def _compare_objects(
        self, objects_before: List[ObjectInfo], objects_after: List[ObjectInfo]
    ) -> Tuple[List[ObjectInfo], List[ObjectInfo]]:
        """Compare objects between two states and return changed and unchanged objects."""
        unchanged_objects = []
        changed_objects = []

        # Create a set of object signatures for quick comparison
        def object_signature(obj: ObjectInfo) -> str:
            # Sort positions for consistent comparison
            sorted_positions = tuple(sorted(obj.positions))
            return f"{obj.color}_{obj.shape}_{sorted_positions}"

        before_signatures = {object_signature(obj): obj for obj in objects_before}
        after_signatures = {object_signature(obj): obj for obj in objects_after}

        # Find unchanged objects (exist in both states with same signature)
        for signature, obj_before in before_signatures.items():
            if signature in after_signatures:
                # Object unchanged - use the "after" version for consistency
                unchanged_objects.append(after_signatures[signature])
            else:
                # Object changed or disappeared
                changed_objects.append(obj_before)

        # Find new objects (exist in after but not in before)
        for signature, obj_after in after_signatures.items():
            if signature not in before_signatures:
                changed_objects.append(obj_after)

        return changed_objects, unchanged_objects

    def _generate_object_analysis(
        self,
        changed_objects: List[ObjectInfo],
        unchanged_objects: List[ObjectInfo],
        action_description: str,
    ) -> str:
        """Generate objective object analysis."""
        analysis = f"🔍 OBJECTIVE OBJECT ANALYSIS FOR: {action_description}\n\n"

        # Changed objects
        if changed_objects:
            analysis += f"📝 CHANGED OBJECTS ({len(changed_objects)} total):\n"
            for i, obj in enumerate(changed_objects, 1):
                analysis += f"  {i}. {obj.object_id}: {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"
                analysis += f"     Bounds: rows {obj.bounds[0]}-{obj.bounds[1]}, cols {obj.bounds[2]}-{obj.bounds[3]}\n"
        else:
            analysis += "📝 CHANGED OBJECTS: None\n"

        # Unchanged objects
        if unchanged_objects:
            analysis += f"\n⚡ UNCHANGED OBJECTS ({len(unchanged_objects)} total):\n"
            for i, obj in enumerate(unchanged_objects, 1):
                analysis += f"  {i}. {obj.object_id}: {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"
                analysis += f"     Bounds: rows {obj.bounds[0]}-{obj.bounds[1]}, cols {obj.bounds[2]}-{obj.bounds[3]}\n"
        else:
            analysis += "\n⚡ UNCHANGED OBJECTS: None\n"

        # Summary
        total_objects = len(changed_objects) + len(unchanged_objects)
        if total_objects > 0:
            unchanged_percentage = (len(unchanged_objects) / total_objects) * 100
            analysis += f"\n📊 OBJECT SUMMARY:\n"
            analysis += f"  • Total objects detected: {total_objects}\n"
            analysis += f"  • Objects that changed: {len(changed_objects)}\n"
            analysis += f"  • Objects that remained: {len(unchanged_objects)} ({unchanged_percentage:.1f}%)\n"

        return analysis

    def _build_aisthesis_prompt(
        self,
        action_name: str,
        objective_analysis: str,
        executed_actions: List[str] = None,
    ) -> str:
        """Build the prompt for the Aisthesis module."""
        aisthesis_content = ""
        try:
            with open(
                "agents/tomas_engine/nucleus/aisthesis.md", "r", encoding="utf-8"
            ) as f:
                aisthesis_content = f.read()
        except FileNotFoundError:
            print("⚠️ Warning: aisthesis.md file not found")
            aisthesis_content = "Aisthesis module for objective object detection"
        except Exception as e:
            print(f"⚠️ Error reading aisthesis.md: {e}")
            aisthesis_content = "Aisthesis module for objective object detection"

        # Add sequence information if multiple actions
        sequence_info = ""
        if executed_actions and len(executed_actions) > 1:
            sequence_info = f"""
## EXECUTED ACTION SEQUENCE
{' → '.join(executed_actions)}
(Comparing state before the entire sequence with state after all actions completed)
"""
        else:
            sequence_info = f"""
## EXECUTED ACTION
{action_name}
"""

        prompt = f"""
{aisthesis_content}

{sequence_info}

## MATHEMATICAL OBJECT ANALYSIS
{objective_analysis}

## TASK
Based on the mathematical analysis above and the BEFORE/AFTER images provided, detect and report objects in the format specified in the prompt. Focus on objective object detection - what objects exist, their properties, and how they changed.
"""
        return prompt
