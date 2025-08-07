import numpy as np
from typing import List

from agents.structs import FrameData

# services
from agents.services.gemini_service import GeminiService

# utils
from agents.image_utils import grid_to_image, display_image_in_iterm2
from agents.tomas_engine.matrix_difference_utils import analyze_pixel_changes

# constants
from agents.tomas_engine.constants import get_action_name


class NucleiAisthesis:
    """Nuclei Aisthesis"""

    def __init__(self):
        self.gemini_service = GeminiService()

    def analyze_action_effect(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> str:
        """Analyze the effect of an action by comparing before and after states."""
        print(f"🏞️ AISTHESIS is analyzing action effect...")

        # Get current state (after action)
        current_state = latest_frame.frame

        # Get previous state (before action)
        previous_state = frames[-2].frame

        action_name = get_action_name(latest_frame.action_input.id.value)

        # Generate images
        image_before = grid_to_image(previous_state)
        image_after = grid_to_image(current_state)

        print(f"\n🖼️ BEFORE action: {action_name}")
        display_image_in_iterm2(image_before)

        print(f"\n🖼️ AFTER action: {action_name}")
        display_image_in_iterm2(image_after)

        # Analyze pixel-level changes
        change_analysis = analyze_pixel_changes(previous_state, current_state)

        # Build clean summary for prompt
        clean_summary = self._build_clean_summary(change_analysis)
        prompt = self._build_aisthesis_prompt(action_name, clean_summary)

        if not change_analysis["has_changes"]:
            return f"That action ({action_name}) generated no effect on the environment.\n {clean_summary}"

        # print(f"\n🔍 AISTHESIS PROMPT:")
        # print(prompt)

        # Send prompt to Gemini
        gemini_response = self.gemini_service.generate_with_images_sync(
            prompt, images=[image_before, image_after]
        )

        print(f"\n🔍 GEMINI RESPONSE:")
        print(gemini_response.content)

        return gemini_response.content

    def _build_clean_summary(self, change_analysis: dict) -> str:
        """Build a clean, concise summary for the prompt."""
        summary = ""
        summary += f"Total pixel changes: {change_analysis['total_changes']}\n"

        # Add change type summary
        if (
            "unchanged_objects" in change_analysis
            and change_analysis["unchanged_objects"]
        ):
            unchanged_objects = change_analysis["unchanged_objects"]
            summary += f"\nUnchanged objects: {len(unchanged_objects)} total\n"
            # Show ALL unchanged objects
            for obj in unchanged_objects:
                center = obj.center
                summary += f"- {obj.color} object ({obj.size}px) at ({center[0]},{center[1]})\n"

        if "changed_objects" in change_analysis and change_analysis["changed_objects"]:
            changed_objects = change_analysis["changed_objects"]
            summary += f"\nChanged objects: {len(changed_objects)} total\n"
            # Show ALL changed objects
            for obj in changed_objects:
                center = obj.center
                summary += f"- {obj.color} object ({obj.size}px) at ({center[0]},{center[1]})\n"

        # Add key changes summary
        if change_analysis.get("change_details"):
            change_details = change_analysis["change_details"]
            summary += f"\nKey changes\n"
            for i, change in enumerate(change_details, 1):
                pos = change["position"]
                summary += f"{i}. ({pos[0]},{pos[1]}): {change['before']} → {change['after']}\n"

        return summary

    def _build_aisthesis_prompt(self, action_name: str, clean_summary: str) -> str:
        """Build the prompt for the Aisthesis module."""
        aisthesis_content = ""
        try:
            with open(
                "agents/tomas_engine/nucleus/aisthesis.md", "r", encoding="utf-8"
            ) as f:
                aisthesis_content = f.read()
        except FileNotFoundError:
            print("⚠️ Warning: aisthesis.md file not found")
            aisthesis_content = "Aisthesis module for visual analysis"
        except Exception as e:
            print(f"⚠️ Error reading aisthesis.md: {e}")
            aisthesis_content = "Aisthesis module for visual analysis"

        prompt = f"""
{aisthesis_content}

Action executed: {action_name}

{clean_summary}

"""
        return prompt
