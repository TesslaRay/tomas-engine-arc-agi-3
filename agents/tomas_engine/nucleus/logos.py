import random
import time
from typing import Dict, Any, Optional

from ...structs import FrameData, GameAction

# services
from agents.services.cerebras_service import CerebrasService

# constants
from agents.tomas_engine.constants import get_action_name

# parser
from agents.tomas_engine.response_parser import extract_action_from_response


class NucleiLogos:
    """Nuclei Logos"""

    def __init__(self, game_id: str):
        seed = int(time.time() * 1000000) + hash(game_id) % 1000000
        random.seed(seed)

        self.cerebras_service = CerebrasService()

    def process(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
        aisthesis_analysis: str,
        sophia_reasoning: str,
    ) -> GameAction:
        """Process input string and return a GameAction."""
        print(f"🗺️ LOGOS is choosing an action...")

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

        else:
            prompt = self._build_logos_prompt(aisthesis_analysis, sophia_reasoning)

            # print(f"\n📝 LOGOS PROMPT:")
            # print("=" * 50)
            # print(prompt)
            # print("=" * 50)

            cerebras_response = self.cerebras_service.generate_text_sync(
                prompt=prompt,
            )

            print(f"\n🤖 LOGOS RESPONSE:")
            print(cerebras_response.content)

            # Parse the action from response - trust Cerebras
            action_data = self._parse_action_response(cerebras_response.content)

            selected_action = action_data["selected_action"]
            action = self._convert_action_string_to_game_action(selected_action)

            # Only fallback if conversion completely fails (should never happen)
            if not action:
                print(
                    f"⚠️ Conversion failed for '{selected_action}', using ACTION1 (up)"
                )
                action = GameAction.ACTION1

            action.reasoning = action_data.get("reasoning", "AI-generated reasoning")

        action_name = get_action_name(action.value)
        print(f"🤖 LOGOS chose {action_name} ({action.value})")
        return action

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

## CURRENT SITUATION

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

        # If we got valid JSON with selected_action, use it directly
        if action_data and action_data.get("selected_action"):
            valid_actions = ["up", "down", "left", "right", "space", "click"]
            selected = action_data["selected_action"]
            if selected in valid_actions:
                return action_data
            else:
                print(f"⚠️ Invalid action '{selected}', not in {valid_actions}")

        # Only fallback if something is really wrong
        print("⚠️ Fallback: No valid action found, trying text extraction...")
        action_data = self._extract_action_from_text(response_text)

        if not action_data:
            print("⚠️ Ultimate fallback: Creating safe default")
            action_data = {
                "selected_action": "up",
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
                    "selected_action": action,
                    "reasoning": "Extracted from text response",
                    "expected_outcome": "Based on text analysis",
                    "confidence": 0.5,
                    "experimental": False,
                }

        return None

    def _convert_action_string_to_game_action(
        self, action_string: str
    ) -> Optional[GameAction]:
        """Convert action string to GameAction enum."""
        action_mapping = {
            "up": GameAction.ACTION1,
            "down": GameAction.ACTION2,
            "left": GameAction.ACTION3,
            "right": GameAction.ACTION4,
            "space": GameAction.ACTION5,
            "click": GameAction.ACTION6,
        }

        return action_mapping.get(action_string.lower())
