import random
import time

from ...structs import FrameData, GameAction


class NucleiLogos:
    """Nuclei Logos"""

    ACTION_NAMES = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "CLICK"}

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

        print(f"🤖 LOGOS chose {self.ACTION_NAMES[action.value]} ({action.value})")
        return action
