import numpy as np
from typing import List

from agents.structs import FrameData

# utils
from agents.image_utils import grid_to_image, display_image_in_iterm2
from agents.tomas_engine.matrix_difference_utils import (
    analyze_pixel_changes,
)

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

        # Generate images
        image_before = grid_to_image(previous_state)
        image_after = grid_to_image(current_state)

        print(f"\n🖼️ BEFORE action: {action_name}")
        display_image_in_iterm2(image_before)

        print(f"\n�️ AFTER action: {action_name}")
        display_image_in_iterm2(image_after)

        # Analyze pixel-level changes
        change_analysis = analyze_pixel_changes(previous_state, current_state)

        if not change_analysis["has_changes"]:
            return (
                f"That action ({action_name}) generated no effect on the environment."
            )

        # Generate detailed change summary
        change_details = change_analysis["change_details"]
        if not change_details:
            detailed_changes = "🔍 SPECIFIC CHANGES: None detected"
        else:
            detailed_changes = (
                f"📍 COMPLETE LIST OF CHANGES ({len(change_details)} total):\n"
            )
            for i, change in enumerate(change_details, 1):
                pos = change["position"]
                detailed_changes += f"  {i}. ({pos[0]},{pos[1]}): {change['before']} → {change['after']}\n"

        print(f"\n🔍 CHANGE ANALYSIS:")
        print(f"Detected {change_analysis['total_changes']} pixel changes:")
        print(detailed_changes)
        
        # Show unchanged objects
        if "unchanged_objects" in change_analysis and change_analysis["unchanged_objects"]:
            unchanged_objects = change_analysis["unchanged_objects"]
            print(f"\n🔒 UNCHANGED OBJECTS ({len(unchanged_objects)} total):")
            for obj in unchanged_objects:
                center = obj.center
                bounds = obj.bounds
                print(f"  • {obj.id}: {obj.color} object with {obj.size} pixels at center ({center[0]},{center[1]}) bounds ({bounds[0]}-{bounds[1]}, {bounds[2]}-{bounds[3]})")
        
        # Show changed objects  
        if "changed_objects" in change_analysis and change_analysis["changed_objects"]:
            changed_objects = change_analysis["changed_objects"]
            print(f"\n🔄 CHANGED OBJECTS ({len(changed_objects)} total):")
            for obj in changed_objects:
                center = obj.center
                bounds = obj.bounds
                print(f"  • {obj.id}: {obj.color} object with {obj.size} pixels at center ({center[0]},{center[1]}) bounds ({bounds[0]}-{bounds[1]}, {bounds[2]}-{bounds[3]})")

        return f"Action '{action_name}' completed with {change_analysis['total_changes']} pixel changes detected."
