import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from agents.structs import FrameData, GameAction

# memory
from .shared_memory import SharedMemory

# structured data
from .data_structures import (
    StructuredObjectInfo, 
    AisthesisStructuredData, 
    ProgressAnalysis
)

# utils
from agents.tomas_engine.utils.matrix import calculate_matrix_difference

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
    ) -> Tuple[str, AisthesisStructuredData]:
        """Analyze the effect of an action sequence by comparing before and after states using objective object detection."""
        print(f"🏞️ AISTHESIS is analyzing the effect of the action sequence...")

        # Get current state (after all actions)
        current_state = latest_frame.frame
        
        # CRITICAL FIX: Extract only the last layer if multiple layers detected
        # This prevents the "red frame" issue when losing levels
        current_state = self._extract_single_frame_layer(current_state)

        # Determine how many frames back to compare based on executed actions
        if executed_actions and len(executed_actions) > 1:
            # Multiple actions executed, compare with state before the sequence
            frames_back = (
                len(executed_actions) + 1
            )  # +1 because frames[-1] is latest, frames[-2] is previous
            if len(frames) >= frames_back:
                previous_state = frames[-frames_back].frame
                previous_state = self._extract_single_frame_layer(previous_state)  # Also fix previous
                action_description = f"sequence of {len(executed_actions)} actions: {', '.join(executed_actions)}"
                print(
                    f"🔄 Comparing current state with {frames_back-1} frames ago (before {len(executed_actions)}-action sequence)"
                )
            else:
                # Fallback if not enough frames
                previous_state = frames[-2].frame
                previous_state = self._extract_single_frame_layer(previous_state)  # Also fix previous
                action_description = f"sequence: {', '.join(executed_actions)}"
                print(f"⚠️ Not enough frames for full comparison, using previous frame")
        else:
            # Single action or no action info, use previous frame
            previous_state = frames[-2].frame
            previous_state = self._extract_single_frame_layer(previous_state)  # Also fix previous
            action_description = get_action_name(latest_frame.action_input.id.value)
            print(f"🔄 Comparing current state with previous frame (single action)")

        # Check if this is a level transition by comparing scores AND game states
        current_score = latest_frame.score
        previous_score = frames[-2].score
        current_state_game = latest_frame.state
        previous_state_game = frames[-2].state
        
        # Detect different types of transitions
        is_level_up = current_score > previous_score  # Score increased = level completed successfully
        is_level_lost = (current_state_game.value == "GAME_OVER" and 
                        previous_state_game.value != "GAME_OVER")  # Game over transition
        is_game_reset = (current_state_game.value == "NOT_FINISHED" and 
                        previous_state_game.value == "GAME_OVER")  # Reset after game over
        
        is_level_transition = is_level_up or is_level_lost or is_game_reset

        if is_level_transition:
            if is_level_up:
                print(f"🎉 LEVEL UP detected! Score: {previous_score} → {current_score}")
                transition_type = "LEVEL_UP"
                progress_detected = True
                
                # display the new level state
                print(f"\n🖼️ NEW LEVEL STATE:")
                image_after = grid_to_image(current_state)
                display_image_in_iterm2(image_after)
                
                text_response = f"🎉 LEVEL UP! Score increased from {previous_score} to {current_score}.\n\nStarted new level - ready for object detection in new environment!"
                
            elif is_level_lost:
                print(f"💀 LEVEL LOST detected! State: {previous_state_game.value} → {current_state_game.value}")
                transition_type = "LEVEL_LOST"
                progress_detected = False
                
                # CRITICAL FIX: When level is lost, only display the current state (game over screen)
                # Do NOT concatenate or overlay with previous frame
                print(f"\n🖼️ GAME OVER STATE (showing only current frame):")
                image_after = grid_to_image(current_state)
                display_image_in_iterm2(image_after)
                
                text_response = f"💀 LEVEL LOST! Game state changed to {current_state_game.value}.\n\nGame over - ready to restart or analyze failure."
                
            else:  # is_game_reset
                print(f"🔄 GAME RESET detected! State: {previous_state_game.value} → {current_state_game.value}")
                transition_type = "GAME_RESET"
                progress_detected = True
                
                # display the reset state
                print(f"\n🖼️ RESET STATE:")
                image_after = grid_to_image(current_state)
                display_image_in_iterm2(image_after)
                
                text_response = f"🔄 GAME RESET! Ready to start fresh attempt.\n\nNew game state - ready for object detection in clean environment!"

            # Create structured data for level transition
            level_transition_data = AisthesisStructuredData(
                objects_before=[],
                objects_after=[],
                changed_objects=[],
                unchanged_objects=[],
                transformation_type=transition_type,
                progress_detected=progress_detected,
                is_level_transition=True,
                clickable_coordinates=self._find_clickable_coordinates(current_state)
            )
            
            return text_response, level_transition_data

        else:
            # Normal single-level frame - use spatial perception for objective analysis
            # Normalize matrices to 2D format
            current_state_2d = self._normalize_to_2d(current_state)
            previous_state_2d = self._normalize_to_2d(previous_state)

            # Check if there are any changes at all
            difference_matrix = calculate_matrix_difference(previous_state_2d, current_state_2d)
            
            # CRITICAL FIX: Also check if mathematical analysis detected object changes
            # Sometimes objects move but pixels might not change due to rounding or detection issues
            objects_before = self._detect_objects_in_matrix(previous_state_2d)
            objects_after = self._detect_objects_in_matrix(current_state_2d)
            object_changes_detected = len(objects_before) != len(objects_after)
            
            # Check for position/size changes in objects
            for obj_before in objects_before:
                for obj_after in objects_after:
                    if obj_before.object_id == obj_after.object_id:
                        if (obj_before.bounds != obj_after.bounds or 
                            obj_before.size != obj_after.size or 
                            obj_before.region != obj_after.region):
                            object_changes_detected = True
                            print(f"🔍 OBJECT MOVEMENT detected: {obj_before.object_id} moved from {obj_before.region} to {obj_after.region}")
                            break
            
            # Only proceed with "no effect" analysis if BOTH pixel diff AND object analysis show no changes
            if not np.any(difference_matrix != 0) and not object_changes_detected:
                print(f"⚡ No pixel changes AND no object changes detected - analyzing current environment with Gemini")
                
                # ENHANCED: Use Gemini to analyze current environment when no changes
                # This is critical because LOGOS needs to understand the current state
                structured_objects = [self._convert_to_structured_object(obj) for obj in objects_before]
                
                # Generate comprehensive environment analysis using Gemini
                text_response = self._analyze_static_environment_with_gemini(
                    current_state, action_description, objects_before
                )
                
                no_effect_data = AisthesisStructuredData(
                    objects_before=structured_objects,
                    objects_after=structured_objects,
                    changed_objects=[],
                    unchanged_objects=structured_objects,
                    transformation_type="NO_EFFECT",
                    progress_detected=False,
                    is_level_transition=False,
                    clickable_coordinates=self._find_clickable_coordinates(current_state)
                )
                
                return text_response, no_effect_data

            # CHANGES DETECTED - proceed with normal object analysis
            print(f"\n🔍 Changes detected! Using objective object detection...")
            if object_changes_detected:
                print(f"📊 Object-level changes detected (even if pixels appear similar)")

            # Detect objects in both states (we already have them from the change detection above)
            try:
                # Compare objects to find changes
                changed_objects, unchanged_objects = self._compare_objects(
                    objects_before, objects_after
                )

                # Consult memory for similar experiences
                memory = SharedMemory.get_instance()
                similar_analyses = memory.get_relevant_experience(
                    f"objects {len(changed_objects)} changed"
                )

                # Generate enhanced mathematical analysis
                enhanced_analysis = self._generate_enhanced_mathematical_analysis(
                    objects_before,
                    objects_after,
                    changed_objects,
                    unchanged_objects,
                    action_description,
                    similar_analyses,
                    current_state
                )

                # Generate images for Gemini analysis
                image_before = grid_to_image(previous_state)
                image_after = grid_to_image(current_state)

                print(f"\n🖼️ BEFORE: {action_description}")
                display_image_in_iterm2(image_before)

                # Check if action was a click and create click visualization
                images_for_gemini = [image_before]
                is_click_action = latest_frame.action_input.id == GameAction.ACTION6

                if is_click_action:  # ACTION6 is click
                    click_visualization = self._create_click_visualization(latest_frame)
                    if click_visualization:
                        print(f"\n🖼️ CLICK POSITION:")
                        display_image_in_iterm2(click_visualization)
                        images_for_gemini.append(click_visualization)

                images_for_gemini.append(image_after)
                print(f"\n🖼️ AFTER: {action_description}")
                display_image_in_iterm2(image_after)

                # Build prompt with click information
                prompt = self._build_aisthesis_prompt(
                    action_description,
                    enhanced_analysis,
                    executed_actions,
                    is_click_action,
                    latest_frame,  # Pass latest_frame to get click coordinates
                )

                # Send to Gemini for object-focused analysis
                aisthesis_response = self.gemini_service.generate_with_images_sync(
                    prompt,
                    images=images_for_gemini,
                    game_id=latest_frame.game_id,
                    nuclei="aisthesis",
                )

                # print(f"\n🔍 AISTHESIS RESPONSE:")
                # print(aisthesis_response)

                # Remember successful experience in shared memory with more context
                memory_context = f"objects {len(changed_objects)} changed {len(unchanged_objects)} unchanged"
                SharedMemory.get_instance().remember_success(
                    memory_context,
                    action_description,
                    f"Detected {len(changed_objects)} changes successfully",
                )

                # Create structured data
                structured_data = self._create_structured_data(
                    objects_before, objects_after, changed_objects, unchanged_objects,
                    action_description, current_state
                )

                return aisthesis_response.content, structured_data

            except Exception as e:
                print(f"⚠️ Error in objective object analysis: {e}")
                
                # Create fallback structured data
                fallback_data = AisthesisStructuredData(
                    objects_before=[],
                    objects_after=[],
                    changed_objects=[],
                    unchanged_objects=[],
                    transformation_type="ERROR",
                    progress_detected=False,
                    is_level_transition=False,
                    clickable_coordinates=[(32, 32)]  # Fallback center coordinate
                )
                
                text_response = f"Error in objective object analysis: {e}"
                return text_response, fallback_data

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
        similar_analyses: str = "",
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

        # Add similar experiences if they exist
        if similar_analyses:
            analysis += f"\n🧠 SIMILAR PAST EXPERIENCES:\n{similar_analyses}\n"

        return analysis

    def _generate_enhanced_mathematical_analysis(
        self, 
        objects_before: List[ObjectInfo],
        objects_after: List[ObjectInfo], 
        changed_objects: List[ObjectInfo],
        unchanged_objects: List[ObjectInfo],
        action_description: str,
        similar_analyses: str,
        current_state = None
    ) -> str:
        """Generate enhanced mathematical analysis that's concise but insightful for Gemini"""
        
        analysis = f"🔍 ENHANCED MATHEMATICAL ANALYSIS FOR: {action_description}\n\n"
        
        # Movement Vector Analysis for changed objects
        if changed_objects:
            analysis += f"📊 MOVEMENT & TRANSFORMATION ANALYSIS ({len(changed_objects)} objects changed):\n"
            
            for obj in changed_objects:
                # Find corresponding object in before state to calculate movement
                before_obj = self._find_matching_object(obj, objects_before)
                
                if before_obj:
                    # Calculate movement vector
                    movement_vector = self._calculate_movement_vector(before_obj, obj)
                    area_change = obj.size - before_obj.size
                    
                    analysis += f"  • {obj.object_id}: "
                    
                    # Movement description
                    if movement_vector['magnitude'] > 0:
                        direction = movement_vector['direction']
                        magnitude = movement_vector['magnitude']
                        analysis += f"MOVED {direction} by {magnitude:.1f} pixels "
                    
                    # Size/area changes
                    if area_change != 0:
                        change_type = "expanded" if area_change > 0 else "contracted"
                        analysis += f"({change_type} by {abs(area_change)} pixels) "
                    
                    # Position details
                    analysis += f"from {before_obj.region} to {obj.region}\n"
                    analysis += f"    Vector: ({movement_vector['dx']:+d}, {movement_vector['dy']:+d}) | Size: {before_obj.size} → {obj.size}\n"
                else:
                    # New object appeared
                    analysis += f"  • {obj.object_id}: MATERIALIZED at {obj.region} ({obj.size} pixels)\n"
        
        # Spatial Relationship Analysis
        spatial_insights = self._analyze_spatial_relationships(objects_after)
        if spatial_insights:
            analysis += f"\n🎯 SPATIAL RELATIONSHIPS:\n{spatial_insights}\n"
        
        # Pattern Detection
        pattern_insights = self._detect_simple_patterns(objects_after)
        if pattern_insights:
            analysis += f"\n📐 PATTERN DETECTION:\n{pattern_insights}\n"
        
        # Static reference objects
        if unchanged_objects:
            key_anchors = [obj for obj in unchanged_objects if obj.size >= 16]  # Focus on significant objects
            if key_anchors:
                analysis += f"\n⚓ KEY ANCHOR OBJECTS ({len(key_anchors)} static references):\n"
                for obj in key_anchors[:3]:  # Limit to 3 most important
                    analysis += f"  • {obj.object_id}: {obj.color} {obj.shape} at {obj.region}\n"
        
        # CRITICAL: ALWAYS include clickable coordinates for LOGOS
        if current_state is not None:
            clickable_coords = self._find_clickable_coordinates(current_state)
            coordinates_summary = self._create_clickable_coordinates_summary(objects_after)
            analysis += f"\n🎯 CLICKABLE COORDINATES FOR LOGOS:\n{coordinates_summary}\n"
            analysis += f"📍 Available click targets: {clickable_coords[:8]}\n"  # Limit to first 8 coords
        
        # Summary for Gemini context
        total_objects = len(objects_after)
        changed_count = len(changed_objects)
        analysis += f"\n📈 SUMMARY: {changed_count}/{total_objects} objects changed"
        
        if similar_analyses:
            analysis += f"\n🧠 PATTERN MEMORY: {similar_analyses[:100]}..."
        
        return analysis

    def _find_matching_object(self, target_obj: ObjectInfo, object_list: List[ObjectInfo]) -> Optional[ObjectInfo]:
        """Find the most similar object in the before state"""
        best_match = None
        best_score = -1
        
        for obj in object_list:
            # Score based on color, shape similarity, and position proximity
            score = 0
            if obj.color == target_obj.color:
                score += 3
            if obj.shape == target_obj.shape:
                score += 2
            
            # Position proximity (inverse distance)
            center_before = self._get_object_center(obj)
            center_after = self._get_object_center(target_obj)
            distance = ((center_before[0] - center_after[0])**2 + (center_before[1] - center_after[1])**2)**0.5
            if distance < 20:  # Close objects are likely the same
                score += max(0, 5 - distance/4)
            
            if score > best_score:
                best_score = score
                best_match = obj
        
        return best_match if best_score > 2 else None

    def _calculate_movement_vector(self, before_obj: ObjectInfo, after_obj: ObjectInfo) -> dict:
        """Calculate movement vector between two object positions"""
        center_before = self._get_object_center(before_obj)
        center_after = self._get_object_center(after_obj)
        
        dx = center_after[1] - center_before[1]  # Column change
        dy = center_after[0] - center_before[0]  # Row change
        magnitude = (dx**2 + dy**2)**0.5
        
        # Simple direction classification
        direction = "stationary"
        if magnitude > 2:
            if abs(dx) > abs(dy):
                direction = "right" if dx > 0 else "left"
            else:
                direction = "down" if dy > 0 else "up"
            
            # Diagonal movements
            if abs(dx) > 2 and abs(dy) > 2:
                direction += "-" + ("down" if dy > 0 else "up")
        
        return {
            'dx': dx,
            'dy': dy, 
            'magnitude': magnitude,
            'direction': direction
        }

    def _get_object_center(self, obj: ObjectInfo) -> Tuple[int, int]:
        """Calculate center point of an object"""
        if not obj.positions:
            # Use bounds as fallback
            center_row = (obj.bounds[0] + obj.bounds[1]) // 2
            center_col = (obj.bounds[2] + obj.bounds[3]) // 2
            return (center_row, center_col)
        
        # Calculate from actual positions
        avg_row = sum(pos[0] for pos in obj.positions) / len(obj.positions)
        avg_col = sum(pos[1] for pos in obj.positions) / len(obj.positions)
        return (int(avg_row), int(avg_col))

    def _analyze_spatial_relationships(self, objects: List[ObjectInfo]) -> str:
        """Analyze key spatial relationships between objects"""
        if len(objects) < 2:
            return ""
        
        insights = []
        
        # Find alignments (objects sharing same row or column)
        row_groups = {}
        col_groups = {}
        
        for obj in objects:
            center = self._get_object_center(obj)
            row_key = center[0] // 4  # Group by approximate rows (with 4-pixel tolerance)
            col_key = center[1] // 4  # Group by approximate columns
            
            if row_key not in row_groups:
                row_groups[row_key] = []
            if col_key not in col_groups:
                col_groups[col_key] = []
                
            row_groups[row_key].append(obj)
            col_groups[col_key].append(obj)
        
        # Report significant alignments
        for row_key, objs in row_groups.items():
            if len(objs) >= 3:
                obj_names = [obj.object_id for obj in objs]
                insights.append(f"  • HORIZONTAL alignment: {', '.join(obj_names[:3])}")
        
        for col_key, objs in col_groups.items():
            if len(objs) >= 3:
                obj_names = [obj.object_id for obj in objs]
                insights.append(f"  • VERTICAL alignment: {', '.join(obj_names[:3])}")
        
        # Find proximity clusters
        close_pairs = []
        for i, obj1 in enumerate(objects):
            for obj2 in objects[i+1:]:
                center1 = self._get_object_center(obj1)
                center2 = self._get_object_center(obj2)
                distance = ((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)**0.5
                
                if distance < 8:  # Very close objects
                    close_pairs.append(f"{obj1.object_id} & {obj2.object_id}")
        
        if close_pairs:
            insights.append(f"  • ADJACENT pairs: {', '.join(close_pairs[:2])}")
        
        return '\n'.join(insights) if insights else ""

    def _detect_simple_patterns(self, objects: List[ObjectInfo]) -> str:
        """Detect simple geometric patterns"""
        if len(objects) < 3:
            return ""
        
        patterns = []
        
        # Count objects by color and shape
        color_counts = {}
        shape_counts = {}
        
        for obj in objects:
            color_counts[obj.color] = color_counts.get(obj.color, 0) + 1
            shape_counts[obj.shape] = shape_counts.get(obj.shape, 0) + 1
        
        # Report significant patterns
        for color, count in color_counts.items():
            if count >= 3:
                patterns.append(f"  • {count} {color} objects forming potential group")
        
        for shape, count in shape_counts.items():
            if count >= 3:
                patterns.append(f"  • {count} {shape} shapes suggesting structural pattern")
        
        # Detect grid-like arrangements (same-sized objects at regular intervals)
        same_size_objects = {}
        for obj in objects:
            size = obj.size
            if size not in same_size_objects:
                same_size_objects[size] = []
            same_size_objects[size].append(obj)
        
        for size, objs in same_size_objects.items():
            if len(objs) >= 4 and size >= 4:  # At least 4 objects of meaningful size
                patterns.append(f"  • {len(objs)} objects of size {size} - possible grid structure")
        
        return '\n'.join(patterns) if patterns else ""

    def _build_aisthesis_prompt(
        self,
        action_name: str,
        objective_analysis: str,
        executed_actions: List[str] = None,
        is_click_action: bool = False,
        latest_frame: FrameData = None,
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
## EXECUTED ACTION SEQUENCE DECIDED by LOGOS
{' → '.join(executed_actions)}
(Comparing state before the entire sequence with state after all actions completed)
"""
        else:
            # Extract click coordinates if this is a click action
            click_info = ""
            if is_click_action and latest_frame:
                try:
                    action_data = latest_frame.action_input.data
                    if action_data and "x" in action_data and "y" in action_data:
                        x_coord = int(action_data["x"])
                        y_coord = int(action_data["y"])
                        click_info = f" at coordinates ({x_coord}, {y_coord})"
                        print(f"🎯 AISTHESIS: Including click coordinates {x_coord}, {y_coord} in prompt")
                except Exception as e:
                    print(f"⚠️ Could not extract click coordinates: {e}")
                    
            sequence_info = f"""
## EXECUTED ACTION DECIDED by LOGOS
{action_name}{click_info}
"""

        # Describe images based on whether it was a click action
        if is_click_action:
            images_description = """
## IMAGES PROVIDED
- **IMAGE 1**: BEFORE state (game state before the click)
- **IMAGE 2**: CLICK POSITION (64x64 white matrix with black pixel showing where click occurred)
- **IMAGE 3**: AFTER state (game state after the click)
"""
        else:
            images_description = """
## IMAGES PROVIDED
- **IMAGE 1**: BEFORE state (game state before the action)
- **IMAGE 2**: AFTER state (game state after the action)
"""

        prompt = f"""
{aisthesis_content}

{sequence_info}

{images_description}

## MATHEMATICAL OBJECT ANALYSIS
{objective_analysis}
"""
        return prompt

    def _create_click_visualization(self, latest_frame: FrameData):
        """Create a 64x64 white matrix with a black pixel at the click position."""
        try:
            # Get click coordinates from action data
            action_data = latest_frame.action_input.data
            if not action_data or "x" not in action_data or "y" not in action_data:
                print("⚠️ Click coordinates not found in action data")
                return None

            x_coord = int(action_data["x"])
            y_coord = int(action_data["y"])

            print(
                f"🎯 Creating click visualization at coordinates: ({x_coord}, {y_coord})"
            )

            # Create 64x64 white matrix (all 0s)
            click_matrix = np.zeros((64, 64), dtype=int)

            # Set black pixel (value 5) at click position
            # Note: x is column, y is row
            if 0 <= y_coord < 64 and 0 <= x_coord < 64:
                click_matrix[y_coord, x_coord] = 5  # Black pixel
            else:
                print(f"⚠️ Click coordinates ({x_coord}, {y_coord}) are out of bounds")
                return None

            # Convert to 3D format for grid_to_image (expecting [matrix])
            click_matrix_3d = [click_matrix.tolist()]

            # Generate image
            click_image = grid_to_image(click_matrix_3d)

            return click_image

        except Exception as e:
            print(f"⚠️ Error creating click visualization: {e}")
            return None
    
    def _convert_to_structured_object(self, obj: ObjectInfo) -> StructuredObjectInfo:
        """Convert ObjectInfo to StructuredObjectInfo"""
        # Calculate center
        rows = [pos[0] for pos in obj.positions]
        cols = [pos[1] for pos in obj.positions]
        center = (sum(rows) // len(rows), sum(cols) // len(cols))
        
        # Check if this might be the player (simple heuristic)
        is_player = "blue" in obj.color.lower() and obj.size <= 4  # Small blue objects might be player
        
        return StructuredObjectInfo(
            object_id=obj.object_id,
            shape=obj.shape,
            color=obj.color,
            positions=obj.positions,
            bounds=obj.bounds,
            region=obj.region,
            size=obj.size,
            center=center,
            is_player=is_player
        )
    
    def _find_clickable_coordinates(self, state) -> List[Tuple[int, int]]:
        """Find potentially clickable coordinates based on non-background objects"""
        clickable_coords = []
        
        try:
            # Normalize to 2D if needed
            state_2d = self._normalize_to_2d(state)
            matrix_array = np.array(state_2d)
            
            # Find all non-background pixels (not 0)
            non_bg_positions = np.where(matrix_array != 0)
            
            # Sample some positions (limit to avoid too many)
            max_coords = 20
            positions = list(zip(non_bg_positions[0], non_bg_positions[1]))
            
            if len(positions) <= max_coords:
                clickable_coords = [(int(row), int(col)) for row, col in positions]
            else:
                # Sample evenly across the space
                step = len(positions) // max_coords
                clickable_coords = [(int(row), int(col)) for row, col in positions[::step]]
            
        except Exception as e:
            print(f"⚠️ Error finding clickable coordinates: {e}")
            # Fallback: return some center coordinates
            clickable_coords = [(32, 32), (16, 16), (48, 48), (16, 48), (48, 16)]
        
        return clickable_coords
    
    def _create_structured_data(
        self, 
        objects_before: List[ObjectInfo], 
        objects_after: List[ObjectInfo],
        changed_objects: List[ObjectInfo],
        unchanged_objects: List[ObjectInfo],
        action_description: str,
        current_state
    ) -> AisthesisStructuredData:
        """Create structured data from analysis results"""
        
        # Convert to structured format
        structured_before = [self._convert_to_structured_object(obj) for obj in objects_before]
        structured_after = [self._convert_to_structured_object(obj) for obj in objects_after]
        structured_changed = [self._convert_to_structured_object(obj) for obj in changed_objects]
        structured_unchanged = [self._convert_to_structured_object(obj) for obj in unchanged_objects]
        
        # Determine transformation type
        transformation_type = self._determine_transformation_type(changed_objects, action_description)
        
        # Detect progress
        progress_detected = len(changed_objects) > 0
        
        # Find clickable coordinates
        clickable_coords = self._find_clickable_coordinates(current_state)
        
        return AisthesisStructuredData(
            objects_before=structured_before,
            objects_after=structured_after,
            changed_objects=structured_changed,
            unchanged_objects=structured_unchanged,
            transformation_type=transformation_type,
            progress_detected=progress_detected,
            is_level_transition=False,
            clickable_coordinates=clickable_coords
        )
    
    def _determine_transformation_type(self, changed_objects: List[ObjectInfo], action_description: str) -> str:
        """Determine the type of transformation that occurred"""
        if not changed_objects:
            return "NO_EFFECT"
        
        if len(changed_objects) == 1:
            if "moved" in action_description.lower() or "position" in action_description.lower():
                return "TRANSLATION"
            elif "color" in action_description.lower():
                return "COLOR_CHANGE"
            elif "shape" in action_description.lower():
                return "SHAPE_CHANGE"
            elif "appeared" in action_description.lower():
                return "MATERIALIZATION"
            elif "disappeared" in action_description.lower():
                return "DEMATERIALIZATION"
        elif len(changed_objects) > 1:
            if "fragmented" in action_description.lower() or "broke" in action_description.lower():
                return "FRAGMENTATION"
            elif "combined" in action_description.lower() or "merged" in action_description.lower():
                return "FUSION"
            else:
                return "MULTIPLE_CHANGES"
        
        # Default
        return "TRANSFORMATION"
    
    def _extract_single_frame_layer(self, frame_data):
        """Extract a single layer from frame data to prevent concatenated frame visualization.
        
        This fixes the 'red frame' issue when levels are lost by ensuring only one
        frame layer is displayed instead of concatenated layers.
        """
        if not frame_data:
            return frame_data
            
        # Check if frame_data is a 3D array (list of 2D layers)
        if isinstance(frame_data, list) and len(frame_data) > 0:
            if isinstance(frame_data[0], list) and len(frame_data[0]) > 0:
                if isinstance(frame_data[0][0], list):
                    # This is a 3D array (multiple layers)
                    if len(frame_data) > 1:
                        print(f"🔧 FRAME FIX: Detected {len(frame_data)} layers, extracting last layer to prevent concatenation")
                        return [frame_data[-1]]  # Return only the last layer wrapped in array for grid_to_image
                    else:
                        # Single layer, return as is
                        return frame_data
                else:
                    # This is already a 2D array, wrap it for grid_to_image consistency
                    return [frame_data]
            else:
                # This is a 1D array, not expected but handle gracefully
                return frame_data
        else:
            # Not a list or empty, return as is
            return frame_data
    
    def _analyze_static_environment_with_gemini(
        self, current_state, action_description: str, 
        objects_current: list
    ) -> str:
        """Analyze current environment when no changes detected - CRITICAL for LOGOS understanding"""
        
        # Generate current state image
        image_current = grid_to_image(current_state)
        
        print(f"\n🖼️ ANALYZING STATIC ENVIRONMENT:")
        display_image_in_iterm2(image_current)
        
        # Build comprehensive environment analysis prompt
        prompt = self._build_static_environment_prompt(action_description, objects_current)
        
        try:
            # Use Gemini for rich environment analysis
            gemini_response = self.gemini_service.generate_with_images_sync(
                prompt,
                images=[image_current],
                game_id="static_analysis", 
                nuclei="aisthesis"
            )
            
            environment_analysis = gemini_response.content
            
            # Enhance with objective object data including COORDINATES
            objective_summary = self._create_objective_environment_summary(objects_current)
            coordinates_summary = self._create_clickable_coordinates_summary(objects_current)
            
            # Combine both analyses
            full_response = f"""ACTION EFFECT: {action_description} generated NO visible changes in the environment.

CURRENT ENVIRONMENT ANALYSIS:
{environment_analysis}

OBJECTIVE OBJECT DETECTION:
{objective_summary}

CLICKABLE COORDINATES FOR LOGOS:
{coordinates_summary}

INTERACTIVE ELEMENTS ASSESSMENT:
Based on visual patterns, potential clickable/interactive areas have been identified in the structured data with exact coordinates."""

            return full_response
            
        except Exception as e:
            print(f"⚠️ Error in static environment analysis: {e}")
            # Fallback to objective analysis only
            objective_summary = self._create_objective_environment_summary(objects_current)
            coordinates_summary = self._create_clickable_coordinates_summary(objects_current)
            return f"""ACTION EFFECT: {action_description} generated NO visible changes.

CURRENT ENVIRONMENT (Objective Analysis):
{objective_summary}

CLICKABLE COORDINATES FOR LOGOS:
{coordinates_summary}

The environment remains unchanged. Consider trying different actions or clicking on distinct visual elements using the provided coordinates."""
    
    def _build_static_environment_prompt(self, action_description: str, objects_current: list) -> str:
        """Build specialized prompt for analyzing static game environment"""
        
        aisthesis_content = ""
        try:
            with open("agents/tomas_engine/nucleus/aisthesis.md", "r", encoding="utf-8") as f:
                aisthesis_content = f.read()
        except FileNotFoundError:
            print("⚠️ Warning: aisthesis.md file not found")
            aisthesis_content = "AISTHESIS - Visual Environment Analyzer"
        except Exception as e:
            print(f"⚠️ Error reading aisthesis.md: {e}")
            aisthesis_content = "AISTHESIS - Visual Environment Analyzer"
        
        object_count = len(objects_current)
        
        prompt = f"""{aisthesis_content}

## STATIC ENVIRONMENT ANALYSIS TASK

**SITUATION**: The action "{action_description}" caused NO visible changes in the environment.

**YOUR CRITICAL MISSION**: Analyze the CURRENT environment to help LOGOS understand what's available for interaction.

**KEY FOCUS AREAS**:

1. **INTERACTIVE ELEMENTS DETECTION**:
   - Identify buttons, switches, levers, doors, keys
   - Look for objects that stand out visually (different colors, shapes, patterns)
   - Note any elements that look clickable or manipulable
   - Identify UI elements, panels, or control interfaces

2. **ENVIRONMENTAL LAYOUT**:
   - Describe the overall game environment structure  
   - Identify distinct regions, areas, or zones
   - Note boundaries, walls, obstacles, or pathways
   - Describe the player's current position if visible

3. **VISUAL DISTINCTIVENESS**:
   - Point out objects or areas that are visually different from the background
   - Identify colored elements, unique shapes, or standout features
   - Note any patterns, symbols, or special markings
   - Highlight areas that might reward exploration or interaction

4. **GAMEPLAY CONTEXT CLUES**:
   - Suggest what type of game this might be based on visual elements
   - Identify potential goals or objectives based on layout
   - Note any progress indicators, counters, or status elements

**HUMAN-LIKE INTUITION**: Humans naturally click on buttons, try to interact with distinct objects, and explore visually interesting elements. Identify what a curious human would want to try clicking or interacting with.

**OUTPUT FORMAT**: Provide a natural, descriptive analysis that helps LOGOS understand the current state and what might be worth trying next.

**DETECTED OBJECTS**: The objective system found {object_count} distinct objects in the current environment.

**IMAGE PROVIDED**: Current game state after the action that caused no changes."""
        
        return prompt
    
    def _create_objective_environment_summary(self, objects_current: list) -> str:
        """Create objective summary of current environment objects"""
        
        if not objects_current:
            return "No distinct objects detected in the current environment."
        
        summary = f"🔍 DETECTED {len(objects_current)} OBJECTS:\n"
        
        # Group objects by characteristics
        by_region = {}
        by_color = {}
        clickable_candidates = []
        
        for i, obj in enumerate(objects_current, 1):
            # Basic info
            summary += f"  {i}. {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"
            summary += f"     Position: rows {obj.bounds[0]}-{obj.bounds[1]}, cols {obj.bounds[2]}-{obj.bounds[3]}\n"
            
            # Group by region
            if obj.region not in by_region:
                by_region[obj.region] = []
            by_region[obj.region].append(obj)
            
            # Group by color  
            if obj.color not in by_color:
                by_color[obj.color] = []
            by_color[obj.color].append(obj)
            
            # Identify potentially clickable elements
            if (obj.size < 50 and obj.size > 1 and  # Reasonable button size
                obj.color not in ["white", "black"] and  # Not background
                obj.shape != "pixel"):  # Not just noise
                clickable_candidates.append(obj)
        
        # Regional distribution
        if len(by_region) > 1:
            summary += f"\n📍 REGIONAL DISTRIBUTION:\n"
            for region, objs in by_region.items():
                summary += f"  • {region}: {len(objs)} objects\n"
        
        # Color distribution  
        if len(by_color) > 1:
            summary += f"\n🎨 COLOR DISTRIBUTION:\n"
            for color, objs in by_color.items():
                summary += f"  • {color}: {len(objs)} objects\n"
        
        # Clickable candidates
        if clickable_candidates:
            summary += f"\n🎯 POTENTIALLY INTERACTIVE ELEMENTS ({len(clickable_candidates)}):\n"
            for obj in clickable_candidates:
                summary += f"  • {obj.color} {obj.shape} at {obj.region} - might be clickable\n"
        
        return summary
    
    def _create_clickable_coordinates_summary(self, objects_current: list) -> str:
        """Create summary of specific clickable coordinates for LOGOS"""
        
        if not objects_current:
            return "No clickable coordinates identified in current environment."
        
        # Prioritize potentially interactive objects
        clickable_objects = []
        
        for obj in objects_current:
            # Calculate center coordinates for clicking
            center_row = (obj.bounds[0] + obj.bounds[1]) // 2
            center_col = (obj.bounds[2] + obj.bounds[3]) // 2
            
            # Assess clickability score based on human-like criteria
            clickability_score = 0
            reasons = []
            
            # Size factor (buttons are typically small-medium)
            if 1 < obj.size <= 50:
                clickability_score += 3
                reasons.append("good button size")
            elif 50 < obj.size <= 100:
                clickability_score += 2
                reasons.append("medium object")
            elif obj.size == 1:
                clickability_score += 1
                reasons.append("pixel-sized")
            
            # Color factor (non-background colors)
            if obj.color not in ["white", "black"]:
                clickability_score += 2
                reasons.append("distinctive color")
            
            # Shape factor (regular shapes more likely to be interactive)
            if "square" in obj.shape or "rectangle" in obj.shape:
                clickability_score += 2
                reasons.append("regular shape")
            elif "line" in obj.shape:
                clickability_score += 1
                reasons.append("linear element")
            
            # Position factor (strategic positions)
            if obj.region in ["center", "top-center", "bottom-center"]:
                clickability_score += 2
                reasons.append("strategic position")
            elif obj.region in ["top-left", "top-right", "bottom-left", "bottom-right"]:
                clickability_score += 1
                reasons.append("corner position")
            
            clickable_objects.append({
                'obj': obj,
                'center': (center_row, center_col),
                'score': clickability_score,
                'reasons': reasons
            })
        
        # Sort by clickability score (highest first)
        clickable_objects.sort(key=lambda x: x['score'], reverse=True)
        
        summary = f"🎯 PRIORITIZED CLICKABLE COORDINATES ({len(clickable_objects)} objects):\n\n"
        
        # Show top 10 most clickable objects with coordinates
        for i, item in enumerate(clickable_objects[:10], 1):
            obj = item['obj']
            center = item['center']
            score = item['score']
            reasons = item['reasons']
            
            priority = "HIGH" if score >= 6 else "MEDIUM" if score >= 3 else "LOW"
            
            summary += f"  {i}. [{center[1]}, {center[0]}] - {obj.color} {obj.shape} in {obj.region}\n"
            summary += f"     Priority: {priority} (score: {score}) - {', '.join(reasons)}\n"
            summary += f"     Size: {obj.size} pixels, Bounds: rows {obj.bounds[0]}-{obj.bounds[1]}, cols {obj.bounds[2]}-{obj.bounds[3]}\n\n"
        
        # Add summary of coordinate format
        if clickable_objects:
            summary += "💡 COORDINATE FORMAT: [x, y] where x=column, y=row\n"
            summary += "💡 RECOMMENDED: Try HIGH priority coordinates first, then MEDIUM priority\n"
            
            # Extract just the coordinates for easy reference
            top_coords = [f"[{item['center'][1]}, {item['center'][0]}]" for item in clickable_objects[:5]]
            summary += f"💡 TOP 5 COORDINATES: {', '.join(top_coords)}\n"
        
        return summary
