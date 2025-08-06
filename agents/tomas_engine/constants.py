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

# Action names in lowercase for consistency in some modules
ACTION_NAMES_LOWER = {
    GameAction.ACTION1.value: "up",
    GameAction.ACTION2.value: "down",
    GameAction.ACTION3.value: "left",
    GameAction.ACTION4.value: "right",
    GameAction.ACTION5.value: "space",
    GameAction.ACTION6.value: "click",
    GameAction.RESET.value: "reset",
}


def get_action_name(action_value: int, lowercase: bool = False) -> str:
    """
    Get the human-readable name for an action value.

    Args:
        action_value: The numeric action value
        lowercase: Whether to return lowercase version

    Returns:
        The human-readable action name
    """
    mapping = ACTION_NAMES_LOWER if lowercase else ACTION_NAMES
    return mapping.get(action_value, f"action {action_value}")
