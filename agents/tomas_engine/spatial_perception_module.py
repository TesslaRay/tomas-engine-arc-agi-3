# numpy for matrix operations
import numpy as np

# dataclasses for object info and change analysis
from dataclasses import dataclass

# typing for type hints
from typing import Optional, Tuple, List, Dict, Set

# import gemini service and image utils
from ..services.gemini_service import GeminiService
from ..image_utils import grid_to_image

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
    ACTION_NAMES = {1: "up", 2: "down", 3: "left", 4: "right", 5: "space", 6: "click"}
    COLOR_NAMES = {
        0: "white", 1: "blue", 2: "gray", 3: "dark-gray", 4: "darker-gray", 5: "black",
        6: "brown", 7: "light-gray", 8: "red", 9: "blue", 10: "green",
        11: "yellow", 12: "orange", 13: "magenta", 14: "light-green", 15: "purple"
    }
    REGION_BOUNDS = {
        "top-left": (0, 21, 0, 21), "top-center": (0, 21, 21, 43), "top-right": (0, 21, 43, 64),
        "center-left": (21, 43, 0, 21), "center": (21, 43, 21, 43), "center-right": (21, 43, 43, 64),
        "bottom-left": (43, 64, 0, 21), "bottom-center": (43, 64, 21, 43), "bottom-right": (43, 64, 43, 64)
    }
    
    def __init__(self):
        """Initialize the spatial perception module."""
        self.matrix_before_action: Optional[List[List[int]]] = None
        self.pending_action: Optional[int] = None
        self.pending_coordinates: Optional[Tuple[int, int]] = None
        self.action_history: List[Tuple[int, Optional[Tuple[int, int]], str, Optional[ChangeAnalysis]]] = []
        
        # Initialize Gemini service
        try:
            self.gemini_service = GeminiService()
            print("✅ Gemini service initialized in SpatialPerceptionModule")
        except Exception as e:
            print(f"⚠️ Error initializing Gemini in SpatialPerceptionModule: {e}")
            self.gemini_service = None
    
    def prepare_action_analysis(self, matrix_before: List[List[int]], action: int, 
                              coordinates: Optional[Tuple[int, int]] = None) -> None:
        """Prepare analysis by saving the state before the action."""
        self.matrix_before_action = [row[:] for row in matrix_before]
        self.pending_action = action
        self.pending_coordinates = coordinates
    
    def analyze_action_effect(self, matrix_after: List[List[int]]) -> str:
        """Analyze the effect of the pending action after receiving the new state."""
        if self.matrix_before_action is None or self.pending_action is None:
            if not hasattr(self, '_first_action_completed'):
                self.matrix_before_action = [row[:] for row in matrix_after]
                self._first_action_completed = True
                return "First execution - saving initial state for future comparisons."
            return "Error: No pending action to analyze."
        
        difference_matrix = self._calculate_matrix_difference(self.matrix_before_action, matrix_after)
        action_name = self.ACTION_NAMES.get(self.pending_action, f"action {self.pending_action}")
        
        if not np.any(difference_matrix != 0):
            analysis = f"That action ({action_name}) generated no effect on the environment."
            change_analysis = None
        else:
            change_analysis = self._perform_detailed_analysis(difference_matrix, 
                                                           self.matrix_before_action, matrix_after)
            analysis = self._generate_detailed_message(change_analysis)
        
        self.action_history.append((self.pending_action, self.pending_coordinates, 
                                  analysis, change_analysis))
        
        # Clean pending data
        self.matrix_before_action = None
        self.pending_action = None
        self.pending_coordinates = None
        
        return analysis
    
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
                    if not visited[row, col] and matrix_array[row, col] != 0:  # Non-background pixel
                        # Find connected component using flood fill
                        positions = self._flood_fill(matrix_array, visited, row, col, matrix_array[row, col])
                        
                        if positions:  # Only create object if positions found
                            obj_info = self._create_object_info(positions, matrix_array[row, col], object_counter)
                            objects.append(obj_info)
                            object_counter += 1
            
            return objects
            
        except Exception as e:
            print(f"❌ Error detecting objects: {e}")
            return []
    
    def _flood_fill(self, matrix: np.ndarray, visited: np.ndarray, 
                   start_row: int, start_col: int, target_color: int) -> List[Tuple[int, int]]:
        """Flood fill algorithm to find connected components."""
        if (start_row < 0 or start_row >= matrix.shape[0] or 
            start_col < 0 or start_col >= matrix.shape[1] or
            visited[start_row, start_col] or 
            matrix[start_row, start_col] != target_color):
            return []
        
        positions = []
        stack = [(start_row, start_col)]
        
        while stack:
            row, col = stack.pop()
            
            if (row < 0 or row >= matrix.shape[0] or 
                col < 0 or col >= matrix.shape[1] or
                visited[row, col] or 
                matrix[row, col] != target_color):
                continue
            
            visited[row, col] = True
            positions.append((row, col))
            
            # Add 4-connected neighbors (you can change to 8-connected if needed)
            stack.extend([(row-1, col), (row+1, col), (row, col-1), (row, col+1)])
        
        return positions
    
    def _create_object_info(self, positions: List[Tuple[int, int]], 
                           color_value: int, object_id: int) -> ObjectInfo:
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
        color_name = self.COLOR_NAMES.get(color_value % 16, f"color-{color_value}")
        
        return ObjectInfo(
            object_id=f"obj_{object_id}",
            shape=shape,
            color=color_name,
            positions=positions,
            bounds=(min_row, max_row, min_col, max_col),
            region=region,
            size=size
        )
    
    def _get_region_for_position(self, row: int, col: int) -> str:
        """Get region name for a given position."""
        for region_name, (row_start, row_end, col_start, col_end) in self.REGION_BOUNDS.items():
            if row_start <= row < row_end and col_start <= col < col_end:
                return region_name
        return "unknown"
    
    def _compare_objects(self, objects_before: List[ObjectInfo], 
                        objects_after: List[ObjectInfo]) -> Tuple[List[ObjectInfo], List[ObjectInfo]]:
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
        return self.ACTION_NAMES.get(action_number, f"action {action_number}")
    
    def _normalize_matrix(self, matrix) -> Optional[List[List[int]]]:
        """Normalize matrix to valid 2D format."""
        if hasattr(matrix, 'tolist'):
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
    
    def _validate_matrices(self, before: np.ndarray, after: np.ndarray, 
                          difference: np.ndarray) -> bool:
        """Validate matrix dimensions and structure."""
        if before.ndim != 2 or after.ndim != 2:
            print(f"❌ Error: Matrices are not 2D. Before: {before.shape}, After: {after.shape}")
            return False
        
        if before.shape != after.shape:
            print(f"❌ Error: Matrices have different dimensions. Before: {before.shape}, After: {after.shape}")
            return False
        
        if difference.shape != before.shape:
            print(f"❌ Error: Difference matrix has incorrect dimensions. Diff: {difference.shape}, Expected: {before.shape}")
            return False
        
        return True
    
    def _perform_detailed_analysis(self, difference_matrix: np.ndarray, 
                                 matrix_before: List[List[int]], 
                                 matrix_after: List[List[int]]) -> ChangeAnalysis:
        """Perform detailed analysis of detected changes."""
        try:
            before_array = np.array(matrix_before).squeeze()
            after_array = np.array(matrix_after).squeeze()
            
            if not self._validate_matrices(before_array, after_array, difference_matrix):
                return self._create_empty_analysis()
            
            # Detect all objects in both matrices
            objects_before = self.detect_objects_in_matrix(matrix_before)
            objects_after = self.detect_objects_in_matrix(matrix_after)
            
            # Compare objects to find changed and unchanged
            changed_objects, unchanged_objects = self._compare_objects(objects_before, objects_after)
            
            # Calculate basic metrics
            change_positions = list(zip(*np.where(difference_matrix != 0)))
            total_changes = len(change_positions)
            change_percentage = (total_changes / difference_matrix.size) * 100 if difference_matrix.size > 0 else 0.0
            
            # Classify changes
            change_types = self._classify_changes(before_array, after_array, change_positions)
            
            # Additional analysis
            regions_affected = self._identify_affected_regions(change_positions)
            near_coordinates = self._check_proximity_to_coordinates(change_positions)
            directional_consistency = self._analyze_directional_consistency(change_positions, self.pending_action)
            
            # Generate analysis
            mathematical_analysis = self._generate_mathematical_analysis(
                total_changes, change_percentage, change_types, regions_affected, 
                directional_consistency, near_coordinates
            )
            
            detailed_changes = self._analyze_specific_changes(
                before_array.tolist(), after_array.tolist(), change_positions
            )
            
            # Add object analysis
            object_analysis = self._generate_object_analysis(changed_objects, unchanged_objects)
            
            change_analysis = ChangeAnalysis(
                total_changes=total_changes,
                change_percentage=change_percentage,
                appearances=change_types['appearances'],
                disappearances=change_types['disappearances'],
                transformations=change_types['transformations'],
                regions_affected=regions_affected,
                near_coordinates=near_coordinates,
                directional_consistency=directional_consistency,
                change_positions=change_positions,
                mathematical_analysis=mathematical_analysis + "\n\n" + detailed_changes + "\n\n" + object_analysis,
                changed_objects=changed_objects,
                unchanged_objects=unchanged_objects,
                all_objects_before=objects_before,
                all_objects_after=objects_after
            )
            
            # Add Gemini interpretation if available
            if self.gemini_service:
                try:
                    change_analysis.gemini_interpretation = self._get_gemini_visual_interpretation(
                        matrix_before, matrix_after, change_analysis
                    )
                except Exception as e:
                    print(f"⚠️ Error in Gemini interpretation: {e}")
                    change_analysis.gemini_interpretation = "Error in visual interpretation"
            
            return change_analysis
            
        except Exception as e:
            print(f"❌ Error in detailed analysis: {e}")
            return self._create_empty_analysis()
    
    def _generate_object_analysis(self, changed_objects: List[ObjectInfo], 
                                 unchanged_objects: List[ObjectInfo]) -> str:
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
    
    def _classify_changes(self, before_array: np.ndarray, after_array: np.ndarray, 
                         change_positions: List[Tuple[int, int]]) -> dict:
        """Classify changes into appearances, disappearances, and transformations."""
        appearances = disappearances = transformations = 0
        
        for row, col in change_positions:
            if (0 <= row < before_array.shape[0] and 0 <= col < before_array.shape[1]):
                before_val = before_array[row, col]
                after_val = after_array[row, col]
                
                if before_val == 0 and after_val != 0:
                    appearances += 1
                elif before_val != 0 and after_val == 0:
                    disappearances += 1
                else:
                    transformations += 1
        
        return {'appearances': appearances, 'disappearances': disappearances, 'transformations': transformations}
    
    def _identify_affected_regions(self, change_positions: List[Tuple[int, int]]) -> List[str]:
        """Identify which regions of the map were affected."""
        if not change_positions:
            return []
        
        regions = []
        for region_name, (row_start, row_end, col_start, col_end) in self.REGION_BOUNDS.items():
            if any(row_start <= row < row_end and col_start <= col < col_end 
                   for row, col in change_positions):
                regions.append(region_name)
        
        return regions
    
    def _check_proximity_to_coordinates(self, change_positions: List[Tuple[int, int]]) -> bool:
        """Check if changes are near the clicked coordinates."""
        if not self.pending_coordinates:
            return False
        
        coord_x, coord_y = self.pending_coordinates
        return any(abs(row - coord_y) <= 3 and abs(col - coord_x) <= 3 
                  for row, col in change_positions)
    
    def _analyze_directional_consistency(self, change_positions: List[Tuple[int, int]], 
                                       action: int) -> Optional[str]:
        """Analyze if changes are consistent with the action direction."""
        if not change_positions or action not in [1, 2, 3, 4] or len(change_positions) < 2:
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
    
    def _generate_mathematical_analysis(self, total_changes: int, change_percentage: float,
                                      change_types: dict, regions_affected: List[str],
                                      directional_consistency: Optional[str], 
                                      near_coordinates: bool) -> str:
        """Generate detailed mathematical analysis."""
        action_name = self.ACTION_NAMES.get(self.pending_action, f"action {self.pending_action}")
        
        analysis = f"🔢 MATHEMATICAL ANALYSIS: The action ({action_name}) generated {total_changes} changes"
        
        if change_percentage > 1.0:
            analysis += f" ({change_percentage:.1f}% of the map)"
        
        # Change types
        if change_types['appearances'] > 0:
            analysis += f"\n📈 Appearances: {change_types['appearances']} pixels (background → color)"
        if change_types['disappearances'] > 0:
            analysis += f"\n📉 Disappearances: {change_types['disappearances']} pixels (color → background)"
        if change_types['transformations'] > 0:
            analysis += f"\n🔄 Transformations: {change_types['transformations']} pixels (color change)"
        
        # Regions
        if regions_affected:
            if len(regions_affected) == 1:
                analysis += f"\n🗺️  Affected region: {regions_affected[0]}"
            elif len(regions_affected) <= 3:
                analysis += f"\n🗺️  Affected regions: {', '.join(regions_affected)}"
            else:
                analysis += f"\n🗺️  Changes distributed across {len(regions_affected)} regions"
        
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
    
    def _analyze_specific_changes(self, matrix_before: List[List[int]], 
                                matrix_after: List[List[int]], 
                                change_positions: List[Tuple[int, int]]) -> str:
        """Generate detailed analysis of specific changes by position."""
        if not change_positions:
            return "🔍 SPECIFIC CHANGES: None detected"
        
        before_array = np.array(matrix_before)
        after_array = np.array(matrix_after)
        
        specific_changes = []
        for row, col in change_positions:
            if (0 <= row < before_array.shape[0] and 0 <= col < before_array.shape[1]):
                before_val = before_array[row, col]
                after_val = after_array[row, col]
                
                before_color = self.COLOR_NAMES.get(before_val % 16, f"color-{before_val}")
                after_color = self.COLOR_NAMES.get(after_val % 16, f"color-{after_val}")
                
                specific_changes.append(f"({row},{col}): {before_color} → {after_color}")
        
        movement_analysis = self._detect_movement_groups(matrix_before, matrix_after, change_positions)
        
        detailed_report = f"🔍 SPECIFIC CHANGES DETECTED:\n"
        detailed_report += f"📍 COMPLETE LIST OF CHANGES ({len(specific_changes)} total):\n"
        for i, change in enumerate(specific_changes, 1):
            detailed_report += f"  {i}. {change}\n"
        
        if movement_analysis:
            detailed_report += f"\n🔄 MOVEMENT ANALYSIS:\n{movement_analysis}"
        
        return detailed_report
    
    def _detect_movement_groups(self, matrix_before: List[List[int]], 
                              matrix_after: List[List[int]], 
                              change_positions: List[Tuple[int, int]]) -> str:
        """Detect groups of pixels that move together."""
        before_array = np.array(matrix_before)
        after_array = np.array(matrix_after)
        
        # Find disappearances and appearances
        disappearances = []
        appearances = []
        
        for row, col in change_positions:
            if (0 <= row < before_array.shape[0] and 0 <= col < before_array.shape[1]):
                before_val = before_array[row, col]
                after_val = after_array[row, col]
                
                if before_val != 0 and after_val == 0:
                    color_name = self.COLOR_NAMES.get(before_val % 16, f"color-{before_val}")
                    disappearances.append((row, col, color_name, before_val))
                elif before_val == 0 and after_val != 0:
                    color_name = self.COLOR_NAMES.get(after_val % 16, f"color-{after_val}")
                    appearances.append((row, col, color_name, after_val))
        
        if not disappearances and not appearances:
            return "Only color changes, no movements detected"
        
        # Group by colors and analyze movements
        disappeared_by_color = self._group_by_color(disappearances)
        appeared_by_color = self._group_by_color(appearances)
        
        movement_report = "🚀 POTENTIAL MOVEMENTS DETECTED:\n" if disappeared_by_color and appeared_by_color else ""
        
        for color in disappeared_by_color:
            if color in appeared_by_color:
                movement_report += self._analyze_color_movement(
                    disappeared_by_color[color], appeared_by_color[color], color
                )
        
        return movement_report if movement_report else "No clear movement patterns detected"
    
    def _group_by_color(self, positions: List[Tuple[int, int, str, int]]) -> dict:
        """Group positions by color."""
        grouped = {}
        for row, col, color, val in positions:
            if color not in grouped:
                grouped[color] = []
            grouped[color].append((row, col, val))
        return grouped
    
    def _analyze_color_movement(self, disappeared: List[Tuple[int, int, int]], 
                               appeared: List[Tuple[int, int, int]], color: str) -> str:
        """Analyze movement for a specific color."""
        if len(disappeared) != len(appeared):
            return ""
        
        # Calculate average movement vector
        total_row_shift = sum(appeared[i][0] - disappeared[i][0] for i in range(len(disappeared)))
        total_col_shift = sum(appeared[i][1] - disappeared[i][1] for i in range(len(disappeared)))
        
        if len(disappeared) > 0:
            avg_row_shift = total_row_shift / len(disappeared)
            avg_col_shift = total_col_shift / len(disappeared)
            
            direction = self._format_direction(avg_row_shift, avg_col_shift)
            
            movement_report = f"  • {color}: {len(disappeared)} pixels moved {direction}\n"
            movement_report += f"    From: {disappeared}\n"
            movement_report += f"    To: {appeared}\n"
            return movement_report
        
        return ""
    
    def _format_direction(self, row_shift: float, col_shift: float) -> str:
        """Format movement direction as string."""
        direction_parts = []
        
        if row_shift > 0:
            direction_parts.append(f"{abs(row_shift):.1f} downward")
        elif row_shift < 0:
            direction_parts.append(f"{abs(row_shift):.1f} upward")
        
        if col_shift > 0:
            direction_parts.append(f"{abs(col_shift):.1f} rightward")
        elif col_shift < 0:
            direction_parts.append(f"{abs(col_shift):.1f} leftward")
        
        return ", ".join(direction_parts)
    
    def _get_gemini_visual_interpretation(self, matrix_before: List[List[int]], 
                                         matrix_after: List[List[int]], 
                                         analysis: ChangeAnalysis) -> str:
        """Get visual interpretation from Gemini based on the two images."""
        try:
            # Validate matrices
            if not matrix_before or not matrix_before[0] or not matrix_after or not matrix_after[0]:
                return "Error: matrices are empty"
            
            # Normalize matrices
            normalized_before = self._normalize_matrix(matrix_before)
            normalized_after = self._normalize_matrix(matrix_after)
            
            if not normalized_before or not normalized_after:
                return "Error in matrix normalization"
            
            # Convert to grid format
            grid_before = [normalized_before]
            grid_after = [normalized_after]
            
            action_name = self.ACTION_NAMES.get(self.pending_action, f"action {self.pending_action}")
            
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
            
            prompt = self._build_enhanced_gemini_prompt(action_name, analysis)
            
            print(f"\n🤖 === CONSULTING GEMINI FOR VISUAL ANALYSIS ===")
            print(f"🔄 Sending before/after images for action: {action_name}")

            print(f"\n🤖 === PROMPT ===")   
            print(prompt)
            
            response = self.gemini_service.generate_with_images_sync(
                prompt=prompt,
                images=[image_before, image_after],
                system_prompt="You are an intelligent visual analyst specializing in interpreting changes in puzzle images. Your goal is to group pixels into coherent objects and detect logical movements based on the provided mathematical data. Provide visual analysis that a human would understand intuitively."
            )
            
            print(f"✅ Response received from Gemini ({response.duration_ms}ms)")
            print(f"📝 Tokens used: {response.usage.get('total_tokens', 'N/A') if hasattr(response, 'usage') and response.usage else 'N/A'}")
            print("=" * 50)
            
            return response.content.strip()
            
        except Exception as e:
            print(f"❌ Error in Gemini visual interpretation: {e}")
            return "Error getting visual interpretation"
    
    def _build_enhanced_gemini_prompt(self, action_name: str, analysis: ChangeAnalysis) -> str:
        """Build the enhanced prompt for Gemini analysis including unchanged objects."""
        changed_objects_info = ""
        unchanged_objects_info = ""
        
        if analysis.changed_objects:
            changed_objects_info = "\n### CHANGED OBJECTS:\n"
            for obj in analysis.changed_objects:
                changed_objects_info += f"- {obj.object_id}: {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"
        
        if analysis.unchanged_objects:
            unchanged_objects_info = "\n### UNCHANGED OBJECTS:\n"
            for obj in analysis.unchanged_objects:
                unchanged_objects_info += f"- {obj.object_id}: {obj.shape} {obj.color} in {obj.region} ({obj.size} pixels)\n"
        
        return f"""
## ROLE: INTELLIGENT VISUAL PATTERN ANALYZER

Interpret pixel-level changes as abstract objects and transformations for ARC AGI reasoning.

## PROVIDED DATA:

- **IMAGE 1**: BEFORE "{action_name}" action
- **IMAGE 2**: AFTER "{action_name}" action
- **MATHEMATICAL DATA**: Complete list of pixel changes
- **OBJECT DATA**: Pre-identified objects (changed and unchanged)

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
- Block_A: 4x8 solid rectangle of yellow at (40,40)-(43,47)
- Bar_B: 4x24 solid rectangle of gray at (32,0)-(35,23)
- Marker_C: 1x1 pixel of light-green at (0,63)
- Anchor_D: 2x2 square of blue at (10,10)-(11,11) [UNCHANGED]

🔄 TRANSFORMATION SUMMARY:
- Block_A: TRANSLATION - moved 8 pixels upward
- Bar_B: MATERIALIZATION - appeared in left region
- Large_Area: CLEARING - rectangular region reset to white background
- Marker_C: COLOR_CHANGE - light-green to white

⚡ UNCHANGED OBJECTS ANALYSIS:
- Anchor_D: POSITIONAL_ANCHOR - serves as reference point in top-left
- Border_Objects: STRUCTURAL_BARRIERS - define boundaries for movement
- Pattern_Core: STABILITY_CENTER - maintains grid structure

📐 SPATIAL RELATIONSHIPS:
- Block_A maintains horizontal alignment with Anchor_D after translation
- Bar_B aligns with grid structure defined by unchanged objects
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
            image.save(img_buffer, format='PNG')
            img_data = img_buffer.getvalue()
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            print(f"\033]1337;File=inline=1:{img_base64}\a")
            
        except Exception as e:
            print(f"⚠️ Error displaying image in iTerm2: {e}")
    
    def _generate_detailed_message(self, analysis: ChangeAnalysis) -> str:
        """Generate combined message with mathematical and visual analysis from Gemini."""
        message = analysis.mathematical_analysis
        message += "\n" + "="*50
        
        if analysis.gemini_interpretation:
            message += f"\n🎨 VISUAL INTERPRETATION:\n{analysis.gemini_interpretation}"
        else:
            message += f"\n🎨 VISUAL INTERPRETATION: Not available"
        
        return message
    
    def get_gemini_interpretation_only(self) -> Optional[str]:
        """Get only the Gemini visual interpretation from the last analysis."""
        if not self.action_history:
            return None
        
        last_analysis = self.action_history[-1][3]  # ChangeAnalysis object
        if last_analysis and last_analysis.gemini_interpretation:
            return last_analysis.gemini_interpretation
        
        # If no Gemini interpretation available, check if there were no changes
        if last_analysis and last_analysis.total_changes == 0:
            return "🎯 DETECTED OBJECTS:\n- No changes detected in the environment\n\n🔄 DETECTED MOVEMENTS:\n- No movements detected\n\n📍 SPECIFIC CHANGES:\n- Environment remained unchanged"
        
        return None
    
    def get_unchanged_objects_only(self) -> Optional[List[ObjectInfo]]:
        """Get only the unchanged objects from the last analysis."""
        if not self.action_history:
            return None
        
        last_analysis = self.action_history[-1][3]  # ChangeAnalysis object
        if last_analysis:
            return last_analysis.unchanged_objects
        
        return None
    
    def get_changed_objects_only(self) -> Optional[List[ObjectInfo]]:
        """Get only the changed objects from the last analysis."""
        if not self.action_history:
            return None
        
        last_analysis = self.action_history[-1][3]  # ChangeAnalysis object
        if last_analysis:
            return last_analysis.changed_objects
        
        return None
    
    def get_all_objects_summary(self) -> Optional[str]:
        """Get a summary of all objects (changed and unchanged) from the last analysis."""
        if not self.action_history:
            return None
        
        last_analysis = self.action_history[-1][3]  # ChangeAnalysis object
        if not last_analysis:
            return None
        
        summary = "📋 COMPLETE OBJECT SUMMARY:\n\n"
        
        # Changed objects
        if last_analysis.changed_objects:
            summary += f"🔄 CHANGED OBJECTS ({len(last_analysis.changed_objects)}):\n"
            for i, obj in enumerate(last_analysis.changed_objects, 1):
                summary += f"  {i}. {obj.object_id}: {obj.shape} {obj.color} in {obj.region}\n"
        else:
            summary += "🔄 CHANGED OBJECTS: None\n"
        
        summary += "\n"
        
        # Unchanged objects
        if last_analysis.unchanged_objects:
            summary += f"⚡ UNCHANGED OBJECTS ({len(last_analysis.unchanged_objects)}):\n"
            for i, obj in enumerate(last_analysis.unchanged_objects, 1):
                summary += f"  {i}. {obj.object_id}: {obj.shape} {obj.color} in {obj.region}\n"
        else:
            summary += "⚡ UNCHANGED OBJECTS: None\n"
        
        # Statistics
        total_changed = len(last_analysis.changed_objects) if last_analysis.changed_objects else 0
        total_unchanged = len(last_analysis.unchanged_objects) if last_analysis.unchanged_objects else 0
        total_objects = total_changed + total_unchanged
        
        if total_objects > 0:
            unchanged_percentage = (total_unchanged / total_objects) * 100
            summary += f"\n📊 STATISTICS:\n"
            summary += f"  • Total objects: {total_objects}\n"
            summary += f"  • Changed: {total_changed} ({100-unchanged_percentage:.1f}%)\n"
            summary += f"  • Unchanged: {total_unchanged} ({unchanged_percentage:.1f}%)\n"
        
        return summary
    
    def _calculate_matrix_difference(self, matrix_before: List[List[int]], 
                                   matrix_after: List[List[int]]) -> np.ndarray:
        """Calculate the difference between two matrices."""
        try:
            before = np.array(matrix_before, dtype=np.int32).squeeze()
            after = np.array(matrix_after, dtype=np.int32).squeeze()
            
            if before.shape != after.shape:
                print(f"❌ Error: Matrices have different dimensions - Before: {before.shape}, After: {after.shape}")
                min_rows = min(before.shape[0], after.shape[0]) if before.ndim >= 1 and after.ndim >= 1 else 1
                min_cols = min(before.shape[1], after.shape[1]) if before.ndim >= 2 and after.ndim >= 2 else 1
                
                if before.ndim == 2 and after.ndim == 2:
                    before = before[:min_rows, :min_cols]
                    after = after[:min_rows, :min_cols]
                else:
                    print("❌ Cannot reconcile dimensions, using default matrices")
                    return np.zeros((64, 64), dtype=np.int32)
            
            if before.ndim != 2 or after.ndim != 2:
                print(f"❌ Error: Matrices are not 2D after processing - Before: {before.ndim}D, After: {after.ndim}D")
                return np.zeros((64, 64), dtype=np.int32)
            
            return after - before
            
        except Exception as e:
            print(f"❌ Error calculating matrix difference: {e}")
            return np.zeros((64, 64), dtype=np.int32)
    
    def _create_empty_analysis(self) -> ChangeAnalysis:
        """Create an empty analysis in case of error."""
        return ChangeAnalysis(
            total_changes=0, change_percentage=0.0, appearances=0, disappearances=0,
            transformations=0, regions_affected=[], near_coordinates=False,
            directional_consistency=None, change_positions=[], 
            mathematical_analysis="Error in mathematical analysis",
            changed_objects=[], unchanged_objects=[], 
            all_objects_before=[], all_objects_after=[]
        )
    
    def get_action_history(self) -> List[Tuple[int, Optional[Tuple[int, int]], str, Optional[ChangeAnalysis]]]:
        """Get the complete history of analyzed actions."""
        return self.action_history.copy()
    
    def get_last_analysis(self) -> Optional[str]:
        """Get the last analysis performed."""
        return self.action_history[-1][2] if self.action_history else None
    
    def get_detailed_last_analysis(self) -> Optional[ChangeAnalysis]:
        """Get the last detailed analysis performed."""
        return self.action_history[-1][3] if self.action_history else None