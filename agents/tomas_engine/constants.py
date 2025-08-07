"""
Constants for the ARC AGI Agents system.
"""

from agents.structs import GameAction

# Action names mapping for display purposes
ACTION_NAMES = {
    GameAction.ACTION1.value: "UP",
    GameAction.ACTION2.value: "DOWN",
    GameAction.ACTION3.value: "LEFT",
    GameAction.ACTION4.value: "RIGHT",
    GameAction.ACTION5.value: "SPACE",
    GameAction.ACTION6.value: "CLICK",
    GameAction.RESET.value: "RESET",
}

COLOR_NAMES = {
    0: "white",
    1: "blue",
    2: "gray",
    3: "dark-gray",
    4: "darker-gray",
    5: "black",
    6: "brown",
    7: "light-gray",
    8: "red",
    9: "ligth-blue",
    10: "green",
    11: "yellow",
    12: "orange",
    13: "magenta",
    14: "light-green",
    15: "purple",
    16: "pink",
}


def get_action_name(action_value: int) -> str:
    """
    Get the human-readable name for an action value.

    Args:
        action_value: The numeric action value
        lowercase: Whether to return lowercase version

    Returns:
        The human-readable action name
    """
    return ACTION_NAMES.get(action_value, f"action {action_value}")


def get_color_name(color_value: int) -> str:
    """
    Get the human-readable name for a color value.
    """
    return COLOR_NAMES.get(color_value, f"color-{color_value}")


def game_action_to_string(action: GameAction) -> str:
    """Convert GameAction to string representation."""
    action_mapping = {
        GameAction.ACTION1: "up",
        GameAction.ACTION2: "down",
        GameAction.ACTION3: "left",
        GameAction.ACTION4: "right",
        GameAction.ACTION5: "space",
        GameAction.ACTION6: "click",
    }
    return action_mapping.get(action, f"action_{action.value}")
