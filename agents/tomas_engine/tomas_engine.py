import json
import os
import random
import re
import time
import base64
from typing import Any, Dict, List, Optional

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState
from ..image_utils import grid_to_image
from ..services.gemini_service import GeminiService


class TomasEngine(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 20

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
        
        # Inicializar memoria episódica
        self.episodic_memory: List[Dict[str, Any]] = []
        self.max_memory_size = 10  # Mantener los últimos 10 movimientos
        
        # Almacenar las últimas 3 imágenes para análisis
        self.recent_images: List[Any] = []  # PIL Images
        self.max_images = 3

    def _load_tomas_prompt(self) -> str:
        """Cargar el contenido del archivo TOMAS.md"""
        try:
            # Obtener la ruta del archivo TOMAS.md
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tomas_md_path = os.path.join(current_dir, "tomas_engine.md")
            
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
                    
                    # Validar que tenga los campos requeridos según TOMAS.md
                    required_fields = ["current_phase", "phase_progress", "environment_observations", "action_effects", "current_hypothesis", "next_test", "action"]
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

    def add_to_episodic_memory(self, action: GameAction, frame_before: FrameData, frame_after: FrameData, gemini_analysis: Optional[Dict[str, Any]] = None) -> None:
        """
        Agregar un movimiento a la memoria episódica
        
        Args:
            action: Acción tomada
            frame_before: Estado del juego antes de la acción
            frame_after: Estado del juego después de la acción
            gemini_analysis: Análisis de Gemini para esta acción
        """
        memory_entry = {
            "action_number": self.action_counter,
            "action": action.value,
            "action_name": self._get_action_name(action.value),
            "score_before": frame_before.score,
            "score_after": frame_after.score,
            "score_change": frame_after.score - frame_before.score,
            "game_state_before": frame_before.state.value,
            "game_state_after": frame_after.state.value,
            "gemini_reasoning": gemini_analysis.get("current_hypothesis", "") if gemini_analysis else "",
            "timestamp": time.time()
        }
        
        # Agregar a la memoria
        self.episodic_memory.append(memory_entry)
        
        # Mantener solo los últimos N movimientos
        if len(self.episodic_memory) > self.max_memory_size:
            self.episodic_memory.pop(0)
        
        print(f"📝 Memoria actualizada: {len(self.episodic_memory)} entradas")

    def _get_action_name(self, action_value: int) -> str:
        """Convertir número de acción a nombre legible"""
        action_names = {
            0: "RESET",
            1: "Arriba",
            2: "Abajo", 
            3: "Izquierda",
            4: "Derecha",
            5: "Barra",
            6: "Click"
        }
        return action_names.get(action_value, f"Acción {action_value}")

    def get_memory_summary(self) -> str:
        """
        Generar un resumen de la memoria episódica para el prompt de Gemini
        
        Returns:
            String con resumen de movimientos recientes
        """
        if not self.episodic_memory:
            return "## Historial de Movimientos\nEste es el primer movimiento del juego."
        
        summary = "## Historial de Movimientos Recientes\n\n"
        
        for i, entry in enumerate(self.episodic_memory[-5:], 1):  # Últimos 5 movimientos
            score_indicator = ""
            if entry["score_change"] > 0:
                score_indicator = f" (+{entry['score_change']} puntos ✅)"
            elif entry["score_change"] < 0:
                score_indicator = f" ({entry['score_change']} puntos ❌)"
            else:
                score_indicator = " (sin cambio de puntuación)"
            
            summary += f"**Movimiento {entry['action_number']}:** {entry['action_name']}{score_indicator}\n"
            if entry["gemini_reasoning"]:
                summary += f"- Razonamiento: {entry['gemini_reasoning']}\n"
            summary += f"- Estado: {entry['game_state_before']} → {entry['game_state_after']}\n\n"
        
        # Agregar análisis de patrones
        if len(self.episodic_memory) >= 3:
            recent_scores = [entry["score_change"] for entry in self.episodic_memory[-3:]]
            if all(s >= 0 for s in recent_scores):
                summary += "🎯 **Patrón observado:** Los últimos movimientos han sido exitosos o neutrales.\n"
            elif all(s <= 0 for s in recent_scores):
                summary += "⚠️ **Patrón observado:** Los últimos movimientos no han mejorado la puntuación.\n"
        
        return summary

    def add_image_to_history(self, image) -> None:
        """
        Agregar imagen al historial de imágenes recientes
        
        Args:
            image: PIL Image object
        """
        self.recent_images.append(image)
        
        # Mantener solo las últimas 3 imágenes
        if len(self.recent_images) > self.max_images:
            self.recent_images.pop(0)
        
        print(f"📸 Historial de imágenes actualizado: {len(self.recent_images)} imágenes")

    def display_image_in_iterm2(self, image) -> None:
        """
        Mostrar imagen directamente en iTerm2 usando secuencias de escape
        
        Args:
            image: PIL Image object (ya viene escalada 5x desde grid_to_image)
        """
        try:
            import io
            
            # Convertir imagen a bytes
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_data = img_buffer.getvalue()
            
            # Codificar en base64
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            
            # Secuencia de escape de iTerm2 para mostrar imagen
            print(f"\033]1337;File=inline=1:{img_base64}\a")
            
        except Exception as e:
            print(f"⚠️ Error al mostrar imagen en iTerm2: {e}")

    def display_recent_images_in_iterm2(self) -> None:
        """
        Mostrar las imágenes recientes disponibles en iTerm2
        """
        if not self.recent_images:
            print("📸 No hay imágenes en el historial")
            return
        
        print(f"🖼️ === MAPAS RECIENTES ({len(self.recent_images)} imágenes) ===")
        
        for i, image in enumerate(self.recent_images):
            if i == len(self.recent_images) - 1:
                print(f"📍 Mapa actual (turno {self.action_counter}):")
            else:
                print(f"📜 Mapa anterior {i+1}:")
            
            self.display_image_in_iterm2(image)
            print()
        
        print("=" * 50)

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
            
            # Agregar imagen actual al historial
            self.add_image_to_history(map_image)
            
            # Mostrar imágenes recientes en iTerm2
            self.display_recent_images_in_iterm2()
            
            # Incluir memoria episódica en el prompt
            memory_summary = self.get_memory_summary()
            
            # Usar el contenido literal del archivo TOMAS.md como prompt base
            prompt = f"""
## ESTADO ACTUAL DEL JUEGO:
- Puntuación: {latest_frame.score}
- Acción número: {self.action_counter}

## Mapa en base64
{latest_frame.frame}

{memory_summary}
"""
            
            
            print(f"\n🤖 === PROMPT ===")
            print(prompt)
                        
            print(f"\n🤖 Llamando a Gemini...")
            
            response = self.gemini_service.generate_with_images_sync(
                prompt=prompt,
                images=self.recent_images,  # Enviar todas las imágenes recientes
                system_prompt=self.tomas_prompt
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
                "current_phase": extracted_json.get("current_phase", ""),
                "phase_progress": extracted_json.get("phase_progress", ""),
                "environment_observations": extracted_json.get("environment_observations", ""),
                "action_effects": extracted_json.get("action_effects", ""),
                "current_hypothesis": extracted_json.get("current_hypothesis", ""),
                "next_test": extracted_json.get("next_test", ""),
                "suggested_action": suggested_action_number,                              
            }
            
            print(f"\n🤖 ACCIÓN SUGERIDA POR GEMINI: {suggested_action_number} -> {action.value}")
            print(f"📋 Razonamiento: {extracted_json.get('current_hypothesis', '')}")
            
        else:
            # Fallback a acción aleatoria si no se puede extraer JSON válido
            print("⚠️ No se pudo extraer acción válida de Gemini, usando acción aleatoria")
            action = random.choice([a for a in GameAction if a is not GameAction.RESET])
            action.reasoning = {
                "fallback_reason": "Error al extraer JSON de Gemini",
                "random_choice": f"Acción aleatoria: {action.value}",                
            }
            print(f"\n🎲 ACCIÓN FALLBACK: {action.value} (aleatoria)")
        
        if action.is_complex():
            action.set_data(
                {
                    "x": random.randint(0, 63),
                    "y": random.randint(0, 63),
                }
            )
        
        # Guardar información para la memoria episódica
        self._last_frame_before_action = latest_frame
        self._last_action = action
        self._last_gemini_analysis = extracted_json
        
        print(f"\n✅ DECISIÓN FINAL: {action.value}")
        return action

    def append_frame(self, frame: FrameData) -> None:
        """Override para capturar cambios y actualizar memoria episódica"""
        super().append_frame(frame)
        
        # Si tenemos información de la acción anterior, actualizar memoria
        if hasattr(self, '_last_frame_before_action') and hasattr(self, '_last_action'):
            self.add_to_episodic_memory(
                action=self._last_action,
                frame_before=self._last_frame_before_action,
                frame_after=frame,
                gemini_analysis=getattr(self, '_last_gemini_analysis', None)
            )
            
            # Limpiar variables temporales
            delattr(self, '_last_frame_before_action')
            delattr(self, '_last_action')
            if hasattr(self, '_last_gemini_analysis'):
                delattr(self, '_last_gemini_analysis')