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

# Módulo de percepción espacial
from ..tomas_engine.spatial_perception_module import SpatialPerceptionModule


class Tomas(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 60

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

        # Inicializar el módulo de percepción espacial
        try:
            self.spatial_perception = SpatialPerceptionModule()
            print("✅ Módulo de Percepción Espacial inicializado correctamente")
        except Exception as e:
            print(f"⚠️ Error al inicializar Percepción Espacial: {e}")
            self.spatial_perception = None

        # Inicializar memoria episódica
        self.episodic_memory: List[Dict[str, Any]] = []
        self.max_memory_size = 10  # Mantener los últimos 10 movimientos

        # Almacenar las últimas 3 imágenes para análisis
        self.recent_images: List[Any] = []  # PIL Images
        self.max_images = 3

        # Sistema de memoria del Vector Cognitivo Global
        self.vcg_history: List[Dict[str, Any]] = []
        self.max_vcg_history = 5  # Mantener los últimos 5 VCG completos

        # Estado anterior del tablero para análisis diferencial
        # Inicializar con matriz dummy "ojos cerrados" (64x64 de ceros)
        self.previous_board_state = self._create_dummy_closed_eyes_matrix()
        self.previous_frame_data = None

        # Información de la acción anterior para análisis espacial
        self.previous_action = None
        self.previous_action_coordinates = None

        # Sistema de cola de órdenes de LOGOS
        self.pending_orders = []  # Cola de órdenes pendientes
        self.current_order_index = 0  # Índice de la orden actual
        self.orders_reasoning = ""  # Razonamiento de la secuencia de órdenes

        print(
            f"👁️ Matriz 'ojos cerrados' inicializada: {len(self.previous_board_state)}x{len(self.previous_board_state[0])} (todo en negro)"
        )
        print(f"📋 Sistema de órdenes LOGOS inicializado: 0 órdenes pendientes")

    def _create_dummy_closed_eyes_matrix(self) -> List[List[int]]:
        """
        Crear matriz dummy que representa 'ojos cerrados' - todo en negro (ceros)

        Esta matriz se usa como estado inicial "anterior" para que el análisis
        espacial funcione desde el primer turno del juego.

        Returns:
            Matriz 64x64 llena de ceros (color negro/fondo)
        """
        return [[0 for _ in range(64)] for _ in range(64)]

    def add_orders_from_logos(
        self, orders_list: List[Dict[str, Any]], reasoning: str = ""
    ) -> None:
        """
        Agregar una secuencia de órdenes de LOGOS para ejecutar

        Args:
            orders_list: Lista de órdenes con formato [{"action": "move_up", "coordinates": (x, y)}, ...]
            reasoning: Razonamiento detrás de la secuencia de órdenes
        """
        self.pending_orders = orders_list.copy()
        self.current_order_index = 0
        self.orders_reasoning = reasoning

        print(f"\n📋 === LOGOS HA EMITIDO {len(orders_list)} ÓRDENES ===")
        for i, order in enumerate(orders_list, 1):
            action_name = order.get("action", "unknown")
            coords = order.get("coordinates")
            coord_info = f" en {coords}" if coords else ""
            print(f"   {i}. {action_name}{coord_info}")
        print(f"🎯 Razonamiento: {reasoning}")
        print("=" * 50)

    def has_pending_orders(self) -> bool:
        """
        Verificar si hay órdenes pendientes por ejecutar

        Returns:
            True si hay órdenes pendientes, False si no
        """
        return self.pending_orders and self.current_order_index < len(
            self.pending_orders
        )

    def get_next_order(self) -> Optional[Dict[str, Any]]:
        """
        Obtener la siguiente orden a ejecutar

        Returns:
            Diccionario con la orden o None si no hay más órdenes
        """
        if self.has_pending_orders():
            current_order = self.pending_orders[self.current_order_index]
            self.current_order_index += 1

            print(
                f"\n⚡ EJECUTANDO ORDEN {self.current_order_index}/{len(self.pending_orders)}"
            )
            print(f"   🎯 Acción: {current_order.get('action', 'unknown')}")
            if "coordinates" in current_order:
                print(f"   📍 Coordenadas: {current_order['coordinates']}")
            print(
                f"   📋 Órdenes restantes: {len(self.pending_orders) - self.current_order_index}"
            )

            return current_order
        return None

    def clear_orders(self) -> None:
        """
        Limpiar todas las órdenes pendientes
        """
        orders_completed = self.current_order_index
        total_orders = len(self.pending_orders)

        self.pending_orders = []
        self.current_order_index = 0
        self.orders_reasoning = ""

        print(f"\n✅ === SECUENCIA DE ÓRDENES COMPLETADA ===")
        print(f"📊 Órdenes ejecutadas: {orders_completed}/{total_orders}")
        print(
            f"🔄 Regresando al flujo cognitivo completo: Spatial Perception → APEIRON → SOPHIA → LOGOS"
        )
        print("=" * 50)

    def _execute_pending_order(self) -> GameAction:
        """
        Ejecutar la siguiente orden pendiente de LOGOS

        Returns:
            GameAction correspondiente a la orden pendiente
        """
        next_order = self.get_next_order()

        if not next_order:
            # No hay más órdenes válidas, esto no debería pasar
            print(
                "❌ Error: se llamó _execute_pending_order pero no hay órdenes válidas"
            )
            self.clear_orders()
            # En lugar de aleatorio, fallback que nunca debería ejecutarse
            action = GameAction.ACTION1  # Solo como fallback de emergencia
            action.reasoning = (
                "Error interno: orden inválida, requiere revisión del código"
            )
            return action

        # Mapear la orden a GameAction
        action_command = next_order.get("action", "").lower()
        action_map = {
            "move_up": 1,
            "move_down": 2,
            "move_left": 3,
            "move_right": 4,
            "space": 5,
            "click": 6,
        }

        suggested_action_number = action_map.get(action_command)

        if suggested_action_number:
            action = self._map_action_number_to_game_action(suggested_action_number)

            # Configurar reasoning con información de la secuencia
            remaining_orders = len(self.pending_orders) - self.current_order_index
            action.reasoning = {
                "execution_mode": "ORDEN_SECUENCIAL_LOGOS",
                "orden_actual": f"{self.current_order_index}/{len(self.pending_orders)}",
                "accion_ejecutada": action_command,
                "ordenes_restantes": remaining_orders,
                "razonamiento_secuencia": self.orders_reasoning,
                "coordinates": next_order.get("coordinates"),
            }

            # Configurar coordenadas si es una acción compleja
            if action.is_complex() and "coordinates" in next_order:
                coords = next_order["coordinates"]
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    action.set_data({"x": coords[0], "y": coords[1]})
                else:
                    # Fallback a coordenadas aleatorias si las coordenadas no son válidas
                    action.set_data(
                        {"x": random.randint(0, 63), "y": random.randint(0, 63)}
                    )

            # Si esta es la última orden, informar sobre el próximo flujo
            if not self.has_pending_orders():
                print(f"\n🏁 Esta fue la ÚLTIMA orden de la secuencia")
                print(
                    f"🔄 En el próximo turno: Spatial Perception analizará TODOS los cambios acumulados"
                )
                print(
                    f"   → APEIRON verá la historia completa de las órdenes ejecutadas"
                )

            print(
                f"\n⚡ EJECUTANDO: {action_command} (orden {self.current_order_index}/{len(self.pending_orders)})"
            )
            return action
        else:
            # Acción no reconocida
            print(f"❌ Acción no reconocida en orden: '{action_command}'")
            print(f"🔄 Limpiando cola de órdenes y regresando al flujo completo")
            self.clear_orders()
            # En lugar de aleatorio, forzar el flujo completo en el siguiente choose_action
            action = GameAction.ACTION1  # Fallback temporal
            action.reasoning = f"Error: acción no reconocida '{action_command}', regresando al flujo completo"
            return action

    def load_markdown_file(self, file_path: str) -> str:
        """
        Cargar un archivo markdown de forma genérica

        Args:
            file_path: Ruta relativa al archivo .md desde el directorio tomas/

        Returns:
            Contenido del archivo como string
        """
        try:
            # Obtener la ruta del directorio actual del archivo
            current_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(current_dir, file_path)

            if not os.path.exists(full_path):
                print(f"⚠️ Archivo {file_path} no encontrado en: {full_path}")
                return f"# Error: Archivo {file_path} no encontrado"

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            print(f"✅ Archivo {file_path} cargado correctamente")
            return content

        except Exception as e:
            print(f"⚠️ Error al cargar {file_path}: {e}")
            return f"# Error: No se pudo cargar {file_path}"

    def analyze_spatial_perception(self, current_frame: FrameData) -> Optional[str]:
        """
        Realizar análisis de percepción espacial comparando el estado actual con el anterior

        Args:
            current_frame: Estado actual del juego

        Returns:
            Análisis espacial como string o None si no hay análisis disponible
        """
        if not self.spatial_perception or current_frame.is_empty():
            return None

        # NOTA: Ya no verificamos self.previous_board_state porque siempre tenemos la matriz dummy

        try:
            print(f"\n🎨 === INICIANDO ANÁLISIS DE PERCEPCIÓN ESPACIAL ===")

            # Determinar si es el primer turno (comparando con matriz dummy)
            is_first_turn = all(
                all(cell == 0 for cell in row) for row in self.previous_board_state
            )

            if is_first_turn:
                print(
                    f"👁️ PRIMER TURNO: Comparando matriz actual vs 'ojos cerrados' (dummy)"
                )
            else:
                print(f"🔄 TURNO SUBSECUENTE: Comparando estado actual vs anterior")

            # Realizar análisis de efectos de la acción anterior
            analysis_result = self.spatial_perception.analyze_action_effect(
                matrix_before=self.previous_board_state,
                matrix_after=current_frame.frame,
                action=self.previous_action if self.previous_action else 0,
                coordinates=self.previous_action_coordinates,
                include_visual_interpretation=True,  # Incluir análisis visual de Gemini
            )

            print(f"✅ Análisis espacial completado")
            print(f"📊 Resultado: {len(analysis_result)} caracteres")
            print(f"🔍 Análisis detallado:")
            print("=" * 50)
            print(analysis_result)
            print("=" * 50)

            return analysis_result

        except Exception as e:
            print(f"❌ Error en análisis de percepción espacial: {e}")
            return None

    def ask_apeiron_analysis(
        self,
        latest_frame: FrameData,
        vector_cognitivo_global_anterior: Optional[str] = None,
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Consultar a APEIRON (LLM1) para análisis perceptual

        Args:
            latest_frame: Estado actual del frame
            vector_cognitivo_global_anterior: VCG del turno anterior (opcional)

        Returns:
            Tupla con (respuesta_completa, json_extraido)
        """
        if not self.gemini_service or latest_frame.is_empty():
            return "Análisis no disponible", None

        try:
            # Cargar los archivos necesarios
            alma_content = self.load_markdown_file("alma.md")
            apeiron_system_prompt = self.load_markdown_file(
                "processus/apeiron/system-prompt.md"
            )
            apeiron_response_format = self.load_markdown_file(
                "processus/apeiron/response.md"
            )

            # Realizar análisis de percepción espacial si hay estado anterior
            spatial_analysis = self.analyze_spatial_perception(latest_frame)

            # Determinar si es el primer turno para contexto adicional
            is_first_turn = all(
                all(cell == 0 for cell in row) for row in self.previous_board_state
            )
            first_turn_context = ""
            if is_first_turn:
                first_turn_context = """
## CONTEXTO ESPECIAL - PRIMER TURNO:
Este es el primer turno del juego. El análisis de percepción espacial compara el estado actual del tablero contra una matriz "ojos cerrados" (todo en negro/ceros). Esto significa que TODAS las figuras/objetos visibles en el tablero actual son NUEVAS APARICIONES desde el estado inicial de "ojos cerrados".

El análisis espacial detectará todos los elementos del tablero como "apariciones" o "materializaciones" desde el estado de oscuridad total.
"""

            # Construir el prompt combinado
            combined_prompt = f"""
{alma_content}

{apeiron_system_prompt}

{apeiron_response_format}

## ESTADO ACTUAL DEL JUEGO:
- Puntuación: {latest_frame.score}
- Acción número: {self.action_counter}
- Estado del juego: {latest_frame.state}

{first_turn_context}

## input_fresco (board_state actual):
{latest_frame.frame}

## board_state_anterior (para análisis diferencial):
{self.previous_board_state if self.previous_board_state is not None else "Este es el primer turno - no hay estado anterior"}

## vector_cognitivo_global_anterior:
{vector_cognitivo_global_anterior if vector_cognitivo_global_anterior else "Este es el primer turno - no hay VCG anterior"}

## analisis_percepcion_espacial:
{spatial_analysis if spatial_analysis else "No hay análisis espacial disponible - primer turno o sin cambios"}

IMPORTANTE: Tu respuesta DEBE ser un JSON válido que incluya el campo "timestamp" en formato ISO 8601 (ejemplo: "2025-08-05T10:30:00.000Z"). Genera el timestamp actual automáticamente.
"""

            print(f"\n🧠 === CONSULTANDO APEIRON (LLM1) ===")
            print(f"🎯 Fase: Análisis Perceptual")

            # Log de entrada
            print(f"\n📥 ENTRADA APEIRON:")
            print(f"   📄 Alma: {len(alma_content)} chars")
            print(f"   📄 System Prompt: {len(apeiron_system_prompt)} chars")
            print(f"   📄 Response Format: {len(apeiron_response_format)} chars")
            print(
                f"   🎮 Frame Data: {latest_frame.frame.shape if hasattr(latest_frame.frame, 'shape') else 'N/A'}"
            )
            print(
                f"   📊 VCG Anterior: {len(vector_cognitivo_global_anterior) if vector_cognitivo_global_anterior else 0} chars"
            )
            print(
                f"   🎨 Percepción Espacial: {len(spatial_analysis) if spatial_analysis else 0} chars"
            )
            print(f"   📝 Prompt Total: {len(combined_prompt)} chars")

            response = self.gemini_service.generate_with_images_sync(
                prompt=combined_prompt,
                images=[],  # Sin imágenes por ahora, solo matriz
                system_prompt=alma_content,
            )

            # Log de salida
            print(f"\n📤 SALIDA APEIRON:")
            print(f"   ✅ Completado en {response.duration_ms}ms")
            print(f"   🎫 Tokens: {response.usage['total_tokens']}")
            print(f"   📝 Respuesta: {len(response.content)} chars")
            print(f"   📄 Contenido completo:")
            print(f"{response.content}")

            # Extraer JSON de la respuesta
            extracted_json = self.extract_json_from_llm_response(
                response.content, "apeiron"
            )

            return response.content, extracted_json

        except Exception as e:
            print(f"❌ Error en APEIRON: {e}")
            return f"Error en APEIRON: {str(e)}", None

    def ask_sophia_analysis(
        self, apeiron_response: str
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Consultar a SOPHIA (LLM2) para análisis epistémico

        Args:
            apeiron_response: Respuesta completa de APEIRON del turno actual

        Returns:
            Tupla con (respuesta_completa, json_extraido)
        """
        if not self.gemini_service:
            return "Análisis no disponible", None

        try:
            # Cargar los archivos necesarios
            alma_content = self.load_markdown_file("alma.md")
            sophia_system_prompt = self.load_markdown_file(
                "processus/sophia/system-prompt.md"
            )
            sophia_response_format = self.load_markdown_file(
                "processus/sophia/response.md"
            )

            # Construir el prompt combinado
            combined_prompt = f"""
{alma_content}

{sophia_system_prompt}

{sophia_response_format}

## Vector Cognitivo Global actualizado por APEIRON:
{apeiron_response}

IMPORTANTE: Tu respuesta DEBE ser un JSON válido que incluya el campo "timestamp" en formato ISO 8601 (ejemplo: "2025-08-05T10:30:00.000Z"). Genera el timestamp actual automáticamente.
"""

            print(f"\n🧠 === CONSULTANDO SOPHIA (LLM2) ===")
            print(f"🎯 Fase: Análisis Epistémico")

            # Log de entrada
            print(f"\n📥 ENTRADA SOPHIA:")
            print(f"   📄 Alma: {len(alma_content)} chars")
            print(f"   📄 System Prompt: {len(sophia_system_prompt)} chars")
            print(f"   📄 Response Format: {len(sophia_response_format)} chars")
            print(f"   🧠 Respuesta APEIRON: {len(apeiron_response)} chars")
            print(f"   📝 Prompt Total: {len(combined_prompt)} chars")

            response = self.gemini_service.generate_with_images_sync(
                prompt=combined_prompt,
                images=[],  # Sophia no necesita imágenes, trabaja con conceptos
                system_prompt=alma_content,
            )

            # Log de salida
            print(f"\n📤 SALIDA SOPHIA:")
            print(f"   ✅ Completado en {response.duration_ms}ms")
            print(f"   🎫 Tokens: {response.usage['total_tokens']}")
            print(f"   📝 Respuesta: {len(response.content)} chars")
            print(f"   📄 Contenido completo:")
            print(f"{response.content}")

            # Extraer JSON de la respuesta
            extracted_json = self.extract_json_from_llm_response(
                response.content, "sophia"
            )

            return response.content, extracted_json

        except Exception as e:
            print(f"❌ Error en SOPHIA: {e}")
            return f"Error en SOPHIA: {str(e)}", None

    def ask_logos_analysis(
        self, apeiron_response: str, sophia_response: str
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Consultar a LOGOS (LLM3) para deliberación y acción

        Args:
            apeiron_response: Respuesta completa de APEIRON del turno actual
            sophia_response: Respuesta completa de SOPHIA del turno actual

        Returns:
            Tupla con (respuesta_completa, json_extraido)
        """
        if not self.gemini_service:
            return "Análisis no disponible", None

        try:
            # Cargar los archivos necesarios
            alma_content = self.load_markdown_file("alma.md")
            logos_system_prompt = self.load_markdown_file(
                "processus/logos/system-prompt.md"
            )
            logos_response_format = self.load_markdown_file(
                "processus/logos/response.md"
            )

            # Obtener la respuesta de LOGOS del turno anterior si existe
            logos_anterior = None
            if self.vcg_history:
                last_vcg = self.vcg_history[-1]
                logos_anterior = last_vcg.get("logos_response", "")

            # Construir el prompt combinado
            combined_prompt = f"""
{alma_content}

{logos_system_prompt}

{logos_response_format}

## Salida de APEIRON (Percepción actual):
{apeiron_response}

## Salida de SOPHIA (Episteme actual):
{sophia_response}

## Respuesta de LOGOS del turno anterior:
{logos_anterior if logos_anterior else "Este es el primer turno - no hay LOGOS anterior"}

IMPORTANTE: Tu respuesta DEBE ser un JSON válido que incluya el campo "timestamp" en formato ISO 8601 (ejemplo: "2025-08-05T10:30:00.000Z"). Genera el timestamp actual automáticamente.
"""

            print(f"\n🧠 === CONSULTANDO LOGOS (LLM3) ===")
            print(f"🎯 Fase: Deliberación y Acción")

            # Log de entrada
            print(f"\n📥 ENTRADA LOGOS:")
            print(f"   📄 Alma: {len(alma_content)} chars")
            print(f"   📄 System Prompt: {len(logos_system_prompt)} chars")
            print(f"   📄 Response Format: {len(logos_response_format)} chars")
            print(f"   🧠 Respuesta APEIRON: {len(apeiron_response)} chars")
            print(f"   🧠 Respuesta SOPHIA: {len(sophia_response)} chars")
            print(
                f"   ⚡ LOGOS anterior: {len(logos_anterior) if logos_anterior else 0} chars"
            )
            print(f"   📝 Prompt Total: {len(combined_prompt)} chars")

            response = self.gemini_service.generate_with_images_sync(
                prompt=combined_prompt,
                images=[],  # Logos no necesita imágenes, trabaja con estrategia
                system_prompt=alma_content,
            )

            # Log de salida
            print(f"\n📤 SALIDA LOGOS:")
            print(f"   ✅ Completado en {response.duration_ms}ms")
            print(f"   🎫 Tokens: {response.usage['total_tokens']}")
            print(f"   📝 Respuesta: {len(response.content)} chars")
            print(f"   📄 Contenido completo:")
            print(f"{response.content}")

            # Extraer JSON de la respuesta
            extracted_json = self.extract_json_from_llm_response(
                response.content, "logos"
            )

            return response.content, extracted_json

        except Exception as e:
            print(f"❌ Error en LOGOS: {e}")
            return f"Error en LOGOS: {str(e)}", None

    def extract_json_from_llm_response(
        self, llm_response: str, llm_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extrae el JSON de la respuesta del LLM según el tipo (apeiron, sophia, logos)

        Args:
            llm_response: Respuesta completa del LLM
            llm_type: Tipo de LLM ("apeiron", "sophia", "logos")

        Returns:
            Diccionario con el JSON extraído o None si no se encuentra
        """
        try:
            # Buscar el JSON principal usando un enfoque más preciso
            # Primero intentar encontrar bloques JSON con llaves balanceadas
            json_start = llm_response.find("{")
            if json_start == -1:
                print(f"❌ No se encontró JSON en la respuesta de {llm_type.upper()}")
                return None

            # Buscar el JSON completo balanceando llaves
            brace_count = 0
            json_end = json_start
            for i, char in enumerate(llm_response[json_start:], json_start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            if brace_count != 0:
                print(
                    f"❌ JSON mal formateado en {llm_type.upper()} - llaves no balanceadas"
                )
                return None

            # Extraer el JSON completo
            json_text = llm_response[json_start:json_end]

            try:
                parsed_json = json.loads(json_text)

                # Definir campos requeridos según el tipo de LLM
                required_fields = {
                    "apeiron": [
                        "timestamp",
                        "causal_narrative_of_turn",
                        "special_events_detected",
                        "conceptualized_entities",
                        "new_turn_learnings",
                        "synthesis_for_next_cycle",
                    ],
                    "sophia": [
                        "timestamp",
                        "epistemic_analysis",
                        "archetype_analysis",
                        "verified_game_rules",
                        "global_game_theories",
                    ],
                    "logos": [
                        "timestamp",
                        "intent_phase",
                        "counsel_phase",
                        "choice_phase",
                        "command_phase",
                        "predictive_judgment_phase",
                    ],
                }

                target_fields = required_fields.get(llm_type, [])

                # Validar que tenga los campos requeridos según el tipo
                if all(field in parsed_json for field in target_fields):
                    # Validación adicional específica para APEIRON
                    if (
                        llm_type == "apeiron"
                        and "special_events_detected" in parsed_json
                    ):
                        special_events = parsed_json.get("special_events_detected", [])
                        if special_events and isinstance(special_events, list):
                            if "LEVEL_COMPLETE" in special_events:
                                print(
                                    f"🎆 APEIRON detectó evento LEVEL_COMPLETE - Transición de nivel inminente"
                                )

                    # Validación adicional específica para Sophia
                    if llm_type == "sophia" and "global_game_theories" in parsed_json:
                        theories = parsed_json.get("global_game_theories", [])
                        if theories and isinstance(theories, list):
                            # Verificar que al menos la teoría activa tenga los nuevos campos
                            for theory in theories:
                                if theory.get("status") in [
                                    "ACTIVE",
                                    "PARTIALLY_CORROBORATED",
                                    "HIGHLY_CORROBORATED",
                                ]:
                                    if (
                                        "victory_hypothesis" not in theory
                                        or "means_catalog" not in theory
                                    ):
                                        print(
                                            f"⚠️ Teoría activa de SOPHIA sin campos victory_hypothesis o means_catalog"
                                        )
                                        print(
                                            f"   Se esperan los campos: victory_hypothesis, means_catalog"
                                        )
                                        print(
                                            f"   Teoría encontrada: {list(theory.keys())}"
                                        )
                                        # No es un error crítico, solo una advertencia

                    print(f"✅ JSON válido extraído de {llm_type.upper()}")
                    return parsed_json
                else:
                    print(
                        f"⚠️ JSON de {llm_type.upper()} no tiene todos los campos requeridos"
                    )
                    print(f"   Esperados: {target_fields}")
                    print(f"   Encontrados: {list(parsed_json.keys())}")
                    return None

            except json.JSONDecodeError as e:
                print(f"❌ Error al parsear JSON de {llm_type.upper()}: {e}")
                return None

        except Exception as e:
            print(f"❌ Error al extraer JSON de {llm_type.upper()}: {e}")
            return None

    def llmJsonExtractor(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """
        Método legacy - mantener para compatibilidad
        """
        return self.extract_json_from_llm_response(llm_response, "logos")

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

        return action_map.get(
            action_number, GameAction.ACTION1
        )  # Default a ACTION1 si no se encuentra

    def add_to_episodic_memory(
        self,
        action: GameAction,
        frame_before: FrameData,
        frame_after: FrameData,
        gemini_analysis: Optional[Dict[str, Any]] = None,
    ) -> None:
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
            "gemini_reasoning": (
                gemini_analysis.get("current_hypothesis", "") if gemini_analysis else ""
            ),
            "timestamp": time.time(),
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
            6: "Click",
        }
        return action_names.get(action_value, f"Acción {action_value}")

    def get_memory_summary(self) -> str:
        """
        Generar un resumen de la memoria episódica para el prompt de Gemini

        Returns:
            String con resumen de movimientos recientes
        """
        if not self.episodic_memory:
            return (
                "## Historial de Movimientos\nEste es el primer movimiento del juego."
            )

        summary = "## Historial de Movimientos Recientes\n\n"

        for i, entry in enumerate(
            self.episodic_memory[-5:], 1
        ):  # Últimos 5 movimientos
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
            recent_scores = [
                entry["score_change"] for entry in self.episodic_memory[-3:]
            ]
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

        print(
            f"📸 Historial de imágenes actualizado: {len(self.recent_images)} imágenes"
        )

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
            image.save(img_buffer, format="PNG")
            img_data = img_buffer.getvalue()

            # Codificar en base64
            img_base64 = base64.b64encode(img_data).decode("utf-8")

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

        # Crear directorio images si no existe
        import os

        os.makedirs("images", exist_ok=True)

        # Guardar la imagen con información del estado
        filename = f"images/tomas_map_action_{self.action_counter:03d}_score_{latest_frame.score:03d}.png"
        map_image.save(filename)

        print(f"Imagen del mapa guardada como: {filename}")
        print(f"Dimensiones de la imagen: {map_image.size}")
        print("=" * 40)

        return map_image

    def ask_gemini_analysis(
        self, latest_frame: FrameData
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Ejecutar el flujo secuencial APEIRON → SOPHIA → LOGOS

        Returns:
            Tupla con (respuesta_completa_de_logos, json_extraido_de_logos)
        """
        if not self.gemini_service or latest_frame.is_empty():
            return "Análisis no disponible", None

        try:
            # Generar imagen del mapa actual (comentado por ahora)
            # map_image = grid_to_image(latest_frame.frame)

            # Agregar imagen actual al historial (comentado por ahora)
            # self.add_image_to_history(map_image)

            # Mostrar imágenes recientes en iTerm2 (comentado por ahora)
            # self.display_recent_images_in_iterm2()

            print(f"\n🧠 === INICIANDO FLUJO COGNITIVO TOMAS ===")
            print(f"🎯 Turno {self.action_counter} | Puntuación: {latest_frame.score}")
            print(f"🔄 Flujo: APEIRON → SOPHIA → LOGOS")
            print("=" * 60)

            # Guardar el estado actual como "anterior" para el próximo turno
            # (Esto se hace al INICIO del turno, no al final)

            # Obtener VCG anterior si existe
            vector_cognitivo_global_anterior = (
                self.get_vector_cognitivo_global_anterior()
            )

            # Debug: mostrar si tenemos VCG anterior
            if vector_cognitivo_global_anterior:
                print(
                    f"📚 VCG Anterior disponible: {len(vector_cognitivo_global_anterior)} chars"
                )
            else:
                print(f"📚 Primer turno - No hay VCG anterior")

            # PASO 1: APEIRON - Análisis Perceptual
            apeiron_response, apeiron_json = self.ask_apeiron_analysis(
                latest_frame, vector_cognitivo_global_anterior
            )

            if not apeiron_json:
                print(
                    "⚠️ APEIRON no devolvió JSON válido, continuando con respuesta textual"
                )

            # PASO 2: SOPHIA - Análisis Epistémico
            sophia_response, sophia_json = self.ask_sophia_analysis(apeiron_response)

            if not sophia_json:
                print(
                    "⚠️ SOPHIA no devolvió JSON válido, continuando con respuesta textual"
                )

            # PASO 3: LOGOS - Deliberación y Acción
            logos_response, logos_json = self.ask_logos_analysis(
                apeiron_response, sophia_response
            )

            if not logos_json:
                print("⚠️ LOGOS no devolvió JSON válido")

            print(f"\n✅ === FLUJO COGNITIVO COMPLETADO ===")
            print(f"📊 Total de pasos ejecutados: APEIRON ✅ | SOPHIA ✅ | LOGOS ✅")
            print("=" * 60)

            # Guardar el VCG completo para el próximo turno
            # IMPORTANTE: Guardamos el estado ACTUAL como referencia para el PRÓXIMO turno
            self.previous_frame_data = latest_frame
            self.previous_board_state = latest_frame.frame
            self.save_vector_cognitivo_global(
                apeiron_response, sophia_response, logos_response
            )

            # Retornar la respuesta de LOGOS (que contiene la decisión de acción)
            return logos_response, logos_json

        except Exception as e:
            print(f"❌ Error en flujo TOMAS: {e}")
            return f"Error en flujo TOMAS: {str(e)}", None

    def get_vector_cognitivo_global_anterior(self) -> Optional[str]:
        """
        Obtener el Vector Cognitivo Global completo del turno anterior
        """
        if not self.vcg_history:
            return None

        # Obtener el VCG más reciente
        last_vcg = self.vcg_history[-1]

        # Construir el VCG anterior con toda la información
        vcg_anterior = f"""
## Vector Cognitivo Global del Turno Anterior (Turno {last_vcg['turno']})

### Estado LLM1 (APEIRON - Percepción anterior):
{last_vcg['apeiron_response']}

### Estado LLM2 (SOPHIA - Abstracción anterior):
{last_vcg['sophia_response']}

### Estado LLM3 (LOGOS - Deliberación anterior):
{last_vcg['logos_response']}

### board_state anterior:
{last_vcg['board_state']}

### Contexto del turno:
- Puntuación: {last_vcg['score']}
- Estado del juego: {last_vcg['game_state']}
- Timestamp: {last_vcg['timestamp']}
"""
        return vcg_anterior

    def save_vector_cognitivo_global(
        self, apeiron_response: str, sophia_response: str, logos_response: str
    ) -> None:
        """
        Guardar el Vector Cognitivo Global completo del turno actual con toda la información
        """
        try:
            print(f"\n💾 === GUARDANDO VCG TURNO {self.action_counter} ===")

            # Crear VCG completo con toda la información necesaria
            vcg_completo = {
                "turno": self.action_counter,
                "timestamp": time.time(),
                "apeiron_response": apeiron_response,
                "sophia_response": sophia_response,
                "logos_response": logos_response,
                "board_state": (
                    str(self.previous_frame_data.frame)
                    if self.previous_frame_data
                    else "N/A"
                ),
                "score": (
                    self.previous_frame_data.score if self.previous_frame_data else 0
                ),
                "game_state": (
                    str(self.previous_frame_data.state)
                    if self.previous_frame_data
                    else "UNKNOWN"
                ),
            }

            # Agregar a la historia de VCG
            self.vcg_history.append(vcg_completo)

            # Mantener solo los últimos N VCG
            if len(self.vcg_history) > self.max_vcg_history:
                self.vcg_history.pop(0)

            print(f"✅ VCG completo guardado - Turno {vcg_completo['turno']}")
            print(f"   📝 APEIRON: {len(apeiron_response)} chars")
            print(f"   🧠 SOPHIA: {len(sophia_response)} chars")
            print(f"   ⚡ LOGOS: {len(logos_response)} chars")
            print(f"   🎮 Board State: Guardado")
            print(f"   📊 Score: {vcg_completo['score']}")
            print(f"   📚 Historia VCG: {len(self.vcg_history)}/{self.max_vcg_history}")

        except Exception as e:
            print(f"⚠️ Error al guardar VCG: {e}")

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

        # PRIORIDAD 1: Verificar si hay órdenes pendientes de LOGOS
        if self.has_pending_orders():
            print(f"\n📋 === EJECUTANDO ÓRDENES PENDIENTES DE LOGOS ===")
            return self._execute_pending_order()

        # PRIORIDAD 2: Si no hay órdenes pendientes, ejecutar flujo cognitivo completo
        # Ejecutar el flujo cognitivo TOMAS (APEIRON → SOPHIA → LOGOS)
        logos_response, logos_json = self.ask_gemini_analysis(latest_frame)

        # Intentar extraer órdenes (singular o múltiples) de la respuesta de LOGOS
        action = None
        if logos_json and "command_phase" in logos_json:
            command_phase = logos_json["command_phase"]

            # OPCIÓN 1: Verificar si LOGOS devolvió múltiples órdenes secuenciales
            if (
                "sequential_orders" in command_phase
                and command_phase["sequential_orders"]
            ):
                ordenes_lista = command_phase["sequential_orders"]
                reasoning = command_phase.get(
                    "chosen_plan_reasoning", "Secuencia de órdenes de LOGOS"
                )

                if isinstance(ordenes_lista, list) and len(ordenes_lista) > 0:
                    # LOGOS devolvió múltiples órdenes - guardarlas para ejecución secuencial
                    self.add_orders_from_logos(ordenes_lista, reasoning)

                    # Ejecutar la primera orden inmediatamente
                    return self._execute_pending_order()

            # OPCIÓN 2: Orden única (comportamiento original)
            immediate_command = command_phase.get("immediate_command", {})

            if "action" in immediate_command:
                action_command = immediate_command["action"]

                # Mapear comandos de texto a números de acción
                action_map = {
                    "move_up": 1,
                    "move_down": 2,
                    "move_left": 3,
                    "move_right": 4,
                    "space": 5,
                    "click": 6,
                }

                suggested_action_number = action_map.get(action_command.lower())

                if suggested_action_number:
                    action = self._map_action_number_to_game_action(
                        suggested_action_number
                    )

                    # Configurar reasoning con toda la información de LOGOS
                    action.reasoning = {
                        "tomas_flow": "APEIRON → SOPHIA → LOGOS",
                        "execution_mode": "ORDEN_UNICA_LOGOS",
                        "objetivo_turno": logos_json.get("intent_phase", {}).get(
                            "plan_objective", ""
                        ),
                        "decision_final": logos_json.get("choice_phase", {}).get(
                            "final_decision", {}
                        ),
                        "comando_inmediato": immediate_command,
                        "resultado_esperado": logos_json.get(
                            "predictive_judgment_phase", {}
                        ).get("expected_outcome", ""),
                        "suggested_action": suggested_action_number,
                    }

                    print(
                        f"\n⚡ ACCIÓN ÚNICA DECIDIDA POR LOGOS: {action_command} -> {action.value}"
                    )
                    print(f"🎯 Objetivo: {action.reasoning['objetivo_turno']}")
                    print(
                        f"🔮 Resultado esperado: {action.reasoning['resultado_esperado']}"
                    )

        # Fallback si no se pudo extraer acción válida de LOGOS
        if not action:
            print(
                "⚠️ No se pudo extraer acción válida de LOGOS, usando acción aleatoria"
            )
            action = random.choice([a for a in GameAction if a is not GameAction.RESET])
            action.reasoning = {
                "fallback_reason": "Error al extraer acción de LOGOS",
                "random_choice": f"Acción aleatoria: {action.value}",
                "logos_response_available": logos_json is not None,
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
        self._last_gemini_analysis = logos_json

        # Guardar información de acción para el próximo análisis espacial
        self.previous_action = (
            action.value
            if hasattr(action, "value") and isinstance(action.value, int)
            else None
        )

        # Extraer coordenadas si es una acción compleja
        if action.is_complex() and hasattr(action, "data") and action.data:
            self.previous_action_coordinates = (
                action.data.get("x"),
                action.data.get("y"),
            )
        else:
            self.previous_action_coordinates = None

        print(f"\n✅ DECISIÓN FINAL: {action.value}")
        return action

    def append_frame(self, frame: FrameData) -> None:
        """Override para capturar cambios y actualizar memoria episódica"""
        super().append_frame(frame)

        # Si tenemos información de la acción anterior, actualizar memoria
        if hasattr(self, "_last_frame_before_action") and hasattr(self, "_last_action"):
            self.add_to_episodic_memory(
                action=self._last_action,
                frame_before=self._last_frame_before_action,
                frame_after=frame,
                gemini_analysis=getattr(self, "_last_gemini_analysis", None),
            )

            # Limpiar variables temporales
            delattr(self, "_last_frame_before_action")
            delattr(self, "_last_action")
            if hasattr(self, "_last_gemini_analysis"):
                delattr(self, "_last_gemini_analysis")
