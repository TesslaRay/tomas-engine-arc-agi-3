import random
import time
from typing import Dict, Any, Optional

from ...structs import FrameData, GameAction

# memory
from .shared_memory import SharedMemory

# services
from agents.services.gemini_service import GeminiService

# constants
from agents.tomas_engine.constants import get_action_name, string_to_game_action

# parser
from agents.tomas_engine.utils.response_parser import extract_action_from_response


class HumanPsychologyEngine:
    """Simulates human psychology during the game"""

    def __init__(self):
        # Emotional/cognitive states
        self.curiosity_level = 0.9  # Decreases with time and failures
        self.confidence = 0.1  # Increases with successes
        self.frustration = 0.0  # Increases with useless actions
        self.patience = 1.0  # Decreases when there is no progress

        # Behavior counters
        self.consecutive_failures = 0
        self.consecutive_no_progress = 0
        self.total_turns = 0
        self.successful_actions = 0
        self.last_progress_turn = 0

        # Mental states
        self.current_state = "exploring"
        self.turns_in_current_state = 0

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

    def update_psychology(self, action_result: str, made_progress: bool):
        """Update the psychological state based on results"""
        self.total_turns += 1
        self.turns_in_current_state += 1

        # Update counters
        if made_progress:
            self.last_progress_turn = self.total_turns
            self.consecutive_no_progress = 0
            self.consecutive_failures = 0
            self.successful_actions += 1

            # Increase confidence and reduce frustration
            self.confidence = min(1.0, self.confidence + 0.15)
            self.frustration = max(0.0, self.frustration - 0.1)
            self.patience = min(1.0, self.patience + 0.05)

        else:
            self.consecutive_no_progress += 1

            # Determine if it was a total failure
            if (
                "no effect" in action_result.lower()
                or "nothing happened" in action_result.lower()
            ):
                self.consecutive_failures += 1
                self.frustration = min(
                    1.0, self.frustration + 0.2
                )  # High frustration by useless actions
            else:
                self.consecutive_failures = 0
                self.frustration = min(1.0, self.frustration + 0.05)  # Low frustration

            # Reduce confidence and patience
            self.confidence = max(0.0, self.confidence - 0.05)
            self.patience = max(0.0, self.patience - 0.1)

        # Reduce curiosity with time (more if there are failures)
        curiosity_decay = 0.02 if made_progress else 0.05
        self.curiosity_level = max(0.1, self.curiosity_level - curiosity_decay)

        # Transición de estados mentales
        self._transition_mental_state()

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


class NucleiLogos:
    """Enhanced Nuclei Logos with Human Psychology"""

    def __init__(self, game_id: str):
        seed = int(time.time() * 1000000) + hash(game_id) % 1000000
        random.seed(seed)

        self.gemini_service = GeminiService()
        self.psychology = HumanPsychologyEngine()

        # Tracking variables for psychology
        self.last_frame_data = None

    def process(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
        aisthesis_analysis: str,
        sophia_reasoning: str,
    ) -> list[GameAction]:
        """Process input string and return a list of GameActions."""
        print(f"🗺️ LOGOS is choosing action sequence...")

        # Update psychology based on the previous frame
        if self.last_frame_data and len(frames) > 2:
            progress_made = self._detect_progress(self.last_frame_data, latest_frame)
            action_result = (
                aisthesis_analysis  # Simplified - AISTHESIS tells what happened
            )
            self.psychology.update_psychology(action_result, progress_made)

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

            # Build prompt with psychological modifiers
            prompt = self._build_enhanced_logos_prompt(
                aisthesis_analysis, sophia_reasoning, relevant_exp, failure_warnings
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

            # Apply psychological filters to the sequence
            action_sequence_strings = self._apply_psychological_filters(
                action_sequence_strings
            )

            # Convert string actions to GameActions
            action_sequence = []
            for i, action_item in enumerate(action_sequence_strings):
                if isinstance(action_item, dict):
                    action_string = action_item.get("action", "")
                    coordinates = action_item.get("coordinates", [])
                    x_coord = (
                        coordinates[0]
                        if len(coordinates) > 0
                        else random.randint(0, 63)
                    )
                    y_coord = (
                        coordinates[1]
                        if len(coordinates) > 1
                        else random.randint(0, 63)
                    )
                else:
                    action_string = action_item
                    x_coord = random.randint(0, 63)
                    y_coord = random.randint(0, 63)

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
            f"🧠 State: {self.psychology.current_state}, Frustration: {self.psychology.frustration:.2f}, Confidence: {self.psychology.confidence:.2f}"
        )
        sequence_names = [get_action_name(action.value) for action in action_sequence]
        print(f"🤖 LOGOS chose sequence: {sequence_names}")
        return action_sequence

    def _detect_progress(self, old_frame: FrameData, new_frame: FrameData) -> bool:
        """Detect if progress was made by comparing frames"""
        # Simplified - you could make this more sophisticated
        # For now, we detect progress if the score changed or there are significant differences
        if hasattr(old_frame, "score") and hasattr(new_frame, "score"):
            return new_frame.score > old_frame.score

        # Other progress indicators (you can expand this)
        if hasattr(old_frame, "game_state") and hasattr(new_frame, "game_state"):
            return old_frame.game_state != new_frame.game_state

        return False  # Default: no progress detected

    def _apply_psychological_filters(self, action_sequence: list) -> list:
        """Apply filters based on the psychological state"""
        if not action_sequence:
            return action_sequence

        # Limit length based on psychological preferences
        preferred_length = self.psychology.get_sequence_length_preference()

        # In frustrated state, force 1 action sequences for quick changes
        if self.psychology.current_state == "frustrated":
            action_sequence = action_sequence[:1]
        else:
            action_sequence = action_sequence[:preferred_length]

        # If we are very frustrated, add random elements
        if self.psychology.frustration > 0.8 and len(action_sequence) == 1:
            # 30% chance to add a completely random action
            if random.random() < 0.3:
                random_actions = ["up", "down", "left", "right", "space"]
                action_sequence.append(random.choice(random_actions))

        return action_sequence

    def _build_enhanced_logos_prompt(
        self,
        aisthesis_analysis: str,
        sophia_reasoning: str,
        relevant_exp: str = "",
        failure_warnings: str = "",
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

        prompt = f"""
{logos_content}

{psychological_section}

**Aisthesis Analysis:**
{aisthesis_analysis}

**Sophia Reasoning:**
{sophia_reasoning}
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
