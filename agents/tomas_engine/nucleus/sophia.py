# Sophia: Processes visual input and generates reasoning strings
class NucleiSophia:
    """Nuclei Sophia"""

    def process(self, input_string: str) -> str:
        """Process input string and return output string."""
        print(f"🧠 SOPHIA is processing input: {input_string}")

        rules = """
        Here is SOPHIA's reasoning. I know all the game rules with 100% confidence.
The rules are:
The objective to win is to complete all 8 levels.
The objective of each level is to bring the blue piece with orange to the exit, but to win, the key must have the same shape and color as the exit.
You are playing a maze game with a key.
The player already has the key with them.
You move the blue piece with the orange rectangle.
At the start of each level you have 3 lives, which are the red squares in the top right.
You have 22 attempts to complete the level before losing a life.
The attempts are the purple squares at the top.
You can only move through the light gray areas. Dark gray is a wall.
Your useful movements are only action 1 (up), 2 (down), 3 (left) and 4 (right).
The key's shape can change form and color.
To change the key's shape you need to move over the figure with a light-blue and white square.
The key's shape must match the exit's shape to complete the level.
The key's shape is shown at the bottom left, with a blue square.
The exit is inside the maze and has a black background, with a blue square and the key shape needed to advance to the next level.
Remember, you must bring the blue piece with orange to the exit, but to win, the key must have the same shape and color as the exit.
Rules for level 2:
The 4x4 purple squares reset your attempts per level.
If you touch the square with white, light blue, red and orange, the key changes color.
        
        """

        return rules
