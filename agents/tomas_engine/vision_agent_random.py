import random
import time
from typing import Any

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState
from ..image_utils import grid_to_image
from .spatial_perception_module import SpatialPerceptionModule


class VisionAgentRandom(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 3

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)
        
        # Inicializar el módulo de percepción espacial
        self.spatial_perception = SpatialPerceptionModule()
        print("✅ Módulo de percepción espacial inicializado")

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

    def show_current_map(self, latest_frame: FrameData) -> None:
        """Display the current map state as an image and save it."""
        print(f"\n=== ESTADO ACTUAL DEL MAPA ===")
        print(f"Estado del juego: {latest_frame.state}")
        print(f"Puntuación: {latest_frame.score}")
        print(f"Acción número: {self.action_counter}")
        
        if latest_frame.is_empty():
            print("Mapa vacío - no hay datos para mostrar")
            return
        
        # Convertir el mapa a imagen
        map_image = grid_to_image(latest_frame.frame)
        
        # Guardar la imagen con información del estado
        filename = f"images/vision_map_action_{self.action_counter:03d}_score_{latest_frame.score:03d}.png"
        map_image.save(filename)
        
        print(f"Imagen del mapa guardada como: {filename}")
        print(f"Dimensiones de la imagen: {map_image.size}")
        print("=" * 40)
        
        return map_image

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Choose which action the Agent should take, fill in any arguments, and return it."""
        
        # Mostrar el estado actual del mapa antes de tomar la decisión
        self.show_current_map(latest_frame)
        
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            # if game is not started (at init or after GAME_OVER) we need to reset
            # add a small delay before resetting after GAME_OVER to avoid timeout
            action = GameAction.RESET
        else:
            # else choose a random action that isnt reset
            # action = random.choice([a for a in GameAction if a is not GameAction.RESET])
            action = GameAction.ACTION6

        if action.is_simple():
            action.reasoning = f"RNG told me to pick {action.value}"
        elif action.is_complex():
            action.set_data(
                # {
                #     "x": 30,
                #     "y": 63,
                # }
                {
                    "x": 10,
                    "y": 32,
                }
            )
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "RNG said so!",
            }
        
        # Preparar análisis de percepción espacial ANTES de ejecutar la acción
        if not latest_frame.is_empty():
            coordinates = None
            if action.is_complex() and hasattr(action, 'data'):
                coordinates = (action.data.get('x'), action.data.get('y'))
            
            self.spatial_perception.prepare_action_analysis(
                matrix_before=latest_frame.frame,
                action=action.value,
                coordinates=coordinates
            )
        
        return action

    def append_frame(self, frame: FrameData) -> None:
        """Override para analizar efectos de acciones con percepción espacial"""
        super().append_frame(frame)
        
        # Analizar efectos de la acción usando el estado después de la acción
        if not frame.is_empty():
            # Ejecutar el análisis completo (necesario para generar la interpretación de Gemini)
            self.spatial_perception.analyze_action_effect(
                matrix_after=frame.frame
            )
            
            # Obtener solo la interpretación visual de Gemini
            gemini_interpretation = self.spatial_perception.get_gemini_interpretation_only()
            
            print(f"\n🎨 === SPATIAL PERCEPTION MODULE ===")
            if gemini_interpretation:
                print(f"🤖 {gemini_interpretation}")
            else:
                print("⚠️ There is no visual interpretation available")
            print("=" * 45)
