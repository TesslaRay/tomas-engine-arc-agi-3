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
        self, frames: list[FrameData], latest_frame: FrameData, executed_actions: List[str] = None
    ) -> str:
        """Analyze the effect of an action sequence by comparing before and after states."""
        print(f"🏞️ AISTHESIS is analyzing action effect...")

        # Get current state (after all actions)
        current_state = latest_frame.frame

        # Determine how many frames back to compare based on executed actions
        if executed_actions and len(executed_actions) > 1:
            # Multiple actions executed, compare with state before the sequence
            frames_back = len(executed_actions) + 1  # +1 because frames[-1] is latest, frames[-2] is previous
            if len(frames) >= frames_back:
                previous_state = frames[-frames_back].frame
                action_description = f"sequence of {len(executed_actions)} actions: {', '.join(executed_actions)}"
                print(f"🔄 Comparing current state with {frames_back-1} frames ago (before {len(executed_actions)}-action sequence)")
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
            print(f"🎉 Level transition detected! Score: {previous_score} → {current_score}")
            
            # Extract the new level state (handle both 2D and 3D matrices)
            if isinstance(current_state[0][0], list):
                # 3D matrix - use the last layer (new level)
                new_level_state = current_state[-1]
            else:
                # 2D matrix - use as is
                new_level_state = current_state
            
            # Generate image for new level
            image_after = grid_to_image(current_state)
            
            print(f"\n🖼️ NEW LEVEL:")
            display_image_in_iterm2(image_after)
            
            # For level transitions, report the new level state without comparison
            return f"🎉 LEVEL UP! Score increased from {previous_score} to {current_score}.\n\nStarted new level:\n- Grid size: {len(new_level_state)}x{len(new_level_state[0])}\n- Ready for new challenges!"
        
        else:
            # Normal single-level frame - do comparison as usual
            # Handle single layer extraction
            if isinstance(current_state[0][0], list):
                current_state_2d = current_state[0]
            else:
                current_state_2d = current_state

            if isinstance(previous_state[0][0], list):
                previous_state_2d = previous_state[0]
            else:
                previous_state_2d = previous_state

            action_name = action_description

            # Generate images for comparison
            image_before = grid_to_image(previous_state)
            image_after = grid_to_image(current_state)

            print(f"\n🖼️ BEFORE: {action_name}")
            display_image_in_iterm2(image_before)

            print(f"\n🖼️ AFTER: {action_name}")
            display_image_in_iterm2(image_after)

            # Analyze pixel-level changes (use 2D matrices for comparison)
            change_analysis = analyze_pixel_changes(previous_state_2d, current_state_2d)

            # Build clean summary for prompt
            clean_summary = self._build_clean_summary(change_analysis)
            prompt = self._build_aisthesis_prompt(action_name, clean_summary, executed_actions)

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

    def _build_aisthesis_prompt(self, action_name: str, clean_summary: str, executed_actions: List[str] = None) -> str:
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

        # Add sequence information if multiple actions
        sequence_info = ""
        if executed_actions and len(executed_actions) > 1:
            sequence_info = f"""
Action sequence executed: {' → '.join(executed_actions)}
(Comparing state before the entire sequence with state after all actions completed)
"""
        else:
            sequence_info = f"""
Action executed: {action_name}
"""

        prompt = f"""
{aisthesis_content}

{sequence_info}

{clean_summary}

"""
        return prompt
