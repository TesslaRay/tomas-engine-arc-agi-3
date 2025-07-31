import os
import base64
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from PIL import Image
import io

import google.generativeai as genai


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
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-pro"):
        """
        Inicializar el servicio Gemini
        
        Args:
            api_key: Clave API de Google (si no se proporciona, se usa la variable de entorno)
            model: Modelo a utilizar por defecto
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.temperature = 0.7
        self.max_output_tokens = 65000
        
        if not self.api_key:
            raise ValueError("Se requiere GEMINI_API_KEY como variable de entorno o parámetro")
        
        # Configurar la API de Gemini
        genai.configure(api_key=self.api_key)
    
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
        pil_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        return GeminiImageData(
            data=img_byte_arr,
            mime_type="image/png"
        )
    
    def _prepare_image_from_path(self, image_path: str) -> GeminiImageData:
        """
        Cargar imagen desde archivo
        
        Args:
            image_path: Ruta al archivo de imagen
            
        Returns:
            GeminiImageData con los datos de la imagen
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Determinar el tipo MIME basado en la extensión
        if image_path.lower().endswith('.png'):
            mime_type = "image/png"
        elif image_path.lower().endswith(('.jpg', '.jpeg')):
            mime_type = "image/jpeg"
        elif image_path.lower().endswith('.gif'):
            mime_type = "image/gif"
        elif image_path.lower().endswith('.webp'):
            mime_type = "image/webp"
        else:
            mime_type = "image/png"  # Por defecto
        
        return GeminiImageData(
            data=image_data,
            mime_type=mime_type
        )
    
    async def generate_with_image(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        image_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None
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
        
        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            )
        )
        
        # Preparar el contenido
        parts = []
        
        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)
        
        # Agregar el prompt principal
        parts.append(prompt)
        
        # Agregar la imagen
        parts.append({
            "mime_type": image_data.mime_type,
            "data": image_data.data
        })
        
        try:
            # Medir tiempo de ejecución
            start_time = time.time()
            
            # Generar contenido
            response = await model_instance.generate_content_async(parts)
            
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
            }
            
            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=getattr(response.candidates[0], 'finish_reason', 'STOP') if response.candidates else 'STOP',
                duration_ms=duration_ms
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
        model: Optional[str] = None
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
        
        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            )
        )
        
        # Preparar el contenido
        parts = []
        
        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)
        
        # Agregar el prompt principal
        parts.append(prompt)
        
        # Agregar todas las imágenes
        for i, image_data in enumerate(image_data_list):
            parts.append({
                "mime_type": image_data.mime_type,
                "data": image_data.data
            })
        
        try:
            # Medir tiempo de ejecución
            start_time = time.time()
            
            # Generar contenido
            response = model_instance.generate_content(parts)
            
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
            }
            
            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=getattr(response.candidates[0], 'finish_reason', 'STOP') if response.candidates else 'STOP',
                duration_ms=duration_ms
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
        model: Optional[str] = None
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
        
        model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=temp,
                max_output_tokens=self.max_output_tokens,
            )
        )
        
        # Preparar el contenido
        parts = []
        
        # Agregar system prompt si se proporciona
        if system_prompt:
            parts.append(system_prompt)
        
        # Agregar el prompt principal
        parts.append(prompt)
        
        # Agregar la imagen
        parts.append({
            "mime_type": image_data.mime_type,
            "data": image_data.data
        })
        
        try:
            # Medir tiempo de ejecución
            start_time = time.time()
            
            # Generar contenido
            response = model_instance.generate_content(parts)
            
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            # Extraer información de uso
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
            }
            
            # Preparar respuesta
            gemini_response = GeminiResponse(
                content=response.text,
                usage=usage,
                model=model_name,
                finish_reason=getattr(response.candidates[0], 'finish_reason', 'STOP') if response.candidates else 'STOP',
                duration_ms=duration_ms
            )
            
            return gemini_response
            
        except Exception as error:
            print(f"Error llamando a la API de Gemini: {error}")
            raise Exception(f"Error de la API de Gemini: {str(error)}")


# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo básico
    service = GeminiService()
    
    # Ejemplo con imagen desde archivo
    try:
        response = service.generate_with_image_sync(
            prompt="¿Qué ves en esta imagen?",
            image_path="ruta/a/imagen.png",
            system_prompt="Eres un asistente experto en análisis de imágenes."
        )
        print(f"Respuesta: {response.content}")
        print(f"Tokens usados: {response.usage}")
        print(f"Tiempo: {response.duration_ms}ms")
    except Exception as e:
        print(f"Error: {e}")