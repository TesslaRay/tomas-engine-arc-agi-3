import random
import time
from typing import Any
from PIL import Image

from .agent import Agent
from .structs import FrameData, GameAction, GameState


class Tomas(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 3

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

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

    def grid_to_image(self, grid: list[list[list[int]]]) -> Image.Image:
        """Converts a 3D grid of integers into a PIL image, stacking grid layers horizontally."""
        color_map = [
            (255, 255, 255),# 0: Negro
            (0, 0, 170),    # 1: Azul oscuro
            (0, 170, 0),    # 2: Verde oscuro
            (102, 102, 102),# 3: Gris oscuro (0x666666)
            (51, 51, 51),   # 4: Gris claro (0x333333)
            (0, 0, 0),      # 5: Negro
            (170, 85, 0),   # 6: Marrón
            (170, 170, 170),# 7: Gris claro
            (226, 77, 62),  # 8: Rojo medio
            (73, 145, 247), # 9: Azul claro (0x4991F7)
            (85, 255, 85),  # 10: Verde claro
            (85, 255, 255), # 11: Cian claro
            (232, 139, 59), # 12: Naranja (0xe88b3b)
            (255, 85, 255), # 13: Magenta claro
            (255, 255, 85), # 14: Amarillo
            (153, 90, 208), # 15: Morado
        ]

        if not grid or not grid[0]:
            # Create empty image if grid is empty
            return Image.new("RGB", (200, 200), color="black")

        height = len(grid[0])
        width = len(grid[0][0])
        num_layers = len(grid)

        # Add a small separator between grids if there are multiple layers
        separator_width = 5 if num_layers > 1 else 0
        total_width = (width * num_layers) + (separator_width * (num_layers - 1))

        image = Image.new("RGB", (total_width, height), "white")
        pixels = image.load()

        for i, grid_layer in enumerate(grid):
            # Check if grid_layer is valid
            if len(grid_layer) != height or len(grid_layer[0]) != width:
                continue

            offset_x = i * (width + separator_width)
            for y in range(height):
                for x in range(width):
                    color_index = grid_layer[y][x] % 16
                    pixels[x + offset_x, y] = color_map[color_index]

        return image

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
        map_image = self.grid_to_image(latest_frame.frame)
        
        # Guardar la imagen con información del estado
        filename = f"tomas_map_action_{self.action_counter:03d}_score_{latest_frame.score:03d}.png"
        map_image.save(filename)
        
        print(f"Imagen del mapa guardada como: {filename}")
        print(f"Dimensiones de la imagen: {map_image.size}")
        print("=" * 40)

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
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "RNG said so!",
            }
        return action
