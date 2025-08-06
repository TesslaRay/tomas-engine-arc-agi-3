import random
import time

from ...structs import FrameData, GameAction

# constants
from agents.tomas_engine.constants import get_action_name


class NucleiLogos:
    """Nuclei Logos"""

    def __init__(self, game_id: str):
        seed = int(time.time() * 1000000) + hash(game_id) % 1000000
        random.seed(seed)

    def process(
        self, input_string: str, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Process input string and return a GameAction."""
        print(f"🗺️ LOGOS is choosing an action...")

        # For now, return a random action
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

        action_name = get_action_name(action.value)
        print(f"🤖 LOGOS chose {action_name} ({action.value})")
        return action
