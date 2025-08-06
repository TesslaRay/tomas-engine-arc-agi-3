# numpy for matrix operations
import numpy as np

# dataclasses for object info and change analysis
from dataclasses import dataclass

# typing for type hints
from typing import Optional, Tuple, List, Union

# utils
from ..image_utils import grid_to_image
from .utils.matrix_utils import calculate_matrix_difference

# services
from ..services.gemini_service import GeminiService
from ..services.cerebras_service import CerebrasService
from .constants import get_action_name


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


@dataclass
class ChangeAnalysis:
    """Structure to store detailed change analysis"""

    total_changes: int
    change_percentage: float
    appearances: int
    disappearances: int
    transformations: int
    regions_affected: List[str]
    near_coordinates: bool
    directional_consistency: Optional[str]
    change_positions: List[Tuple[int, int]]
    mathematical_analysis: str
    gemini_interpretation: Optional[str] = None
    # New fields for object detection
    changed_objects: List[ObjectInfo] = None
    unchanged_objects: List[ObjectInfo] = None
    all_objects_before: List[ObjectInfo] = None
    all_objects_after: List[ObjectInfo] = None


class SpatialPerceptionModule:
    """Spatial perception module that analyzes action effects on environment."""

    # Constants

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
        9: "ligth-blue",
        10: "green",
        11: "yellow",
        12: "orange",
        13: "magenta",
        14: "light-green",
        15: "purple",
        16: "pink",
    }

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

    def __init__(self, provider: str = "gemini"):
        """Initialize the spatial perception module.

        Args:
            provider: AI provider to use ("gemini" or "cerebras")
        """
        self.provider = provider.lower()
        self.llm_service = None

        # Initialize selected service
        if self.provider == "gemini":
            try:
                self.llm_service = GeminiService()
                print("✅ Gemini service initialized in SpatialPerceptionModule")
            except Exception as e:
                print(f"⚠️ Error initializing Gemini in SpatialPerceptionModule: {e}")
                self.llm_service = None
        elif self.provider == "cerebras":
            try:
                self.llm_service = CerebrasService()
                print("✅ Cerebras service initialized in SpatialPerceptionModule")
            except Exception as e:
                print(f"⚠️ Error initializing Cerebras in SpatialPerceptionModule: {e}")
                self.llm_service = None
        else:
            print(f"⚠️ Unknown provider '{provider}'. Supported: 'gemini', 'cerebras'")
            self.llm_service = None

        # Store previous response for consistency
        self.previous_llm_response = None

    def analyze_action_effect(
        self,
        matrix_before: List[List[int]],
        matrix_after: List[List[int]],
        action: Union[int, List[int]],
        coordinates: Optional[Tuple[int, int]] = None,
        include_visual_interpretation: bool = True,
    ) -> str:
        """Analyze the effect of an action by comparing before and after states.

        Args:
            matrix_before: State before the action
            matrix_after: State after the action
            action: Action number (int) or list of action numbers (List[int])
            coordinates: Clicked coordinates for complex actions
            include_visual_interpretation: Whether to include Gemini visual analysis

        Returns:
            Analysis string (mathematical only or mathematical + visual)
        """
        if not matrix_before or not matrix_after:
            return "Error: Invalid matrices provided."

        difference_matrix = self._calculate_matrix_difference(
            matrix_before, matrix_after
        )

        # Handle both single action and multiple actions
        if isinstance(action, list):
            if len(action) == 1:
                action_name = get_action_name(action[0])
                primary_action = action[0]
            elif len(action) == 0:
                return "Error: Empty action list provided."
            else:
                action_names = [get_action_name(a) for a in action]
                action_name = f"multiple actions ({', '.join(action_names)})"
                primary_action = action[0]
        else:
            action_name = get_action_name(action)
            primary_action = action

        if not np.any(difference_matrix != 0):
            return (
                f"That action ({action_name}) generated no effect on the environment."
            )
        else:
            change_analysis = self._perform_detailed_analysis(
                difference_matrix,
                matrix_before,
                matrix_after,
                action,
                primary_action,
                coordinates,
                include_visual_interpretation,
            )
            return self._generate_detailed_message(
                change_analysis, include_visual_interpretation
            )

    def detect_objects_in_matrix(self, matrix: List[List[int]]) -> List[ObjectInfo]:
        """Detect all objects (connected components) in a matrix."""
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

            # Add 4-connected neighbors (you can change to 8-connected if needed)
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

    def get_action_name(self, action_number: int) -> str:
        """Get the name of an action by its number."""
        return get_action_name(action_number)

    def _normalize_matrix(self, matrix) -> Optional[List[List[int]]]:
        """Normalize matrix to valid 2D format."""
        if hasattr(matrix, "tolist"):
            matrix = matrix.tolist()

        if not isinstance(matrix, list) or not matrix:
            return None

        # If 3D, take first layer
        if isinstance(matrix[0], list) and matrix[0] and isinstance(matrix[0][0], list):
            matrix = matrix[0]

        # Validate 2D structure
        if not isinstance(matrix[0], list):
            return None

        # Validate all elements are numbers
        for row in matrix:
            if not isinstance(row, list):
                return None
            for val in row:
                if isinstance(val, list) or not isinstance(val, (int, float)):
                    return None

        return matrix

    def _validate_matrices(
        self, before: np.ndarray, after: np.ndarray, difference: np.ndarray
    ) -> bool:
        """Validate matrix dimensions and structure."""
        if before.ndim != 2 or after.ndim != 2:
            print(
                f"❌ Error: Matrices are not 2D. Before: {before.shape}, After: {after.shape}"
            )
            return False

        if before.shape != after.shape:
            print(
                f"❌ Error: Matrices have different dimensions. Before: {before.shape}, After: {after.shape}"
            )
            return False

        if difference.shape != before.shape:
            print(
                f"❌ Error: Difference matrix has incorrect dimensions. Diff: {difference.shape}, Expected: {before.shape}"
            )
            return False

        return True

    def _perform_detailed_analysis(
        self,
        difference_matrix: np.ndarray,
        matrix_before: List[List[int]],
        matrix_after: List[List[int]],
        action: Union[int, List[int]],
        primary_action: int,
        coordinates: Optional[Tuple[int, int]] = None,
        include_visual_interpretation: bool = True,
    ) -> ChangeAnalysis:
        """Perform detailed analysis of detected changes."""
        try:
            before_array = np.array(matrix_before).squeeze()
            after_array = np.array(matrix_after).squeeze()

            if not self._validate_matrices(
                before_array, after_array, difference_matrix
            ):
                return self._create_empty_analysis()

            # Detect all objects in both matrices
            objects_before = self.detect_objects_in_matrix(matrix_before)
            objects_after = self.detect_objects_in_matrix(matrix_after)

            # Compare objects to find changed and unchanged
            changed_objects, unchanged_objects = self._compare_objects(
                objects_before, objects_after
            )

            # Calculate basic metrics
            change_positions = list(zip(*np.where(difference_matrix != 0)))
            total_changes = len(change_positions)
            change_percentage = (
                (total_changes / difference_matrix.size) * 100
                if difference_matrix.size > 0
                else 0.0
            )

            # Classify changes
            change_types = self._classify_changes(
                before_array, after_array, change_positions
            )

            # Additional analysis
            regions_affected = self._identify_affected_regions(change_positions)
            near_coordinates = self._check_proximity_to_coordinates(
                change_positions, coordinates
            )
            directional_consistency = self._analyze_directional_consistency(
                change_positions, primary_action
            )

            # Generate analysis
            mathematical_analysis = self._generate_mathematical_analysis(
                total_changes,
                change_percentage,
                change_types,
                regions_affected,
                directional_consistency,
                near_coordinates,
                action,
            )

            detailed_changes = self._analyze_specific_changes(
                before_array.tolist(), after_array.tolist(), change_positions
            )

            # Add object analysis
            object_analysis = self._generate_object_analysis(
                changed_objects, unchanged_objects
            )

            change_analysis = ChangeAnalysis(
                total_changes=total_changes,
                change_percentage=change_percentage,
                appearances=change_types["appearances"],
                disappearances=change_types["disappearances"],
                transformations=change_types["transformations"],
                regions_affected=regions_affected,
                near_coordinates=near_coordinates,
                directional_consistency=directional_consistency,
                change_positions=change_positions,
                mathematical_analysis=mathematical_analysis
                + "\n\n"
                + detailed_changes
                + "\n\n"
                + object_analysis,
                changed_objects=changed_objects,
                unchanged_objects=unchanged_objects,
                all_objects_before=objects_before,
                all_objects_after=objects_after,
            )

            # Add LLM interpretation if available and requested
            if include_visual_interpretation and self.llm_service:
                try:
                    change_analysis.gemini_interpretation = (
                        self._get_llm_visual_interpretation(
                            matrix_before, matrix_after, change_analysis, action
                        )
                    )
                except Exception as e:
                    print(f"⚠️ Error in {self.provider.upper()} interpretation: {e}")
                    change_analysis.gemini_interpretation = (
                        "Error in visual interpretation"
                    )
            else:
                change_analysis.gemini_interpretation = None

            return change_analysis

        except Exception as e:
            print(f"❌ Error in detailed analysis: {e}")
            return self._create_empty_analysis()

    def _generate_object_analysis(
        self, changed_objects: List[ObjectInfo], unchanged_objects: List[ObjectInfo]
    ) -> str:
        """Generate detailed object analysis."""
        analysis = "🔍 OBJECT ANALYSIS:\n"

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

    def _classify_changes(
        self,
        before_array: np.ndarray,
        after_array: np.ndarray,
        change_positions: List[Tuple[int, int]],
    ) -> dict:
        """Classify changes into appearances, disappearances, and transformations."""
        appearances = disappearances = transformations = 0

        for row, col in change_positions:
            if 0 <= row < before_array.shape[0] and 0 <= col < before_array.shape[1]:
                before_val = before_array[row, col]
                after_val = after_array[row, col]

                if before_val == 0 and after_val != 0:
                    appearances += 1
                elif before_val != 0 and after_val == 0:
                    disappearances += 1
                else:
                    transformations += 1

        return {
            "appearances": appearances,
            "disappearances": disappearances,
            "transformations": transformations,
        }

    def _identify_affected_regions(
        self, change_positions: List[Tuple[int, int]]
    ) -> List[str]:
        """Identify which regions of the map were affected."""
        if not change_positions:
            return []

        regions = []
        for region_name, (
            row_start,
            row_end,
            col_start,
            col_end,
        ) in self.REGION_BOUNDS.items():
            if any(
                row_start <= row < row_end and col_start <= col < col_end
                for row, col in change_positions
            ):
                regions.append(region_name)

        return regions

    def _check_proximity_to_coordinates(
        self,
        change_positions: List[Tuple[int, int]],
        coordinates: Optional[Tuple[int, int]],
    ) -> bool:
        """Check if changes are near the clicked coordinates."""
        if not coordinates:
            return False

        coord_x, coord_y = coordinates
        return any(
            abs(row - coord_y) <= 3 and abs(col - coord_x) <= 3
            for row, col in change_positions
        )

    def _analyze_directional_consistency(
        self, change_positions: List[Tuple[int, int]], action: int
    ) -> Optional[str]:
        """Analyze if changes are consistent with the action direction."""
        if (
            not change_positions
            or action not in [1, 2, 3, 4]
            or len(change_positions) < 2
        ):
            return None

        rows = [pos[0] for pos in change_positions]
        cols = [pos[1] for pos in change_positions]
        center_row = sum(rows) / len(rows)
        center_col = sum(cols) / len(cols)

        if action in [1, 2]:  # Vertical movements
            if action == 1 and center_row < 32:
                return "consistent-up"
            elif action == 2 and center_row > 32:
                return "consistent-down"
            else:
                return "inconsistent-vertical"
        else:  # Horizontal movements
            if action == 3 and center_col < 32:
                return "consistent-left"
            elif action == 4 and center_col > 32:
                return "consistent-right"
            else:
                return "inconsistent-horizontal"

    def _generate_mathematical_analysis(
        self,
        total_changes: int,
        change_percentage: float,
        change_types: dict,
        regions_affected: List[str],
        directional_consistency: Optional[str],
        near_coordinates: bool,
        action: Union[int, List[int]],
    ) -> str:
        """Generate detailed mathematical analysis."""
        # Handle both single action and multiple actions for display
        if isinstance(action, list):
            if len(action) == 1:
                action_name = get_action_name(action[0])
            else:
                action_names = [get_action_name(a) for a in action]
                action_name = f"multiple actions ({', '.join(action_names)})"
        else:
            action_name = get_action_name(action)

        analysis = f"🔢 MATHEMATICAL ANALYSIS: The action ({action_name}) generated {total_changes} changes"

        if change_percentage > 1.0:
            analysis += f" ({change_percentage:.1f}% of the map)"

        # Change types
        if change_types["appearances"] > 0:
            analysis += f"\n📈 Appearances: {change_types['appearances']} pixels (background → color)"
        if change_types["disappearances"] > 0:
            analysis += f"\n📉 Disappearances: {change_types['disappearances']} pixels (color → background)"
        if change_types["transformations"] > 0:
            analysis += f"\n🔄 Transformations: {change_types['transformations']} pixels (color change)"

        # Regions
        if regions_affected:
            if len(regions_affected) == 1:
                analysis += f"\n🗺️  Affected region: {regions_affected[0]}"
            elif len(regions_affected) <= 3:
                analysis += f"\n🗺️  Affected regions: {', '.join(regions_affected)}"
            else:
                analysis += (
                    f"\n🗺️  Changes distributed across {len(regions_affected)} regions"
                )

        # Proximity
        if near_coordinates:
            analysis += f"\n🎯 Changes near clicked coordinates"

        # Direction
        if directional_consistency:
            if "consistent" in directional_consistency:
                direction = directional_consistency.split("-")[1]
                analysis += f"\n🧭 Directional pattern: consistent toward {direction}"
            elif "inconsistent" in directional_consistency:
                analysis += f"\n🧭 Directional pattern: unexpected for movement"

        return analysis

    def _analyze_specific_changes(
        self,
        matrix_before: List[List[int]],
        matrix_after: List[List[int]],
        change_positions: List[Tuple[int, int]],
    ) -> str:
        """Generate detailed analysis of specific changes by position."""
        if not change_positions:
            return "🔍 SPECIFIC CHANGES: None detected"

        before_array = np.array(matrix_before)
        after_array = np.array(matrix_after)

        specific_changes = []
        for row, col in change_positions:
            if 0 <= row < before_array.shape[0] and 0 <= col < before_array.shape[1]:
                before_val = before_array[row, col]
                after_val = after_array[row, col]

                before_color = self.COLOR_NAMES.get(
                    before_val % 17, f"color-{before_val}"
                )
                after_color = self.COLOR_NAMES.get(after_val % 17, f"color-{after_val}")

                specific_changes.append(
                    f"({row},{col}): {before_color} → {after_color}"
                )

        detailed_report = f"🔍 SPECIFIC CHANGES DETECTED:\n"
        detailed_report += (
            f"📍 COMPLETE LIST OF CHANGES ({len(specific_changes)} total):\n"
        )
        for i, change in enumerate(specific_changes, 1):
            detailed_report += f"  {i}. {change}\n"

        return detailed_report

    def _get_llm_visual_interpretation(
        self,
        matrix_before: List[List[int]],
        matrix_after: List[List[int]],
        analysis: ChangeAnalysis,
        action: Union[int, List[int]],
    ) -> str:
        """Get visual interpretation from the selected LLM service based on the two images."""
        try:
            # Validate matrices
            if (
                not matrix_before
                or not matrix_before[0]
                or not matrix_after
                or not matrix_after[0]
            ):
                return "Error: matrices are empty"

            # Normalize matrices
            normalized_before = self._normalize_matrix(matrix_before)
            normalized_after = self._normalize_matrix(matrix_after)

            if not normalized_before or not normalized_after:
                return "Error in matrix normalization"

            # Convert to grid format
            grid_before = [normalized_before]
            grid_after = [normalized_after]

            # Handle both single action and multiple actions for display
            if isinstance(action, list):
                if len(action) == 1:
                    action_name = get_action_name(action[0])
                else:
                    action_names = [get_action_name(a) for a in action]
                    action_name = f"multiple actions ({', '.join(action_names)})"
            else:
                action_name = get_action_name(action, lowercase=True)

            # Generate images
            image_before = grid_to_image(grid_before)
            image_after = grid_to_image(grid_after)

            # Debug display
            print(f"\n🖼️ === IMAGES SENT TO GEMINI ===")
            print(f"📸 BEFORE action ({action_name}):")
            self._display_image_in_iterm2(image_before)
            print(f"\n📸 AFTER action ({action_name}):")
            self._display_image_in_iterm2(image_after)
            print("=" * 50)

            prompt = self._build_enhanced_llm_prompt(action_name, analysis)

            print(
                f"\n🤖 === CONSULTING {self.provider.upper()} FOR VISUAL ANALYSIS ==="
            )
            print(f"🔄 Sending before/after images for action: {action_name}")

            response = self.llm_service.generate_with_images_sync(
                prompt=prompt,
                images=[image_before, image_after],
                system_prompt="You are an intelligent visual analyst specializing in interpreting changes in puzzle images. Your goal is to group pixels into coherent objects and detect logical movements based on the provided mathematical data. Provide visual analysis that a human would understand intuitively.",
            )

            print(
                f"✅ Response received from {self.provider.upper()} ({response.duration_ms}ms)"
            )
            print(
                f"📝 Tokens used: {response.usage.get('total_tokens', 'N/A') if hasattr(response, 'usage') and response.usage else 'N/A'}"
            )
            print("=" * 50)

            # Store this response for next analysis context
            llm_response = response.content.strip()
            self.previous_llm_response = llm_response

            return llm_response

        except Exception as e:
            print(f"❌ Error in {self.provider.upper()} visual interpretation: {e}")
            return "Error getting visual interpretation"

    def _build_enhanced_llm_prompt(
        self, action_name: str, analysis: ChangeAnalysis
    ) -> str:
        """Build the enhanced prompt for LLM analysis including unchanged objects."""
        changed_objects_info = ""
        unchanged_objects_info = ""
        previous_response_info = ""

        if analysis.changed_objects:
            changed_objects_info = "\n### CHANGED OBJECTS:\n"
            for obj in analysis.changed_objects:
                changed_objects_info += f"- {obj.object_id}: {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"

        if analysis.unchanged_objects:
            unchanged_objects_info = "\n### UNCHANGED OBJECTS:\n"
            for obj in analysis.unchanged_objects:
                unchanged_objects_info += f"- {obj.object_id}: {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"

        if self.previous_llm_response:
            previous_response_info = f"\n### PREVIOUS ANALYSIS CONTEXT:\n"
            previous_response_info += (
                f"In your previous analysis, you detected these objects:\n\n"
            )
            previous_response_info += f"{self.previous_llm_response}\n\n"
            previous_response_info += f"**IMPORTANT**: Please maintain consistent object names and IDs when the same objects appear again. "
            previous_response_info += f"If you see objects that match previous ones, use the same naming convention. "
            previous_response_info += f"**Always use UPPERCASE for object names** (e.g., BLOCK_A, BAR_B, MARKER_C).\n"

        return f"""
## ROLE: INTELLIGENT VISUAL PATTERN ANALYZER

Interpret pixel-level changes as abstract objects and transformations for ARC AGI reasoning.

## PROVIDED DATA:

- **IMAGE 1**: BEFORE "{action_name}" action
- **IMAGE 2**: AFTER "{action_name}" action
- **MATHEMATICAL DATA**: Complete list of pixel changes
- **OBJECT DATA**: Pre-identified objects (changed and unchanged)

{previous_response_info}

## EXACT MATHEMATICAL DATA:
{analysis.mathematical_analysis}

{changed_objects_info}

{unchanged_objects_info}

## ENHANCED PERCEPTION TASKS:

### 1. OBJECT VALIDATION & REFINEMENT

- **Verify detected objects**: Confirm if the automatically detected objects make visual sense
- **Merge related objects**: Group objects that should be considered as single entities
- **Split complex objects**: Identify if detected objects should be separated
- **Identify missed objects**: Find objects that weren't automatically detected
- **Classify object relationships**: Parent-child, grouped, or independent objects

### 2. TRANSFORMATION CATEGORIZATION

Classify each detected change into abstract categories:

- **TRANSLATION**: Object moved without changing shape/color
- **ROTATION**: Object rotated around a point
- **REFLECTION**: Object mirrored across an axis
- **SCALING**: Object size changed proportionally
- **MATERIALIZATION**: New object appeared
- **DEMATERIALIZATION**: Object disappeared
- **COLOR_CHANGE**: Object changed color only
- **SHAPE_CHANGE**: Object changed form
- **FRAGMENTATION**: Object broke into pieces
- **FUSION**: Multiple objects combined
- **CLEARING**: Area reset to background
- **FILLING**: Background area filled with color

### 3. UNCHANGED OBJECTS ANALYSIS

For objects that remained unchanged:
- **Stability analysis**: Why these objects didn't change
- **Positional importance**: Strategic locations or patterns
- **Interaction barriers**: Objects that block or influence changes
- **Reference points**: Objects that serve as anchors or guides

### 4. SPATIAL RELATIONSHIP ANALYSIS

- **Alignment**: Objects sharing rows/columns/diagonals
- **Proximity**: Distance relationships between objects
- **Containment**: Objects inside/outside other objects
- **Symmetry**: Reflective or rotational symmetries
- **Grid patterns**: Regular spacing or arrangements
- **Interaction zones**: Areas where changed and unchanged objects meet

## REQUIRED OUTPUT FORMAT:

```
🎯 DETECTED OBJECTS (VALIDATED):
- [Object ID]: [refined shape description] of [color] at region [coordinates]

🔄 TRANSFORMATION SUMMARY:
- [Object ID]: [TRANSFORMATION_TYPE] - [specific description]

⚡ UNCHANGED OBJECTS ANALYSIS:
- [Object ID]: [reason for stability] - [role in the pattern]

📐 SPATIAL RELATIONSHIPS:
- [relationship type]: [description including changed/unchanged interactions]

📊 CHANGE STATISTICS:
- Total objects detected: [number]
- Objects that changed: [number]
- Objects that remained stable: [number]
- Transformation types: [list unique types]
- Spatial extent: [affected regions]
```

## ABSTRACTION RULES:

✅ **DO:**

- Group pixels by **spatial continuity and structural coherence**
- Recognize **multi-color objects** as single entities (striped bars, patterned blocks)
- Use standard shape names (rectangle, square, line, L-shape, etc.)
- **Use UPPERCASE for all object names** (BLOCK_A, BAR_B, MARKER_C, etc.)
- Identify transformation types clearly
- Describe spatial relationships objectively
- Focus on structural and geometric properties
- **Analyze the role of unchanged objects in the overall pattern**
- **Consider how unchanged objects might influence or constrain changes**

❌ **DON'T:**

- Infer game rules or mechanics
- Predict future states
- Use semantic interpretations ("character", "building")
- Describe individual pixels unless they're isolated objects
- Make assumptions about causality
- Ignore unchanged objects in your analysis

## EXAMPLE OUTPUT:

```
🎯 DETECTED OBJECTS (VALIDATED):
- BLOCK_A: 4x8 solid rectangle of yellow at (40,40)-(43,47)
- BAR_B: 4x24 solid rectangle of gray at (32,0)-(35,23)
- MARKER_C: 1x1 pixel of light-green at (0,63)
- ANCHOR_D: 2x2 square of blue at (10,10)-(11,11) [UNCHANGED]

🔄 TRANSFORMATION SUMMARY:
- BLOCK_A: TRANSLATION - moved 8 pixels upward
- BAR_B: MATERIALIZATION - appeared in left region
- LARGE_AREA: CLEARING - rectangular region reset to white background
- MARKER_C: COLOR_CHANGE - light-green to white

⚡ UNCHANGED OBJECTS ANALYSIS:
- ANCHOR_D: POSITIONAL_ANCHOR - serves as reference point in top-left
- BORDER_OBJECTS: STRUCTURAL_BARRIERS - define boundaries for movement
- PATTERN_CORE: STABILITY_CENTER - maintains grid structure

📐 SPATIAL RELATIONSHIPS:
- BLOCK_A maintains horizontal alignment with ANCHOR_D after translation
- BAR_B aligns with grid structure defined by unchanged objects
- Cleared area encompasses previous object positions but avoids stable anchors
- Unchanged objects form a protective boundary around changed region

📊 CHANGE STATISTICS:
- Total objects detected: 8
- Objects that changed: 4
- Objects that remained stable: 4 (50%)
- Transformation types: TRANSLATION, MATERIALIZATION, CLEARING, COLOR_CHANGE
- Spatial extent: 6 distinct regions with 2 stable anchor regions
```

**GOAL**: Provide comprehensive object analysis including both changed and unchanged elements, their interactions, and their roles in the overall pattern for downstream ARC reasoning.
"""

    def _display_image_in_iterm2(self, image) -> None:
        """Display image directly in iTerm2 using escape sequences."""
        try:
            import io
            import base64

            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_data = img_buffer.getvalue()
            img_base64 = base64.b64encode(img_data).decode("utf-8")
            print(f"\033]1337;File=inline=1:{img_base64}\a")

        except Exception as e:
            print(f"⚠️ Error displaying image in iTerm2: {e}")

    def _generate_detailed_message(
        self, analysis: ChangeAnalysis, include_visual_interpretation: bool = True
    ) -> str:
        """Generate message with mathematical analysis and optionally visual interpretation.

        Args:
            analysis: The change analysis data
            include_visual_interpretation: Whether to include visual interpretation

        Returns:
            Formatted analysis message
        """
        message = analysis.mathematical_analysis

        if include_visual_interpretation:
            message += "\n" + "=" * 50

            if analysis.gemini_interpretation:
                message += (
                    f"\n🎨 VISUAL INTERPRETATION:\n{analysis.gemini_interpretation}"
                )
            else:
                message += f"\n🎨 VISUAL INTERPRETATION: Not available"

        return message

    def _calculate_matrix_difference(
        self, matrix_before: List[List[int]], matrix_after: List[List[int]]
    ) -> np.ndarray:
        """Calculate the difference between two matrices."""
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

    def _create_empty_analysis(self) -> ChangeAnalysis:
        """Create an empty analysis in case of error."""
        return ChangeAnalysis(
            total_changes=0,
            change_percentage=0.0,
            appearances=0,
            disappearances=0,
            transformations=0,
            regions_affected=[],
            near_coordinates=False,
            directional_consistency=None,
            change_positions=[],
            mathematical_analysis="Error in mathematical analysis",
            changed_objects=[],
            unchanged_objects=[],
            all_objects_before=[],
            all_objects_after=[],
        )
