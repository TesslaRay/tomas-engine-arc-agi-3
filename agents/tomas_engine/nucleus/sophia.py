# memory
from .shared_memory import SharedMemory


class NucleiSophia:
    """Nuclei Sophia"""

    def process(self, input_string: str) -> str:
        """Process input string and return output string."""
        print(f"🧠 SOPHIA is processing...")

        # Consult shared memory for game rules context
        # memory_context = SharedMemory.get_instance().get_relevant_experience(
        #     "game rules"
        # )

        # if memory_context:
        #     print(f"📚 Memory context: {memory_context}")

        # GAME LS20
        rules = """
        Here is SOPHIA's reasoning. I know all the game rules with 100% confidence.

        The rules are:

        The objective to win is to complete all 8 levels.
        The goal of each level is to bring the blue piece with orange to the exit, but to win, the key must have the same shape and color as the exit.

        You are playing a maze game with a key.
        The player already has the key with them.
        You move the blue piece with the orange rectangle.
        At the start of each level you have 3 lives, which are the red squares in the top right.
        Solo te puedes mover en las areas de color gris mas oscuro.
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

        # GAME VC33
        # rules = """
        #         Here is SOPHIA's reasoning. I know all the game rules with 100% confidence.

        # The rules are:
        # The objective to win is to complete all 9 levels.
        # La meta de cada nivel es alinear la caja amarilla de 8x8 sobre el agua blanca, con la caja amarilla de 4x4 dentro de la barra separadora.

        # ONLY valid actions are the clicks on the red and blue buttons.

        # El boton rojo hace que suba el nivel del agua un nivel en el lado derecho y baje un nivel en el lado izquierdo.

        # El boton azul hace que suba el nivel del agua un nivel en el lado izquierdo y baje un nivel en el lado derecho.

        # Tienes 64 intentos para completar el nivel.

        # Los intentos son los cuadrados verdes en la parte superior.

        # Los niveles se identifican por el pixel amarillo de 1x1 en la parte superior a la derecha de los pixeles verdes.

        # # Rules for level 2:

        # Ahora el cuadrado verde de 8x8 sobre el agua blanca tiene que estar alineado con el cuadrado verde de 4x4 sobre la barra separadora.

        # # Rules for level 3:

        # Nuevamente tienes que alinear el cuadrado verde de 8x8 sobre el agua blanca con el cuadrado verde de 4x4 sobre la barra separadora.

        # Tienes 2 barras separadoras, por lo que tienes que mover agua de un lado a otro para alinear los cuadrados verdes.

        # # Rules for level 4:

        # Ahora tienes que alinear el cuadrado verde de 8x8 sobre el agua blanca con el cuadrado verde de 4x4 sobre la barra separadora y al mismo tiempo alinear el cuadrado amarillo de 4x4 sobre la barra separadora con el cuadrado amarillo de 8x8 sobre el agua blanca.

        # Tienes 2 barras separadoras, por lo que tienes que mover agua de un lado a otro para alinear los cuadrados verdes y amarillos.

        #         """

        # Recordar las reglas como experiencia exitosa
        # SharedMemory.get_instance().remember_success(
        #     "game rules reasoning", "provide_rules", "Rules successfully provided"
        # )

        return rules
