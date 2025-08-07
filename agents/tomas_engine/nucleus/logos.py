import random
import time
from typing import Dict, Any, Optional

from ...structs import FrameData, GameAction

# services
# from agents.services.cerebras_service import CerebrasService
# from agents.services.openai_service import OpenAIService
from agents.services.gemini_service import GeminiService

# constants
from agents.tomas_engine.constants import get_action_name, string_to_game_action

# parser
from agents.tomas_engine.response_parser import extract_action_from_response


class NucleiLogos:
    """Nuclei Logos"""

    def __init__(self, game_id: str):
        seed = int(time.time() * 1000000) + hash(game_id) % 1000000
        random.seed(seed)

        # self.cerebras_service = CerebrasService()
        # self.openai_service = OpenAIService()
        self.gemini_service = GeminiService()

    def process(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
        aisthesis_analysis: str,
        sophia_reasoning: str,
    ) -> list[GameAction]:
        """Process input string and return a list of GameActions."""
        print(f"🗺️ LOGOS is choosing action sequence...")

        # return [random.choice([a for a in GameAction if a is not GameAction.RESET])]

        is_first_action_turn = len(frames) == 2

        if is_first_action_turn:
            action = random.choice([a for a in GameAction if a is not GameAction.RESET])

            if action.is_simple():
                action.reasoning = f"RNG told me to pick {action.value}"

            elif action.is_complex():
                action.set_data(
                    {
                        "x": random.randint(0, 63),
                        "y": random.randint(0, 63),
                    }
                )

            action_sequence = [action]

        else:
            prompt = self._build_logos_prompt(aisthesis_analysis, sophia_reasoning)

            # print(f"\n📝 LOGOS PROMPT:")
            # print("=" * 50)
            # print(prompt)
            # print("=" * 50)

            logos_response = self.gemini_service.generate_text_sync(
                prompt=prompt,
                game_id=latest_frame.game_id,
            )

            print(f"\n🤖 LOGOS RESPONSE:")
            print(logos_response.content)

            # Parse the action sequence from response
            action_data = self._parse_action_response(logos_response.content)

            action_sequence_strings = action_data.get("action_sequence", [])

            # Convert string actions to GameActions
            action_sequence = []
            for i, action_item in enumerate(action_sequence_strings):
                # Handle both string actions and dict actions with coordinates
                if isinstance(action_item, dict):
                    # Action with coordinates format: {"action": "click", "coordinates": [x, y]}
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
                    # Simple string action format: "up", "down", etc.
                    action_string = action_item
                    x_coord = random.randint(0, 63)
                    y_coord = random.randint(0, 63)

                action = string_to_game_action(action_string)
                if action:
                    # Use specific reasoning for each action if available, otherwise use general reasoning
                    if isinstance(action_item, dict) and "reasoning" in action_item:
                        action.reasoning = action_item["reasoning"]
                    else:
                        action.reasoning = action_data.get(
                            "reasoning", "AI-generated reasoning"
                        )

                    # Set coordinates for complex actions (like click)
                    if action.is_complex():
                        action.set_data(
                            {
                                "x": x_coord,
                                "y": y_coord,
                            }
                        )
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

        # Print the sequence
        sequence_names = [get_action_name(action.value) for action in action_sequence]
        print(f"🤖 LOGOS chose sequence: {sequence_names}")
        return action_sequence

    def _build_logos_prompt(
        self, aisthesis_analysis: str, sophia_reasoning: str
    ) -> str:
        """Build the prompt for the Logos module."""
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

        prompt = f"""
{logos_content}

**Aisthesis Analysis:**
{aisthesis_analysis}

**Sophia Reasoning:**
{sophia_reasoning}

"""
        return prompt

    def _parse_action_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the action decision from Cerebras response. Trust Cerebras - minimal validation."""

        # Extract JSON from response
        action_data = extract_action_from_response(response_text)

        # If we got valid JSON with action_sequence, use it directly
        if action_data and action_data.get("action_sequence"):
            valid_actions = ["up", "down", "left", "right", "space", "click"]
            action_sequence = action_data["action_sequence"]

            # Validate all actions in sequence
            if isinstance(action_sequence, list) and len(action_sequence) <= 5:
                valid_sequence = True
                for action in action_sequence:
                    if isinstance(action, str):
                        # Simple string action
                        if action not in valid_actions:
                            valid_sequence = False
                            break
                    elif isinstance(action, dict):
                        # Complex action with coordinates
                        action_name = action.get("action", "")
                        if action_name not in valid_actions:
                            valid_sequence = False
                            break
                        # Validate coordinates format
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
                    print(
                        f"⚠️ Invalid action sequence '{action_sequence}', contains invalid actions or is empty"
                    )
            else:
                print(
                    f"⚠️ Invalid action sequence format '{action_sequence}', must be list of 1-5 actions"
                )

        # Only fallback if something is really wrong
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

        # Look for action mentions in standard order
        actions = ["up", "down", "left", "right", "space", "click"]

        print(f"🔍 Searching for actions in text: {response_text[:200]}...")

        for action in actions:
            # Use word boundary to avoid partial matches in compound words
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
