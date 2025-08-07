from typing import Any

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState

# nucleus
from agents.tomas_engine.nucleus.aisthesis import NucleiAisthesis
from agents.tomas_engine.nucleus.sophia import NucleiSophia
from agents.tomas_engine.nucleus.logos import NucleiLogos

# constants
from agents.tomas_engine.constants import game_action_to_string


class TomasEngine(Agent):
    """Tomas Engine Agent"""

    MAX_ACTIONS = 10

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.aisthesis = NucleiAisthesis()
        self.sophia = NucleiSophia()
        self.logos = NucleiLogos(self.game_id)
        self.pending_actions = []  # Queue for multi-action sequences
        self.executed_sequence = []  # Track actions executed in current sequence

    @property
    def name(self) -> str:
        return f"{super().name}.{self.MAX_ACTIONS}"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Decide if the agent is done playing or not."""
        return any(
            [
                latest_frame.state is GameState.WIN,
                # uncomment to only let the agent play one time
                # latest_frame.state is GameState.GAME_OVER,
            ]
        )

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:

        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            # if game is not started (at init or after GAME_OVER) we need to reset
            # add a small delay before resetting after GAME_OVER to avoid timeout
            self.pending_actions = []  # Clear any pending actions on reset
            self.executed_sequence = []  # Clear executed sequence on reset
            return GameAction.RESET

        # If we have pending actions from a sequence, execute the next one
        if self.pending_actions:
            next_action = self.pending_actions.pop(0)

            # Convert GameAction to string for tracking
            action_string = game_action_to_string(next_action)
            self.executed_sequence.append(action_string)
            print(
                f"\n🔄 Executing next action in sequence: {next_action} (action #{len(self.executed_sequence)} of sequence)"
            )
            return next_action

        # No pending actions, need to get new sequence from LOGOS
        # Detect if this is the first action turn
        is_first_action_turn = len(frames) == 2

        if is_first_action_turn:
            # First turn: only execute logos
            print("\n🎯 First action turn: executing LOGOS only")

            self.executed_sequence = []

            action_sequence = self.logos.process(
                frames=frames,
                latest_frame=latest_frame,
                aisthesis_analysis="",
                sophia_reasoning="",
            )
        else:
            # Subsequent turns: aisthesis -> sophia -> logos
            print("\n🔄 Executing aisthesis -> sophia -> logos")

            # Step 1: Aisthesis processes visual input
            # Pass the executed sequence if we just finished a multi-action sequence
            executed_actions = (
                self.executed_sequence if self.executed_sequence else None
            )
            aisthesis_analysis = self.aisthesis.analyze_action_effect(
                frames=frames,
                latest_frame=latest_frame,
                executed_actions=executed_actions,
            )

            # Step 2: Sophia processes the analysis into reasoning
            sophia_reasoning = self.sophia.process(aisthesis_analysis)

            # Step 3: Logos converts reasoning to action sequence
            action_sequence = self.logos.process(
                frames=frames,
                latest_frame=latest_frame,
                aisthesis_analysis=aisthesis_analysis,
                sophia_reasoning=sophia_reasoning,
            )

        # Extract first action and queue the rest
        if action_sequence:
            current_action = action_sequence[0]
            self.pending_actions = action_sequence[1:]  # Queue remaining actions

            # Reset executed sequence and start tracking new sequence
            self.executed_sequence = []
            action_string = game_action_to_string(current_action)
            self.executed_sequence.append(action_string)

            print(
                f"\n🎯 Executing first action: {current_action}, {len(self.pending_actions)} remaining in queue"
            )
            return current_action

        else:
            # Just execute bar
            print("⚠️ No actions received from LOGOS")
            return GameAction.ACTION5
