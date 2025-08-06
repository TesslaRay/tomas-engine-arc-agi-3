import numpy as np

from agents.structs import FrameData

# utils
from agents.image_utils import grid_to_image, display_image_in_iterm2
from agents.tomas_engine.utils.matrix_utils import calculate_matrix_difference

# constants
from agents.tomas_engine.constants import get_action_name


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

        action_name = get_action_name(latest_frame.action_input.id.value)
        print(f"\n📸 BEFORE action: {action_name}")
        display_image_in_iterm2(grid_to_image(previous_state))

        print(f"\n📸 AFTER action: {action_name}")
        display_image_in_iterm2(grid_to_image(current_state))

        difference_matrix = calculate_matrix_difference(previous_state, current_state)

        if not np.any(difference_matrix != 0):
            return (
                f"That action ({action_name}) generated no effect on the environment."
            )

        return "visual_analysis_completed"
