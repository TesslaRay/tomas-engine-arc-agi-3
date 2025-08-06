from agents.structs import FrameData

# utils
from agents.image_utils import grid_to_image, display_image_in_iterm2


class NucleiAisthesis:
    """Nuclei Aisthesis"""

    def __init__(self):
        pass

    def analyze_action_effect(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> str:
        """Analyze the effect of an action by comparing before and after states."""
        print(f"🏞️ AISTHESIS is analyzing action effect...")

        # Get current state (after action)
        current_state = latest_frame.frame

        # Get previous state (before action)

        previous_state = frames[-2].frame
        print(f"\n📸 BEFORE action:")
        display_image_in_iterm2(grid_to_image(previous_state))

        print(f"\n📸 AFTER action:")
        display_image_in_iterm2(grid_to_image(current_state))

        return "visual_analysis_completed"
