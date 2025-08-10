import random
import time
from typing import Dict, Any, Optional

from ...structs import FrameData, GameAction

# memory
from .shared_memory import SharedMemory

# services
from agents.services.gemini_service import GeminiService

# structured data
from .data_structures import (
    PsychologyState,
    AisthesisStructuredData,
    SophiaStructuredData,
    ProgressAnalysis,
)

# constants
from agents.tomas_engine.constants import get_action_name, string_to_game_action

# parser
from agents.tomas_engine.utils.response_parser import extract_action_from_response


class HumanPsychologyEngine:
    """Simulates human psychology during the game"""

    def __init__(self):
        # Emotional/cognitive states (more conservative initial values)
        self.curiosity_level = 0.8  # Slightly lower initial curiosity
        self.confidence = 0.2  # Slightly higher initial confidence
        self.frustration = 0.0  # Starts calm
        self.patience = 1.0  # Full patience initially

        # Behavior counters
        self.consecutive_failures = 0
        self.consecutive_no_progress = 0
        self.total_turns = 0
        self.successful_actions = 0
        self.last_progress_turn = 0

        # Mental states with stability tracking
        self.current_state = "exploring"
        self.turns_in_current_state = 0
        self.state_stability_threshold = 3  # Need 3 confirmations to change state
        self.pending_state_change = None
        self.state_change_confidence = 0

        # Enhanced memory and history
        self.state_history = []
        self.emotion_history = []
        self.successful_patterns = []
        self.failed_patterns = []
        self.confidence_trend_window = []
        self.recent_success_rate = 0.5  # Start neutral

        self.mental_states = {
            "exploring": {
                "description": "Focus on discovering new mechanics",
                "prompt_modifier": "Be curious, try different actions to understand the game",
                "sequence_preference": [1, 2],
                "risk_tolerance": 0.8,
            },
            "pattern_seeking": {
                "description": "Look for repetitions and consistent rules",
                "prompt_modifier": "Analyze patterns, look for connections between actions and effects",
                "sequence_preference": [2, 3],
                "risk_tolerance": 0.6,
            },
            "hypothesis_testing": {
                "description": "Test if your hypotheses are correct",
                "prompt_modifier": "Test specific hypotheses, follow a systematic plan",
                "sequence_preference": [1, 2],
                "risk_tolerance": 0.4,
            },
            "optimization": {
                "description": "Improve strategies that already work",
                "prompt_modifier": "Use actions that have proven to work, optimize sequences",
                "sequence_preference": [3, 4, 5, 1, 1],
                "risk_tolerance": 0.2,
            },
            "frustrated": {
                "description": "Take a completely different approach",
                "prompt_modifier": "Change strategy completely, try something radical and different",
                "sequence_preference": [1],
                "risk_tolerance": 0.9,
            },
        }

    def update_psychology(self, progress_type: str, confidence_adjustment: float = 0.0):
        """Update the psychological state based on results"""
        self.total_turns += 1
        self.turns_in_current_state += 1

        # Update counters based on progress type
        if progress_type in ["MAJOR_PROGRESS", "MINOR_PROGRESS"]:
            self.last_progress_turn = self.total_turns
            self.consecutive_no_progress = 0
            self.consecutive_failures = 0
            self.successful_actions += 1
        elif progress_type == "VALID_ACTION":
            # Reset failure count but don't count as full progress
            self.consecutive_failures = 0
            self.consecutive_no_progress += 1
        else:  # NO_EFFECT
            self.consecutive_failures += 1
            self.consecutive_no_progress += 1

        # Adjust confidence based on progress type
        base_confidence_change = 0.0
        base_frustration_change = 0.0
        base_patience_change = 0.0

        # MORE GRADUAL confidence changes (reduced from 0.15/0.05 to 0.08/0.03)
        if progress_type == "MAJOR_PROGRESS":
            # Reduced confidence boost for major progress
            base_confidence_change = 0.08  # Was 0.15
            base_frustration_change = -0.08  # Was -0.15
            base_patience_change = 0.05  # Was 0.1
        elif progress_type == "MINOR_PROGRESS":
            # Reduced confidence boost for visible changes
            base_confidence_change = 0.03  # Was 0.05
            base_frustration_change = -0.03  # Was -0.05
            base_patience_change = 0.02  # Was 0.03
        elif progress_type == "VALID_ACTION":
            # Even smaller changes for valid actions
            base_confidence_change = 0.01  # Was 0.02
            base_frustration_change = 0.01  # Was 0.02
            base_patience_change = 0.0
        else:  # NO_EFFECT
            # Reduced penalty for useless actions
            base_confidence_change = -0.03  # Was -0.05
            base_frustration_change = 0.08  # Was 0.2 (much more gradual)
            base_patience_change = -0.05  # Was -0.1

        # Apply EMOTIONAL STABILITY modifier - reduce changes if emotionally unstable
        stability = self._calculate_emotional_stability()
        stability_modifier = max(0.5, stability)  # At least 50% of the change

        base_confidence_change *= stability_modifier
        base_frustration_change *= stability_modifier
        base_patience_change *= stability_modifier

        # Apply changes with memory consideration
        total_confidence_change = base_confidence_change + confidence_adjustment

        # Update emotional state with MOMENTUM consideration
        self._update_with_momentum("confidence", total_confidence_change)
        self._update_with_momentum("frustration", base_frustration_change)
        self._update_with_momentum("patience", base_patience_change)

        # Track confidence trend
        if not hasattr(self, "confidence_trend_window"):
            self.confidence_trend_window = []
        self.confidence_trend_window.append(self.confidence)
        if len(self.confidence_trend_window) > 10:
            self.confidence_trend_window = self.confidence_trend_window[-10:]

        # Update recent success rate
        self._update_success_rate(progress_type)

        if confidence_adjustment != 0.0:
            print(
                f"🎯 Confidence adjustment: {confidence_adjustment:+.2f} (prediction accuracy)"
            )
            print(
                f"📊 Total confidence change: {total_confidence_change:+.2f} (progress: {base_confidence_change:+.2f} + prediction: {confidence_adjustment:+.2f})"
            )

        # More gradual curiosity decay
        if progress_type in ["MAJOR_PROGRESS", "MINOR_PROGRESS"]:
            curiosity_decay = 0.005  # Even less decay for progress
        elif progress_type == "VALID_ACTION":
            curiosity_decay = 0.015  # Reduced decay
        else:
            curiosity_decay = 0.025  # Reduced decay for failures

        self.curiosity_level = max(0.1, self.curiosity_level - curiosity_decay)

        # Update emotional history
        current_emotions = {
            "confidence": self.confidence,
            "frustration": self.frustration,
            "curiosity": self.curiosity_level,
            "patience": self.patience,
        }
        self.emotion_history.append(current_emotions)
        self.state_history.append(self.current_state)

        # Keep only recent history
        if len(self.emotion_history) > 10:
            self.emotion_history = self.emotion_history[-10:]
        if len(self.state_history) > 10:
            self.state_history = self.state_history[-10:]

        # STABLE transition mental states (requires multiple confirmations)
        self._stable_transition_mental_state()

    def _transition_mental_state(self):
        """Change mental state based on current psychology"""
        old_state = self.current_state

        # High frustration -> frustrated
        if self.frustration > 0.7:
            self.current_state = "frustrated"

        # Long time without progress -> frustrated
        elif self.consecutive_no_progress > 8:
            self.current_state = "frustrated"

        # Many consecutive useless actions -> frustrated
        elif self.consecutive_failures > 4:
            self.current_state = "frustrated"

        # High confidence -> optimization
        elif self.confidence > 0.8 and self.successful_actions > 3:
            self.current_state = "optimization"

        # Medium confidence and some successes -> hypothesis_testing
        elif self.confidence > 0.5 and self.successful_actions > 1:
            self.current_state = "hypothesis_testing"

        # Low curiosity but some progress -> pattern_seeking
        elif self.curiosity_level < 0.5 and self.successful_actions > 0:
            self.current_state = "pattern_seeking"

        # Default: exploring
        else:
            self.current_state = "exploring"

        # Reset counter si cambió de estado
        if old_state != self.current_state:
            self.turns_in_current_state = 0
            print(f"🧠 Estado mental cambió: {old_state} -> {self.current_state}")
            print(
                f"   Frustración: {self.frustration:.2f}, Confianza: {self.confidence:.2f}, Curiosidad: {self.curiosity_level:.2f}"
            )

    def get_psychological_prompt_modifier(self) -> str:
        """Get the prompt modifier based on the psychological state"""
        state_info = self.mental_states[self.current_state]

        base_modifier = state_info["prompt_modifier"]

        # Add specific modifiers based on psychological levels
        if self.frustration > 0.8:
            base_modifier += " IMPORTANT: You are very frustrated, you need to try something COMPLETELY different."
        elif self.frustration > 0.5:
            base_modifier += " You are a bit frustrated, consider changing your focus."

        if self.confidence > 0.8:
            base_modifier += " You have high confidence in your abilities."
        elif self.confidence < 0.3:
            base_modifier += " Your confidence is low, be more cautious."

        if self.curiosity_level < 0.3:
            base_modifier += (
                " Your curiosity has decreased, focus on more direct actions."
            )

        return base_modifier

    def get_sequence_length_preference(self) -> int:
        """Get the sequence length preference based on the mental state"""
        preferences = self.mental_states[self.current_state]["sequence_preference"]

        # In frustrated mode, always prefer short sequences for quick changes
        if self.current_state == "frustrated":
            return 1

        # Adjust based on confidence
        if self.confidence > 0.8:
            return max(preferences)  # Longer sequences when there is confidence
        elif self.confidence < 0.3:
            return min(preferences)  # Short sequences when there is low confidence
        else:
            return random.choice(preferences)

    def _calculate_emotional_stability(self) -> float:
        """Calculate emotional stability based on recent history"""
        if len(self.emotion_history) < 3:
            return 0.5  # Neutral stability for new systems

        # Calculate variance in recent emotions
        recent_emotions = (
            self.emotion_history[-5:]
            if len(self.emotion_history) >= 5
            else self.emotion_history
        )

        frustration_values = [e.get("frustration", 0.5) for e in recent_emotions]
        confidence_values = [e.get("confidence", 0.5) for e in recent_emotions]

        # Calculate variance (low variance = high stability)
        def variance(values):
            if len(values) < 2:
                return 0
            mean_val = sum(values) / len(values)
            return sum((x - mean_val) ** 2 for x in values) / len(values)

        frustration_var = variance(frustration_values)
        confidence_var = variance(confidence_values)

        # Convert to stability score (higher = more stable)
        avg_variance = (frustration_var + confidence_var) / 2
        stability = max(0.1, 1.0 - min(1.0, avg_variance * 4))  # Scale variance

        return stability

    def _update_with_momentum(self, emotion_type: str, change: float):
        """Update emotion with momentum consideration"""
        current_value = getattr(self, emotion_type)

        # Apply momentum - if we have history, consider the trend
        if len(self.emotion_history) >= 2:
            prev_value = self.emotion_history[-1].get(emotion_type, current_value)
            momentum = current_value - prev_value

            # If change is in same direction as momentum, amplify slightly
            # If opposite direction, dampen the change
            if (change > 0 and momentum > 0) or (change < 0 and momentum < 0):
                momentum_factor = 1.1  # Small amplification
            elif (change > 0 and momentum < 0) or (change < 0 and momentum > 0):
                momentum_factor = 0.8  # Dampen opposing changes
            else:
                momentum_factor = 1.0

            final_change = change * momentum_factor
        else:
            final_change = change

        # Apply change with bounds
        new_value = max(0.0, min(1.0, current_value + final_change))
        setattr(self, emotion_type, new_value)

    def _update_success_rate(self, progress_type: str):
        """Update recent success rate based on progress type"""
        # Weight different progress types
        if progress_type == "MAJOR_PROGRESS":
            success_value = 1.0
        elif progress_type == "MINOR_PROGRESS":
            success_value = 0.7
        elif progress_type == "VALID_ACTION":
            success_value = 0.4
        else:  # NO_EFFECT
            success_value = 0.0

        # Moving average with recent history
        decay_factor = 0.2  # How much to weight new information
        self.recent_success_rate = (
            1 - decay_factor
        ) * self.recent_success_rate + decay_factor * success_value

    def _stable_transition_mental_state(self):
        """Change mental state based on psychology, but require multiple confirmations for stability"""
        # Calculate what the ideal state should be
        ideal_state = self._calculate_ideal_state()

        # If ideal state is different from current state
        if ideal_state != self.current_state:
            # If we already have a pending state change to this state
            if self.pending_state_change == ideal_state:
                self.state_change_confidence += 1
                print(
                    f"🧠 Confirmando cambio de estado a {ideal_state}: {self.state_change_confidence}/{self.state_stability_threshold}"
                )

                # If we have enough confirmations, make the change
                if self.state_change_confidence >= self.state_stability_threshold:
                    old_state = self.current_state
                    self.current_state = ideal_state
                    self.pending_state_change = None
                    self.state_change_confidence = 0
                    self.turns_in_current_state = 0
                    print(
                        f"🧠 Estado mental cambió GRADUALMENTE: {old_state} -> {self.current_state}"
                    )
                    print(
                        f"   Frustración: {self.frustration:.2f}, Confianza: {self.confidence:.2f}, Curiosidad: {self.curiosity_level:.2f}"
                    )
            else:
                # Start a new pending state change
                self.pending_state_change = ideal_state
                self.state_change_confidence = 1
                print(
                    f"🧠 Iniciando transición gradual hacia: {ideal_state} (1/{self.state_stability_threshold})"
                )
        else:
            # Current state matches ideal, reset any pending change
            if self.pending_state_change:
                print(
                    f"🧠 Cancelando transición pendiente, mantiene estado: {self.current_state}"
                )
            self.pending_state_change = None
            self.state_change_confidence = 0

    def _calculate_ideal_state(self) -> str:
        """Calculate what the ideal mental state should be based on current psychology"""
        # High frustration -> frustrated (immediate priority)
        if self.frustration > 0.7:
            return "frustrated"

        # Long time without progress -> frustrated
        elif self.consecutive_no_progress > 8:
            return "frustrated"

        # Many consecutive useless actions -> frustrated
        elif self.consecutive_failures > 4:
            return "frustrated"

        # High confidence and good success rate -> optimization
        elif self.confidence > 0.8 and self.recent_success_rate > 0.6:
            return "optimization"

        # Medium confidence and some successes -> hypothesis_testing
        elif self.confidence > 0.5 and self.successful_actions > 1:
            return "hypothesis_testing"

        # Low curiosity but some progress -> pattern_seeking
        elif self.curiosity_level < 0.5 and self.successful_actions > 0:
            return "pattern_seeking"

        # Default: exploring
        else:
            return "exploring"

    def get_psychology_state(self) -> PsychologyState:
        """Get current psychology state as structured data"""
        # Calculate confidence trend
        if len(self.confidence_trend_window) >= 3:
            recent_conf = self.confidence_trend_window[-3:]
            if recent_conf[-1] > recent_conf[0]:
                trend = "increasing"
            elif recent_conf[-1] < recent_conf[0]:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return PsychologyState(
            current_state=self.current_state,
            frustration=self.frustration,
            confidence=self.confidence,
            curiosity_level=self.curiosity_level,
            patience=self.patience,
            state_history=self.state_history.copy(),
            emotion_history=self.emotion_history.copy(),
            successful_patterns=self.successful_patterns.copy(),
            failed_patterns=self.failed_patterns.copy(),
            recent_success_rate=self.recent_success_rate,
            confidence_trend=trend,
        )


class NucleiLogos:
    """Enhanced Nuclei Logos with Human Psychology"""

    def __init__(self, game_id: str):
        seed = int(time.time() * 1000000) + hash(game_id) % 1000000
        random.seed(seed)

        self.gemini_service = GeminiService()
        self.psychology = HumanPsychologyEngine()

        # Tracking variables for psychology
        self.last_frame_data = None
        self.last_expected_outcome = None  # Store previous prediction for comparison

    def process(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
        aisthesis_analysis: str,
        sophia_reasoning: str,
        aisthesis_data: "AisthesisStructuredData" = None,
        sophia_data: "SophiaStructuredData" = None,
    ) -> list[GameAction]:
        """Process input string and return a list of GameActions."""
        print(f"🗺️ LOGOS is choosing action sequence...")

        # Update psychology based on the previous frame
        progress_type = "FIRST_TURN"
        if self.last_frame_data and len(frames) > 2:
            progress_type = self._detect_progress(
                self.last_frame_data, latest_frame, aisthesis_analysis
            )
            # Note: confidence_adjustment will be extracted from current Gemini response, not here
            self.psychology.update_psychology(progress_type)

        # Save current frame for next time
        self.last_frame_data = latest_frame

        is_first_action_turn = len(frames) == 2

        if is_first_action_turn:
            # First action - always exploratory
            action = random.choice([a for a in GameAction if a is not GameAction.RESET])
            if action.is_simple():
                action.reasoning = f"First exploratory action: {action.value}"
            elif action.is_complex():
                action.set_data(
                    {
                        "x": random.randint(0, 63),
                        "y": random.randint(0, 63),
                    }
                )
            action_sequence = [action]
        else:
            # Use psychology to make decisions
            memory = SharedMemory.get_instance()
            relevant_exp = memory.get_relevant_experience(aisthesis_analysis[:100])
            failure_warnings = memory.get_failure_warnings(aisthesis_analysis[:100])

            # Build prompt with psychological modifiers and structured data
            prompt = self._build_enhanced_logos_prompt(
                aisthesis_analysis,
                sophia_reasoning,
                relevant_exp,
                failure_warnings,
                self.last_expected_outcome,
                aisthesis_data,
                sophia_data,
            )

            logos_response = self.gemini_service.generate_text_sync(
                prompt=prompt,
                game_id=latest_frame.game_id,
                nuclei="logos",
            )

            print(f"\n🤖 LOGOS RESPONSE:")
            print(logos_response.content)

            # Parse with psychological considerations
            action_data = self._parse_action_response(logos_response.content)
            action_sequence_strings = action_data.get("action_sequence", [])

            # Extract and apply confidence adjustment from Gemini's analysis
            confidence_adjustment = action_data.get("confidence_adjustment", 0.0)
            if confidence_adjustment != 0.0:
                # Apply the confidence adjustment that Gemini calculated based on prediction accuracy
                self.psychology.confidence = max(
                    0.0, min(1.0, self.psychology.confidence + confidence_adjustment)
                )
                print(
                    f"🧠 Applied Gemini's confidence adjustment: {confidence_adjustment:+.2f}"
                )

            # Store expected outcome for next iteration
            self.last_expected_outcome = action_data.get(
                "expected_outcome", "Unknown outcome"
            )

            # Apply psychological filters to the sequence
            action_sequence_strings = self._apply_psychological_filters(
                action_sequence_strings
            )

            # Convert string actions to GameActions
            action_sequence = []
            for action_item in action_sequence_strings:
                if isinstance(action_item, dict):
                    action_string = action_item.get("action", "")
                    coordinates = action_item.get("coordinates", [])
                    if len(coordinates) >= 2:
                        x_coord = coordinates[0]
                        y_coord = coordinates[1]
                    else:
                        # Use clickable coordinates from AISTHESIS if available
                        x_coord, y_coord = self._get_fallback_coordinates(
                            aisthesis_data
                        )
                else:
                    action_string = action_item
                    # Use clickable coordinates from AISTHESIS if available
                    x_coord, y_coord = self._get_fallback_coordinates(aisthesis_data)

                action = string_to_game_action(action_string)
                if action:
                    if isinstance(action_item, dict) and "reasoning" in action_item:
                        action.reasoning = action_item["reasoning"]
                    else:
                        action.reasoning = action_data.get(
                            "reasoning", "AI-generated reasoning"
                        )

                    if action.is_complex():
                        action.set_data({"x": x_coord, "y": y_coord})
                        print(
                            f"🎯 Set coordinates for {action_string}: ({x_coord}, {y_coord})"
                        )

                    action_sequence.append(action)
                else:
                    print(f"⚠️ Conversion failed for '{action_string}', skipping")

            # Fallback if no valid actions
            if not action_sequence:
                print("⚠️ No valid actions found, using ACTION1 (up)")
                fallback_action = GameAction.ACTION1
                fallback_action.reasoning = "Fallback due to parsing failure"
                action_sequence = [fallback_action]

        # Print psychological state and sequence
        print(
            f"🧠 State: {self.psychology.current_state} | Progress: {progress_type} | Frustration: {self.psychology.frustration:.2f}, Confidence: {self.psychology.confidence:.2f}"
        )
        sequence_names = [get_action_name(action.value) for action in action_sequence]
        print(f"🤖 LOGOS chose sequence: {sequence_names}")
        return action_sequence

    def _detect_progress(
        self, old_frame: FrameData, new_frame: FrameData, aisthesis_analysis: str
    ) -> str:
        """Enhanced multidimensional progress detection"""

        # Create detailed progress analysis
        progress_analysis = self._create_multidimensional_progress_analysis(
            old_frame, new_frame, aisthesis_analysis
        )

        # Calculate overall progress score
        overall_score = progress_analysis.get_overall_progress_score()

        # Determine progress type based on multidimensional analysis
        if overall_score >= 0.8:
            print(f"🎉 MAJOR_PROGRESS: Overall score {overall_score:.2f}")
            print(
                f"   📊 Breakdown: Spatial={progress_analysis.new_areas_discovered}, Mechanical={progress_analysis.new_interactions_discovered}, Strategic={progress_analysis.sequence_effectiveness:.2f}"
            )
            return "MAJOR_PROGRESS"
        elif overall_score >= 0.5:
            print(f"🔄 MINOR_PROGRESS: Overall score {overall_score:.2f}")
            print(
                f"   📊 Details: Rules confirmed={progress_analysis.rules_confirmed}, Objects moved={progress_analysis.object_positions_changed}"
            )
            return "MINOR_PROGRESS"
        elif overall_score >= 0.2:
            print(f"✅ VALID_ACTION: Overall score {overall_score:.2f}")
            print(f"   📊 Some progress detected in understanding or strategy")
            return "VALID_ACTION"
        else:
            print(f"❌ NO_EFFECT: Overall score {overall_score:.2f}")
            print(f"   📊 No significant progress across any dimension")
            return "NO_EFFECT"

    def _create_multidimensional_progress_analysis(
        self, old_frame: FrameData, new_frame: FrameData, aisthesis_analysis: str
    ) -> ProgressAnalysis:
        """Create comprehensive progress analysis across multiple dimensions"""

        analysis_lower = aisthesis_analysis.lower()

        # 1. SPATIAL PROGRESS ANALYSIS
        new_areas_discovered = any(
            keyword in analysis_lower
            for keyword in [
                "new level",
                "level up",
                "different area",
                "new region",
                "explored",
            ]
        )

        player_position_change = any(
            keyword in analysis_lower
            for keyword in [
                "player moved",
                "player position",
                "moved from",
                "player.*center",
                "player.*region",
            ]
        )

        # Count object position changes
        object_positions_changed = 0
        if "changed objects" in analysis_lower:
            # Try to extract number from text like "changed objects (3 total)"
            import re

            match = re.search(r"changed objects \((\d+)", analysis_lower)
            if match:
                object_positions_changed = int(match.group(1))
            else:
                # Fallback: if objects changed, assume at least 1
                if (
                    "objects that changed" in analysis_lower
                    or "transformation" in analysis_lower
                ):
                    object_positions_changed = 1

        # 2. MECHANICAL PROGRESS ANALYSIS
        new_interactions_discovered = any(
            keyword in analysis_lower
            for keyword in [
                "activated",
                "triggered",
                "interaction",
                "button",
                "switch",
                "door",
                "key",
            ]
        )

        # Rules confirmed (simplified heuristic)
        rules_confirmed = 0
        if any(
            keyword in analysis_lower for keyword in ["confirmed", "proven", "verified"]
        ):
            rules_confirmed = 1

        # Hypotheses generated (simplified heuristic)
        hypotheses_generated = 0
        if any(
            keyword in analysis_lower
            for keyword in ["hypothesis", "theory", "suggests", "might"]
        ):
            hypotheses_generated = 1

        # 3. CONCEPTUAL PROGRESS ANALYSIS
        understanding_improved = any(
            keyword in analysis_lower
            for keyword in [
                "pattern",
                "rule",
                "mechanism",
                "understanding",
                "learned",
                "discovered",
            ]
        )

        objective_clarity_increased = any(
            keyword in analysis_lower
            for keyword in [
                "goal",
                "objective",
                "target",
                "exit",
                "win condition",
                "progress toward",
            ]
        )

        strategy_refined = any(
            keyword in analysis_lower
            for keyword in [
                "strategy",
                "approach",
                "plan",
                "sequence",
                "optimal",
                "efficient",
            ]
        )

        # 4. STRATEGIC PROGRESS ANALYSIS

        # Sequence effectiveness based on whether action had intended effect
        sequence_effectiveness = 0.5  # Default neutral
        if "no effect" in analysis_lower or "no impact" in analysis_lower:
            sequence_effectiveness = 0.0
        elif "major progress" in analysis_lower or "score" in analysis_lower:
            sequence_effectiveness = 1.0
        elif "minor progress" in analysis_lower or "changed" in analysis_lower:
            sequence_effectiveness = 0.7
        elif "valid action" in analysis_lower:
            sequence_effectiveness = 0.4

        # Action precision based on how targeted/specific the action was
        action_precision = 0.6  # Default moderate precision
        if "click" in analysis_lower and "coordinates" in analysis_lower:
            action_precision = 0.9  # Targeted click
        elif any(
            keyword in analysis_lower for keyword in ["specific", "targeted", "precise"]
        ):
            action_precision = 0.8
        elif "random" in analysis_lower or "exploratory" in analysis_lower:
            action_precision = 0.3

        # Goal proximity (simplified heuristic based on score and level progression)
        goal_proximity = 0.3  # Default low proximity
        if hasattr(old_frame, "score") and hasattr(new_frame, "score"):
            if new_frame.score > old_frame.score:
                score_increase = new_frame.score - old_frame.score
                goal_proximity = min(
                    1.0, 0.5 + score_increase * 0.1
                )  # Scale based on score increase

        # Look for goal-related keywords
        if any(
            keyword in analysis_lower
            for keyword in ["exit", "goal", "finish", "complete", "win"]
        ):
            goal_proximity = min(1.0, goal_proximity + 0.3)

        return ProgressAnalysis(
            progress_type="PENDING",  # Will be determined by overall score
            new_areas_discovered=new_areas_discovered,
            player_position_change=player_position_change,
            object_positions_changed=object_positions_changed,
            new_interactions_discovered=new_interactions_discovered,
            rules_confirmed=rules_confirmed,
            hypotheses_generated=hypotheses_generated,
            understanding_improved=understanding_improved,
            objective_clarity_increased=objective_clarity_increased,
            strategy_refined=strategy_refined,
            sequence_effectiveness=sequence_effectiveness,
            action_precision=action_precision,
            goal_proximity=goal_proximity,
        )

    def _apply_psychological_filters(self, action_sequence: list) -> list:
        """Apply filters based on the psychological state

        IMPORTANT: Respects Logos's full decision - does not truncate sequences.
        Psychology only influences the decision-making in the prompt, not the execution.
        """
        if not action_sequence:
            return action_sequence

        # RESPECT LOGOS'S DECISION: Do not truncate sequences
        # The psychological state influences the prompt and decision-making,
        # but once Logos decides on a sequence, we execute it fully

        print(
            f"🧠 Psychology influences decision-making, but respecting full sequence: {len(action_sequence)} actions"
        )

        # Only apply psychological modifications in extreme cases
        # If we are extremely frustrated, we might add one random action as exploration
        if (
            self.psychology.frustration > 0.9
            and len(action_sequence) == 1
            and random.random() < 0.2
        ):
            random_actions = ["up", "down", "left", "right", "space"]
            additional_action = random.choice(random_actions)
            print(
                f"🤯 Extreme frustration: adding random exploration action '{additional_action}'"
            )
            action_sequence.append(additional_action)

        return action_sequence

    def _build_enhanced_logos_prompt(
        self,
        aisthesis_analysis: str,
        sophia_reasoning: str,
        relevant_exp: str = "",
        failure_warnings: str = "",
        last_expected_outcome: str = None,
        aisthesis_data: AisthesisStructuredData = None,
        sophia_data: SophiaStructuredData = None,
    ) -> str:
        """Build enhanced prompt with psychological modifiers."""
        logos_content = ""
        try:
            with open(
                "agents/tomas_engine/nucleus/logos.md", "r", encoding="utf-8"
            ) as f:
                logos_content = f.read()

        except FileNotFoundError:
            print("⚠️ Warning: logos.md file not found")
            logos_content = "Logos module for action selection"

        except Exception as e:
            print(f"⚠️ Error reading logos.md: {e}")
            logos_content = "Logos module for action selection"

        # Add psychological modifiers
        psychological_modifier = self.psychology.get_psychological_prompt_modifier()

        memory_section = ""
        if relevant_exp or failure_warnings:
            memory_section = f"""

**Shared Memory:**
{relevant_exp}
{failure_warnings}
"""

        prediction_analysis_section = ""
        if last_expected_outcome:
            prediction_analysis_section = f"""

**Previous Action Analysis:**
Your last expected_outcome: "{last_expected_outcome}"
Actual AISTHESIS result: "{aisthesis_analysis[:200]}..."

Compare these to determine your prediction accuracy and calculate confidence_adjustment:
- Perfect Match: +0.2 confidence boost
- Partial Match: +0.1 confidence boost  
- No Match: 0 adjustment
- Wrong Prediction: -0.1 confidence penalty
"""

        psychological_section = f"""

**Your current mental state:**
State: {self.psychology.current_state}
{psychological_modifier}

##Psychological levels:
- Frustration: {self.psychology.frustration:.2f}/1.0
- Confidence: {self.psychology.confidence:.2f}/1.0  
- Curiosity: {self.psychology.curiosity_level:.2f}/1.0
- Patience: {self.psychology.patience:.2f}/1.0

## Recent history:
- Successful actions: {self.psychology.successful_actions}
- Consecutive failures: {self.psychology.consecutive_failures}
- Turns without progress: {self.psychology.consecutive_no_progress}
"""

        # Build structured data sections
        aisthesis_structured_section = ""
        if aisthesis_data:
            clickable_coords = ", ".join(
                [f"[{x}, {y}]" for x, y in aisthesis_data.clickable_coordinates[:10]]
            )
            aisthesis_structured_section = f"""

**AISTHESIS Structured Data:**
- Transformation Type: {aisthesis_data.transformation_type}
- Progress Detected: {aisthesis_data.progress_detected}
- Objects Changed: {len(aisthesis_data.changed_objects)}
- Objects Unchanged: {len(aisthesis_data.unchanged_objects)}
- Clickable Coordinates (first 10): {clickable_coords}
- Level Transition: {aisthesis_data.is_level_transition}
"""

        sophia_structured_section = ""
        if sophia_data:
            reliable_actions = ", ".join(sophia_data.most_reliable_actions[:5])
            high_confidence_rules = [
                rule.description
                for rule in sophia_data.confirmed_rules
                if rule.confidence > 0.8
            ][:3]
            rules_summary = (
                " | ".join(high_confidence_rules)
                if high_confidence_rules
                else "No high-confidence rules yet"
            )
            sophia_structured_section = f"""

**SOPHIA Structured Data:**
- Most Reliable Actions: {reliable_actions}
- High Confidence Rules: {rules_summary}
- Game Objective Confidence: {sophia_data.game_objective_confidence:.2f}
- Total Confirmed Rules: {len(sophia_data.confirmed_rules)}
- Active Hypotheses: {len(sophia_data.active_hypotheses)}
- Recommended Tests: {', '.join(sophia_data.recommended_tests[:3])}
"""

        prompt = f"""
{logos_content}
{prediction_analysis_section}

{psychological_section}

**Aisthesis Analysis:**
{aisthesis_analysis}

**Sophia Reasoning:**
{sophia_reasoning}
{aisthesis_structured_section}
{sophia_structured_section}
{memory_section}
"""
        return prompt

    def _parse_action_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the action decision from response."""
        action_data = extract_action_from_response(response_text)

        if action_data and action_data.get("action_sequence"):
            valid_actions = ["up", "down", "left", "right", "space", "click"]
            action_sequence = action_data["action_sequence"]

            if isinstance(action_sequence, list) and len(action_sequence) <= 5:
                valid_sequence = True
                for action in action_sequence:
                    if isinstance(action, str):
                        if action not in valid_actions:
                            valid_sequence = False
                            break
                    elif isinstance(action, dict):
                        action_name = action.get("action", "")
                        if action_name not in valid_actions:
                            valid_sequence = False
                            break
                        coordinates = action.get("coordinates", [])
                        if not isinstance(coordinates, list) or len(coordinates) != 2:
                            valid_sequence = False
                            break
                    else:
                        valid_sequence = False
                        break

                if valid_sequence and len(action_sequence) > 0:
                    return action_data
                else:
                    print(f"⚠️ Invalid action sequence '{action_sequence}'")
            else:
                print(f"⚠️ Invalid action sequence format '{action_sequence}'")

        # Fallback
        print("⚠️ Fallback: No valid action found, trying text extraction...")
        action_data = self._extract_action_from_text(response_text)

        if not action_data:
            print("⚠️ Ultimate fallback: Creating safe default")
            action_data = {
                "action_sequence": ["up"],
                "reasoning": "Fallback due to parsing failure",
                "expected_outcome": "Safe exploration move",
                "confidence": 0.3,
                "experimental": True,
            }

        return action_data

    def _extract_action_from_text(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract action from plain text if JSON parsing fails."""
        import re

        actions = ["up", "down", "left", "right", "space", "click"]
        print(f"🔍 Searching for actions in text: {response_text[:200]}...")

        for action in actions:
            if re.search(rf"\b{action}\b", response_text, re.IGNORECASE):
                print(f"🔍 Found '{action}' in text extraction")
                return {
                    "action_sequence": [action],
                    "reasoning": "Extracted from text response",
                    "expected_outcome": "Based on text analysis",
                    "confidence": 0.5,
                    "experimental": False,
                }

        return None

    def _get_fallback_coordinates(
        self, aisthesis_data: AisthesisStructuredData = None
    ) -> tuple[int, int]:
        """Get fallback coordinates using AISTHESIS clickable coordinates when available"""
        if aisthesis_data and aisthesis_data.clickable_coordinates:
            # Use a random coordinate from AISTHESIS's clickable list
            coord = random.choice(aisthesis_data.clickable_coordinates)
            print(f"🎯 Using AISTHESIS clickable coordinate: ({coord[0]}, {coord[1]})")
            return coord[0], coord[1]
        else:
            # Fallback to random coordinates
            x_coord = random.randint(0, 63)
            y_coord = random.randint(0, 63)
            print(f"🎯 Using random fallback coordinate: ({x_coord}, {y_coord})")
            return x_coord, y_coord
