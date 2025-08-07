import os
import base64
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from PIL import Image
import io

import google.generativeai as genai
from .langfuse_service import LangfuseService


@dataclass
class GeminiImageData:
    """Datos de imagen para enviar a Gemini"""

    data: bytes
    mime_type: str


@dataclass
class GeminiResponse:
    """Respuesta del servicio Gemini"""

    content: str
    usage: Dict[str, int]
    model: str
    finish_reason: str
    duration_ms: int


class GeminiService:
    """Servicio para interactuar con Google Gemini AI"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-pro",
        enable_observability: bool = True,
    ):
        """
        Inicializar el servicio Gemini

        Args:
            api_key: Clave API de Google (si no se proporciona, se usa la variable de entorno)
            model: Modelo a utilizar por defecto
            enable_observability: Habilitar observabilidad con Langfuse
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.temperature = 0.7
        self.max_output_tokens = 65000

        if not self.api_key:
            raise ValueError(
                "Se requiere GEMINI_API_KEY como variable de entorno o parámetro"
            )

        # Configurar la API de Gemini
        genai.configure(api_key=self.api_key)

        # Inicializar observabilidad con Langfuse
        self.langfuse = LangfuseService(enabled=enable_observability)

    def is_available(self) -> bool:
        """Verificar si el servicio está disponible"""
        return bool(self.api_key)

    def _prepare_image_from_pil(self, pil_image: Image.Image) -> GeminiImageData:
        """
        Convertir imagen PIL a formato compatible con Gemini

        Args:
            pil_image: Imagen PIL

        Returns:
            GeminiImageData con los datos de la imagen
        """
        # Convertir PIL image a bytes
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format="PNG")
        img_byte_arr = img_byte_arr.getvalue()

        return GeminiImageData(data=img_byte_arr, mime_type="image/png")

    def _prepare_image_from_path(self, image_path: str) -> GeminiImageData:
        """
        Cargar imagen desde archivo

        Args:
            image_path: Ruta al archivo de imagen

        Returns:
            GeminiImageData con los datos de la imagen
        """
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Determinar el tipo MIME basado en la extensión
        if image_path.lower().endswith(".png"):
            mime_type = "image/png"
        elif image_path.lower().endswith((".jpg", ".jpeg")):
            mime_type = "image/jpeg"
        elif image_path.lower().endswith(".gif"):
            mime_type = "image/gif"
        elif image_path.lower().endswith(".webp"):
            mime_type = "image/webp"
        else:
            mime_type = "image/png"  # Por defecto

        return GeminiImageData(data=image_data, mime_type=mime_type)

    async def generate_with_image(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        image_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        trace_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        game_id: Optional[str] = None,
    ) -> GeminiResponse:
        """
        Generar texto con Gemini usando prompt e imagen

        Args:
            prompt: Prompt de texto
            image: Imagen PIL (opcional)
            image_path: Ruta a archivo de imagen (opcional)
            system_prompt: Prompt del sistema (opcional)
            temperature: Temperatura para la generación (opcional)
            model: Modelo específico a usar (opcional)
            trace_name: Nombre del trace para Langfuse (opcional)
            user_id: ID del usuario para Langfuse (opcional)
            session_id: ID de la sesión para Langfuse (opcional)
            game_id: ID del juego para tag en Langfuse (opcional)

        Returns:
            GeminiResponse con la respuesta generada
        """
        if not image and not image_path:
            raise ValueError("Se debe proporcionar una imagen (PIL) o ruta de imagen")

        # Preparar la imagen
        if image:
            image_data = self._prepare_image_from_pil(image)
        else:
            image_data = self._prepare_image_from_path(image_path)

        # Configurar el modelo
        model_name = model or self.model
        temp = temperature if temperature is not None else self.temperature

        # Crear trace para observabilidad
        trace = self.langfuse.create_trace(
            name=trace_name or f"gemini_async_image_generation",
            user_id=user_id,
            session_id=session_id,
            metadata={
                "model": model_name,
                "temperature": temp,
                "has_system_prompt": system_prompt is not None,
                "image_source": "pil" if image else "path",
                "async": True,
            },
            tags=["gemini", "vision", "async", "single-image", "generation"],
        )

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            ),
        )

        # Preparar el contenido
        parts = []

        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)

        # Agregar el prompt principal
        parts.append(prompt)

        # Agregar la imagen
        parts.append({"mime_type": image_data.mime_type, "data": image_data.data})

        try:
            # Medir tiempo de ejecución
            print(f"\n📡 Calling Gemini {model_name} with image...")
            start_time = time.time()

            # Generar contenido
            response = await model_instance.generate_content_async(parts)

            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            print(f"✅ Gemini {model_name} async response received in {duration_ms}ms")

            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(
                    response.usage_metadata, "prompt_token_count", 0
                ),
                "completion_tokens": getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ),
                "total_tokens": getattr(
                    response.usage_metadata, "total_token_count", 0
                ),
            }

            # Track en Langfuse
            self.langfuse.track_gemini_call(
                trace_id=trace.trace_id,
                model=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                response=response.text,
                usage=usage,
                start_time=start_time,
                end_time=end_time,
                temperature=temp,
                has_images=True,
                game_id=game_id,
            )

            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=(
                    getattr(response.candidates[0], "finish_reason", "STOP")
                    if response.candidates
                    else "STOP"
                ),
                duration_ms=duration_ms,
            )

            return gemini_response

        except Exception as error:
            print(f"Error llamando a la API de Gemini: {error}")
            raise Exception(f"Error de la API de Gemini: {str(error)}")

    def generate_with_images_sync(
        self,
        prompt: str,
        images: Optional[List[Image.Image]] = None,
        image_paths: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        trace_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        game_id: Optional[str] = None,
    ) -> GeminiResponse:
        """
        Versión que acepta múltiples imágenes

        Args:
            prompt: Prompt de texto
            images: Lista de imágenes PIL (opcional)
            image_paths: Lista de rutas a archivos de imagen (opcional)
            system_prompt: Prompt del sistema (opcional)
            temperature: Temperatura para la generación (opcional)
            model: Modelo específico a usar (opcional)
            trace_name: Nombre del trace para Langfuse (opcional)
            user_id: ID del usuario para Langfuse (opcional)
            session_id: ID de la sesión para Langfuse (opcional)
            game_id: ID del juego para tag en Langfuse (opcional)

        Returns:
            GeminiResponse con la respuesta generada
        """
        # if not images and not image_paths:
        #     raise ValueError("Se debe proporcionar al menos una imagen (PIL) o ruta de imagen")

        # Preparar las imágenes
        image_data_list = []

        if images:
            for img in images:
                image_data_list.append(self._prepare_image_from_pil(img))

        if image_paths:
            for path in image_paths:
                image_data_list.append(self._prepare_image_from_path(path))

        # Configurar el modelo
        model_name = model or self.model
        temp = temperature if temperature is not None else self.temperature

        # Crear trace para observabilidad
        trace = self.langfuse.create_trace(
            name=trace_name or f"gemini_multi_image_generation",
            user_id=user_id,
            session_id=session_id,
            metadata={
                "model": model_name,
                "temperature": temp,
                "has_system_prompt": system_prompt is not None,
                "image_count": len(image_data_list),
            },
            tags=["gemini", "vision", "multi-image", "generation"],
        )

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            ),
        )

        # Preparar el contenido
        parts = []

        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)

        # Agregar el prompt principal
        parts.append(prompt)

        # Agregar todas las imágenes
        for image_data in image_data_list:
            parts.append({"mime_type": image_data.mime_type, "data": image_data.data})

        try:
            # Medir tiempo de ejecución
            print(
                f"\n📡 Calling Gemini {model_name} with {len(image_data_list)} images..."
            )
            start_time = time.time()

            # Generar contenido
            response = model_instance.generate_content(parts)

            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            print(
                f"✅ Gemini {model_name} multi-image response received in {duration_ms}ms"
            )

            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(
                    response.usage_metadata, "prompt_token_count", 0
                ),
                "completion_tokens": getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ),
                "total_tokens": getattr(
                    response.usage_metadata, "total_token_count", 0
                ),
            }

            # Track en Langfuse
            self.langfuse.track_gemini_call(
                trace_id=trace.trace_id,
                model=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                response=response.text,
                usage=usage,
                start_time=start_time,
                end_time=end_time,
                temperature=temp,
                has_images=True,
                game_id=game_id,
            )

            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=(
                    getattr(response.candidates[0], "finish_reason", "STOP")
                    if response.candidates
                    else "STOP"
                ),
                duration_ms=duration_ms,
            )

            return gemini_response

        except Exception as error:
            print(f"Error llamando a la API de Gemini: {error}")
            raise Exception(f"Error de la API de Gemini: {str(error)}")

    def generate_with_image_sync(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        image_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        trace_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        game_id: Optional[str] = None,
    ) -> GeminiResponse:
        """
        Versión síncrona de generate_with_image

        Args:
            prompt: Prompt de texto
            image: Imagen PIL (opcional)
            image_path: Ruta a archivo de imagen (opcional)
            system_prompt: Prompt del sistema (opcional)
            temperature: Temperatura para la generación (opcional)
            model: Modelo específico a usar (opcional)
            trace_name: Nombre del trace para Langfuse (opcional)
            user_id: ID del usuario para Langfuse (opcional)
            session_id: ID de la sesión para Langfuse (opcional)
            game_id: ID del juego para tag en Langfuse (opcional)

        Returns:
            GeminiResponse con la respuesta generada
        """
        if not image and not image_path:
            raise ValueError("Se debe proporcionar una imagen (PIL) o ruta de imagen")

        # Preparar la imagen
        if image:
            image_data = self._prepare_image_from_pil(image)
        else:
            image_data = self._prepare_image_from_path(image_path)

        # Configurar el modelo
        model_name = model or self.model
        temp = temperature if temperature is not None else self.temperature

        # Crear trace para observabilidad
        trace = self.langfuse.create_trace(
            name=trace_name or f"gemini_single_image_generation",
            user_id=user_id,
            session_id=session_id,
            metadata={
                "model": model_name,
                "temperature": temp,
                "has_system_prompt": system_prompt is not None,
                "image_source": "pil" if image else "path",
            },
            tags=["gemini", "vision", "single-image", "generation"],
        )

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            ),
        )

        # Preparar el contenido
        parts = []

        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)

        # Agregar el prompt principal
        parts.append(prompt)

        # Agregar la imagen
        parts.append({"mime_type": image_data.mime_type, "data": image_data.data})

        try:
            # Medir tiempo de ejecución
            print(f"\n📡 Calling Gemini {model_name} with single image...")
            start_time = time.time()

            # Generar contenido
            response = model_instance.generate_content(parts)

            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            print(
                f"✅ Gemini {model_name} single image response received in {duration_ms}ms"
            )

            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(
                    response.usage_metadata, "prompt_token_count", 0
                ),
                "completion_tokens": getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ),
                "total_tokens": getattr(
                    response.usage_metadata, "total_token_count", 0
                ),
            }

            # Track en Langfuse
            self.langfuse.track_gemini_call(
                trace_id=trace.trace_id,
                model=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                response=response.text,
                usage=usage,
                start_time=start_time,
                end_time=end_time,
                temperature=temp,
                has_images=True,
                game_id=game_id,
            )

            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=(
                    getattr(response.candidates[0], "finish_reason", "STOP")
                    if response.candidates
                    else "STOP"
                ),
                duration_ms=duration_ms,
            )

            return gemini_response

        except Exception as error:
            print(f"Error llamando a la API de Gemini: {error}")
            raise Exception(f"Error de la API de Gemini: {str(error)}")

    def generate_text_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        trace_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        game_id: Optional[str] = None,
    ) -> GeminiResponse:
        """
        Generar texto sin imágenes usando Gemini

        Args:
            prompt: Prompt de texto
            system_prompt: Prompt del sistema (opcional)
            temperature: Temperatura para la generación (opcional)
            model: Modelo específico a usar (opcional)
            trace_name: Nombre del trace para Langfuse (opcional)
            user_id: ID del usuario para Langfuse (opcional)
            session_id: ID de la sesión para Langfuse (opcional)
            game_id: ID del juego para tag en Langfuse (opcional)

        Returns:
            GeminiResponse con la respuesta generada
        """
        # Configurar el modelo
        model_name = model or self.model
        temp = temperature if temperature is not None else self.temperature

        # Crear trace para observabilidad
        trace = self.langfuse.create_trace(
            name=trace_name or f"gemini_text_generation",
            user_id=user_id,
            session_id=session_id,
            metadata={
                "model": model_name,
                "temperature": temp,
                "has_system_prompt": system_prompt is not None,
            },
            tags=["gemini", "text", "generation"],
        )

        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            ),
        )

        # Preparar el contenido
        parts = []

        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)

        # Agregar el prompt principal
        parts.append(prompt)

        try:
            # Medir tiempo de ejecución
            print(f"\n📡 Calling Gemini {model_name} text only...")
            start_time = time.time()

            # Generar contenido
            response = model_instance.generate_content(parts)

            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            print(f"✅ Gemini {model_name} text response received in {duration_ms}ms")

            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(
                    response.usage_metadata, "prompt_token_count", 0
                ),
                "completion_tokens": getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ),
                "total_tokens": getattr(
                    response.usage_metadata, "total_token_count", 0
                ),
            }

            # Track en Langfuse
            self.langfuse.track_gemini_call(
                trace_id=trace.trace_id,
                model=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                response=response.text,
                usage=usage,
                start_time=start_time,
                end_time=end_time,
                temperature=temp,
                has_images=False,
                game_id=game_id,
            )

            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=(
                    getattr(response.candidates[0], "finish_reason", "STOP")
                    if response.candidates
                    else "STOP"
                ),
                duration_ms=duration_ms,
            )

            return gemini_response

        except Exception as error:
            print(f"Error llamando a la API de Gemini: {error}")
            raise Exception(f"Error de la API de Gemini: {str(error)}")
