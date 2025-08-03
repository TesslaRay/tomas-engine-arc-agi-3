# numpy for matrix operations
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List
from ..services.gemini_service import GeminiService
from ..image_utils import grid_to_image


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


class SpatialPerceptionModule:
    """Spatial perception module that analyzes action effects on environment."""
    
    # Constants
    ACTION_NAMES = {1: "up", 2: "down", 3: "left", 4: "right", 5: "space", 6: "click"}
    COLOR_NAMES = {
        0: "white", 1: "blue", 2: "green", 3: "gray", 4: "dark-gray", 5: "black",
        6: "brown", 7: "light-gray", 8: "red", 9: "light-blue", 10: "light-green",
        11: "cyan", 12: "orange", 13: "magenta", 14: "yellow", 15: "purple"
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
                mathematical_analysis=mathematical_analysis + "\n\n" + detailed_changes
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
            
            prompt = self._build_gemini_prompt(action_name, analysis)
            
            print(f"\n🤖 === CONSULTING GEMINI FOR VISUAL ANALYSIS ===")
            print(f"🔄 Sending before/after images for action: {action_name}")
            
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
    
    def _build_gemini_prompt(self, action_name: str, analysis: ChangeAnalysis) -> str:
        """Build the prompt for Gemini analysis."""
        return f"""
Act as an INTELLIGENT VISUAL PATTERN ANALYZER that interprets image changes:

## PROVIDED IMAGES:
- **IMAGE 1**: BEFORE "{action_name}" action  
- **IMAGE 2**: AFTER "{action_name}" action

## EXACT MATHEMATICAL DATA:
{analysis.mathematical_analysis}

## ANALYSIS INSTRUCTIONS:

### 1. OBJECT/SHAPE IDENTIFICATION
- Analyze the provided pixel-by-pixel changes
- **GROUP** contiguous pixels of same color that change together
- **IDENTIFY** geometric shapes (squares, rectangles, lines)
- **RECOGNIZE** composite objects (e.g., blue square + orange square = bicolor object)

### 2. MOVEMENT DETECTION
- If pixels **disappear** in zone A AND **appear** in adjacent zone B → it's MOVEMENT
- If pixels change color without spatial pattern → it's TRANSFORMATION
- **Calculate movement direction** based on coordinate changes

### 3. REQUIRED RESPONSE FORMAT:
```
🎯 DETECTED OBJECTS:
- [Object description]: [shape] of [color] in region [location]

🔄 DETECTED MOVEMENTS:
- [Object]: moved [distance] pixels toward [direction]
- [Object]: color changed from [color1] to [color2]

📍 SPECIFIC CHANGES:
- Region [location]: [visual change description]
```

### 4. INTERPRETATION RULES:
✅ **YOU SHOULD:**
- Group contiguous pixels that change together as single objects
- Infer movements when there's disappearance + appearance in nearby zones
- Describe simple geometric shapes (square, rectangle, line)
- Use coordinates to calculate movement directions

❌ **YOU SHOULD NOT:**
- Invent changes not present in mathematical data
- Use complex semantic terms ("characters", "buildings")
- Describe each pixel individually if they form coherent shapes

## IDEAL RESPONSE EXAMPLE:
```
🎯 DETECTED OBJECTS:
- Small square: 1x1 purple pixel in top-left corner (2,2)
- Horizontal rectangle: 8x2 orange pixels in bottom-center region (48,40 to 49,47)

🔄 DETECTED MOVEMENTS:  
- Purple square: disappeared (changed to gray)
- Orange rectangle: moved 8 pixels rightward

📍 SPECIFIC CHANGES:
- Region (2,2): purple square disappeared
- Bottom-center region: orange rectangle shifted horizontally right
```

**GOAL**: Provide intuitive visual description that a human would understand when viewing the images.
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
            mathematical_analysis="Error in mathematical analysis"
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