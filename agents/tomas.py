import json
import os
import random
import re
import time
from typing import Any, Dict, Optional

from .agent import Agent
from .structs import FrameData, GameAction, GameState
from .image_utils import grid_to_image
from .services.gemini_service import GeminiService


class Tomas(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 5

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)
        
        # Inicializar el servicio de Gemini
        try:
            self.gemini_service = GeminiService()
            print("✅ Servicio Gemini inicializado correctamente")
        except Exception as e:
            print(f"⚠️ Error al inicializar Gemini: {e}")
            self.gemini_service = None
        
        # Cargar el contenido del archivo TOMAS.md
        self.tomas_prompt = self._load_tomas_prompt()

    def _load_tomas_prompt(self) -> str:
        """Cargar el contenido del archivo TOMAS.md"""
        try:
            # Obtener la ruta del archivo TOMAS.md
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tomas_md_path = os.path.join(current_dir, "TOMAS.md")
            
            with open(tomas_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"✅ Archivo TOMAS.md cargado correctamente")
            return content
            
        except Exception as e:
            print(f"⚠️ Error al cargar TOMAS.md: {e}")
            return "# Tomas agente resolvedor de juegos mediante la intuicion\n\nEres Tomas un agente encargado de descubrir como funciona un juego."

    def llmJsonExtractor(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """
        Extrae el JSON de la respuesta del LLM
        
        Args:
            llm_response: Respuesta completa del LLM
            
        Returns:
            Diccionario con el JSON extraído o None si no se encuentra
        """
        try:
            # Buscar JSON en la respuesta usando regex
            json_pattern = r'\{.*?\}'
            matches = re.findall(json_pattern, llm_response, re.DOTALL)
            
            if not matches:
                print("❌ No se encontró JSON en la respuesta")
                return None
            
            # Tomar el primer match que sea JSON válido
            for match in matches:
                try:
                    parsed_json = json.loads(match)
                    
                    # Validar que tenga los campos requeridos
                    required_fields = ["goal_reasoning", "pattern_analysis", "hypothesis", "exploration_strategy", "action"]
                    if all(field in parsed_json for field in required_fields):
                        print("✅ JSON válido extraído correctamente")
                        return parsed_json
                    else:
                        print(f"⚠️ JSON no tiene todos los campos requeridos: {list(parsed_json.keys())}")
                        
                except json.JSONDecodeError:
                    continue
            
            print("❌ No se encontró JSON válido con la estructura requerida")
            return None
            
        except Exception as e:
            print(f"❌ Error al extraer JSON: {e}")
            return None

    def _map_action_number_to_game_action(self, action_number: int) -> GameAction:
        """
        Mapear número de acción del JSON a GameAction
        
        Args:
            action_number: Número de acción (1-6)
            
        Returns:
            GameAction correspondiente
        """
        action_map = {
            1: GameAction.ACTION1,  # Arriba
            2: GameAction.ACTION2,  # Abajo
            3: GameAction.ACTION3,  # Izquierda
            4: GameAction.ACTION4,  # Derecha
            5: GameAction.ACTION5,  # Barra espaciadora
            6: GameAction.ACTION6,  # Click del mouse
        }
        
        return action_map.get(action_number, GameAction.ACTION1)  # Default a ACTION1 si no se encuentra

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
        filename = f"images/tomas_map_action_{self.action_counter:03d}_score_{latest_frame.score:03d}.png"
        map_image.save(filename)
        
        print(f"Imagen del mapa guardada como: {filename}")
        print(f"Dimensiones de la imagen: {map_image.size}")
        print("=" * 40)
        
        return map_image

    def ask_gemini_analysis(self, latest_frame: FrameData) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Consultar a Gemini para análisis del estado actual usando el prompt de TOMAS.md
        
        Returns:
            Tupla con (respuesta_completa, json_extraido)
        """
        if not self.gemini_service or latest_frame.is_empty():
            return "Análisis no disponible", None
        
        try:
            # Generar imagen del mapa actual
            map_image = grid_to_image(latest_frame.frame)
            
            # Usar el contenido literal del archivo TOMAS.md como prompt base
            prompt = f"""{self.tomas_prompt}

ESTADO ACTUAL DEL JUEGO:
- Estado del juego: {latest_frame.state}
- Puntuación: {latest_frame.score}
- Acción número: {self.action_counter}

Analiza la imagen del mapa actual y proporciona tu análisis como Tomas.
"""
            
            # Llamar a Gemini
            response = self.gemini_service.generate_with_image_sync(
                prompt=prompt,
                image=map_image,
                system_prompt="Eres un experto analizando juegos de puzzle y estrategia."
            )
            
            print(f"\n🤖 === ANÁLISIS DE GEMINI ===")
            print(f"Tiempo de respuesta: {response.duration_ms}ms")
            print(f"Tokens usados: {response.usage['total_tokens']}")
            print(f"Análisis: {response.content}")
            print("=" * 40)
            
            # Extraer JSON de la respuesta
            extracted_json = self.llmJsonExtractor(response.content)
            
            return response.content, extracted_json
            
        except Exception as e:
            print(f"❌ Error al consultar Gemini: {e}")
            return f"Error en análisis: {str(e)}", None

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
            action.reasoning = "Reseteando juego por estado inicial o game over"
            print(f"\n🔄 ACCIÓN: RESET (automática)")
            return action
        
        # Consultar a Gemini para obtener análisis y acción sugerida
        gemini_response, extracted_json = self.ask_gemini_analysis(latest_frame)
        
        # Intentar usar la acción sugerida por Gemini
        if extracted_json and isinstance(extracted_json.get("action"), int):
            suggested_action_number = extracted_json["action"]
            
            # Mapear a GameAction
            action = self._map_action_number_to_game_action(suggested_action_number)
            
            # Configurar reasoning con toda la información de Gemini
            action.reasoning = {
                "goal_reasoning": extracted_json.get("goal_reasoning", ""),
                "pattern_analysis": extracted_json.get("pattern_analysis", ""),
                "hypothesis": extracted_json.get("hypothesis", ""),
                "exploration_strategy": extracted_json.get("exploration_strategy", ""),
                "suggested_action": suggested_action_number,
                "chosen_action": action.value,
                "gemini_response": gemini_response[:200] + "..." if len(gemini_response) > 200 else gemini_response
            }
            
            print(f"\n🤖 ACCIÓN SUGERIDA POR GEMINI: {suggested_action_number} -> {action.value}")
            print(f"📋 Razonamiento: {extracted_json.get('goal_reasoning', '')[:100]}...")
            
        else:
            # Fallback a acción aleatoria si no se puede extraer JSON válido
            print("⚠️ No se pudo extraer acción válida de Gemini, usando acción aleatoria")
            action = random.choice([a for a in GameAction if a is not GameAction.RESET])
            action.reasoning = {
                "fallback_reason": "Error al extraer JSON de Gemini",
                "random_choice": f"Acción aleatoria: {action.value}",
                "gemini_response": gemini_response[:200] + "..." if len(gemini_response) > 200 else gemini_response
            }
            print(f"\n🎲 ACCIÓN FALLBACK: {action.value} (aleatoria)")
        
        if action.is_complex():
            action.set_data(
                {
                    "x": random.randint(0, 63),
                    "y": random.randint(0, 63),
                }
            )
        
        print(f"\n✅ DECISIÓN FINAL: {action.value}")
        return action
