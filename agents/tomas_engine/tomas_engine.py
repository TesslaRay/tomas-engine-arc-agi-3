from typing import Any

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState

# nucleus
from agents.tomas_engine.nucleus.aisthesis import NucleiAisthesis
from agents.tomas_engine.nucleus.sophia import NucleiSophia
from agents.tomas_engine.nucleus.logos import NucleiLogos


class TomasEngine(Agent):
    """Tomas Engine Agent"""

    MAX_ACTIONS = 30

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.aisthesis = NucleiAisthesis()
        self.sophia = NucleiSophia()
        self.logos = NucleiLogos(self.game_id)

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
            return GameAction.RESET

        # Detect if this is the first action turn
        is_first_action_turn = len(frames) == 2

        if is_first_action_turn:
            # First turn: only execute logos
            print("\n🎯 First action turn: executing LOGOS only")
            action = self.logos.process(
                frames=frames,
                latest_frame=latest_frame,
                aisthesis_analysis="",
                sophia_reasoning="",
            )
        else:
            # Subsequent turns: aisthesis -> sophia -> logos
            print("\n🔄 Executing aisthesis -> sophia -> logos")

            # Step 1: Aisthesis processes visual input
            aisthesis_analysis = self.aisthesis.analyze_action_effect(
                frames=frames,
                latest_frame=latest_frame,
            )

            # Step 2: Sophia processes the analysis into reasoning
            sophia_reasoning = self.sophia.process(aisthesis_analysis)

            # Step 3: Logos converts reasoning to action
            action = self.logos.process(
                frames=frames,
                latest_frame=latest_frame,
                aisthesis_analysis=aisthesis_analysis,
                sophia_reasoning=sophia_reasoning,
            )

        return action
