import random
import time
from typing import Any

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState

# utils
from ..image_utils import grid_to_image

# modules
from .spatial_perception_module import SpatialPerceptionModule


class VisionAgentRandom(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 2

    def __init__(self, *args: Any, llm_provider: str = "cerebras", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

        print(f"🤖 Starting Vision Agent Random with {llm_provider.upper()} provider")
        
        # Inicializar el módulo de percepción espacial con el proveedor seleccionado
        self.spatial_perception = SpatialPerceptionModule(provider=llm_provider)
        print(f"✅ Spatial Perception Module initialized with {llm_provider.upper()}")
        
        # Store minimal state for matrix comparison (not full history)
        # Initialize with dummy "closed eyes" matrix like Tomas for turn 0 analysis
        self.previous_matrix = self._create_dummy_closed_eyes_matrix()
        self.pending_action = 0  # Action 0 represents "opening eyes" for first turn
        self.pending_coordinates = None
        
        # Test sequence: left, up, up, up, up
        self.test_actions = [3, 1, 1, 1, 1]
        self.action_index = 0
        
        print(f"👁️ Matriz 'ojos cerrados' inicializada: 64x64 (todo en rosa - color 16)")
        print(f"🔄 Turno 0: Comparará el primer estado del juego vs 'ojos cerrados'")

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

    def _create_dummy_closed_eyes_matrix(self) -> list[list[int]]:
        """
        Crear matriz dummy que representa 'ojos cerrados' - todo en rosa (16)
        
        Esta matriz se usa como estado inicial "anterior" para que el análisis 
        espacial funcione desde el primer turno del juego, igual que en Tomas.
        
        Returns:
            Matriz 64x64 llena de 16s (color rosa/pink)
        """
        return [[16 for _ in range(64)] for _ in range(64)]
    
    def is_first_turn(self) -> bool:
        """
        Determinar si es el primer turno comparando si previous_matrix es la dummy
        
        Returns:
            True si es el primer turno (previous_matrix es toda rosa)
        """
        if not self.previous_matrix:
            return True
        
        # Verificar si toda la matriz es rosa (16)
        return all(all(cell == 16 for cell in row) for row in self.previous_matrix)
    
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
            # Use predefined test sequence instead of random
            if self.action_index < len(self.test_actions):
                action_number = self.test_actions[self.action_index]
                self.action_index += 1
                
                # Map numbers to GameAction
                action_map = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 
                             4: GameAction.ACTION4, 5: GameAction.ACTION5, 6: GameAction.ACTION6}
                action = action_map.get(action_number, GameAction.ACTION1)
                
                print(f"🎯 Test sequence: Action {action_number} ({self.action_index}/{len(self.test_actions)})")
            else:
                # Fall back to random if sequence is exhausted
                action = random.choice([a for a in GameAction if a is not GameAction.RESET])

        if action.is_simple():
            action.reasoning = f"RNG told me to pick {action.value}"
        elif action.is_complex():
            action.set_data({
                "x": 30,
                "y": 63,
            })
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "RNG said so!",
            }
        
        # Store current state for analysis after action execution
        if not latest_frame.is_empty():
            # Only update previous_matrix after we've done the analysis
            # This preserves the current matrix for comparison
            self.pending_action = action.value
            
            # Extract coordinates for complex actions
            self.pending_coordinates = None
            if action.is_complex() and hasattr(action, 'data'):
                self.pending_coordinates = (action.data.get('x'), action.data.get('y'))
        
        return action

    def append_frame(self, frame: FrameData) -> None:
        """Override para analizar efectos de acciones con percepción espacial"""
        super().append_frame(frame)
        
        # Analyze action effects if we have both previous and current matrices
        if (not frame.is_empty() and self.previous_matrix is not None and 
            self.pending_action is not None):
            
            # Determine if this is the first turn for special context
            is_first_turn = self.is_first_turn()
            first_turn_context = ""
            if is_first_turn:
                first_turn_context = " (PRIMER TURNO: 'ojos cerrados' → estado inicial del juego)"
            
            print(f"\n🎨 === SPATIAL PERCEPTION MODULE ===")
            print(f"🔍 Análisis de acción {self.pending_action}{first_turn_context}")
            
            # Execute complete analysis using the new stateless API
            analysis_result = self.spatial_perception.analyze_action_effect(
                matrix_before=self.previous_matrix,
                matrix_after=frame.frame,
                action=self.pending_action,
                coordinates=self.pending_coordinates,
                include_visual_interpretation=True
            )
            
            print(f"🤖 {analysis_result}")
            print("=" * 50)
            
            # Update previous_matrix for next comparison AFTER analysis
            self.previous_matrix = [row[:] for row in frame.frame]  # Deep copy
            self.pending_action = None
            self.pending_coordinates = None
            
        elif not frame.is_empty():
            print(f"\n🎨 === SPATIAL PERCEPTION MODULE ===")
            print("⚠️ No previous matrix available for comparison")
            print("=" * 50)
