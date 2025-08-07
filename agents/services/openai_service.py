import os
import base64
import time
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from PIL import Image
import io

from openai import OpenAI

# Disable OpenAI HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class OpenAIImageData:
    """Image data for sending to OpenAI"""

    data: bytes
    mime_type: str


@dataclass
class OpenAIResponse:
    """OpenAI service response"""

    content: str
    usage: Dict[str, int]
    model: str
    finish_reason: str
    duration_ms: int


class OpenAIService:
    """Service for interacting with OpenAI API"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-5"):
        """
        Initialize the OpenAI service

        Args:
            api_key: OpenAI API key (if not provided, the environment variable is used)
            model: Model to use by default
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.temperature = 0.7
        self.max_output_tokens = 1024  # Reduced for faster GPT-5 responses

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable or api_key parameter is required"
            )

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)

    def generate_text_sync(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> OpenAIResponse:
        """
        Generate text using OpenAI API

        Args:
            prompt: The prompt to send to the model
            temperature: Temperature for generation (overrides instance default)
            max_tokens: Maximum tokens to generate (overrides instance default)
            model: Model to use (overrides instance default)
            system_prompt: Optional system prompt

        Returns:
            OpenAIResponse with the generated content
        """
        start_time = time.time()

        # Use provided values or fall back to instance defaults
        temp = temperature if temperature is not None else self.temperature
        max_toks = max_tokens if max_tokens is not None else self.max_output_tokens
        model_name = model if model is not None else self.model

        # GPT-5 only supports temperature=1
        if model_name.startswith("gpt-5") and temp != 1.0:
            temp = 1.0

        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Make the API call
            print(f"\n📡 Calling OpenAI {model_name}...")

            # Use max_completion_tokens for newer models, max_tokens for older ones
            api_params = {
                "model": model_name,
                "messages": messages,
                "temperature": temp,
            }

            # Check if model supports max_completion_tokens or max_tokens
            if (
                model_name.startswith("gpt-5")
                or "o1" in model_name
                or "reasoning" in model_name
            ):
                api_params["max_completion_tokens"] = max_toks
            else:
                api_params["max_tokens"] = max_toks

            # Use Responses API for GPT-5, Chat Completions for older models
            if model_name.startswith("gpt-5"):
                # Convert to Responses API format
                input_content = prompt
                if system_prompt:
                    input_content = f"System: {system_prompt}\n\nUser: {prompt}"

                responses_params = {
                    "model": model_name,
                    "input": input_content,
                    "temperature": temp,
                    "reasoning_effort": "minimal",  # For faster responses
                    "verbosity": "low",  # For concise responses
                    "max_completion_tokens": max_toks,
                }

                response = self.client.responses.create(**responses_params)
            else:
                response = self.client.chat.completions.create(**api_params)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            print(f"✅ OpenAI {model_name} response received in {duration_ms}ms")

            # Extract response data (different structure for Responses API vs Chat Completions)
            if model_name.startswith("gpt-5"):
                # Responses API structure
                content = (
                    response.output.content
                    if hasattr(response.output, "content")
                    else response.output
                )
                finish_reason = (
                    response.finish_reason
                    if hasattr(response, "finish_reason")
                    else "stop"
                )
                usage = {
                    "prompt_tokens": (
                        response.usage.input_tokens if hasattr(response, "usage") else 0
                    ),
                    "completion_tokens": (
                        response.usage.output_tokens
                        if hasattr(response, "usage")
                        else 0
                    ),
                    "total_tokens": (
                        response.usage.total_tokens if hasattr(response, "usage") else 0
                    ),
                }
            else:
                # Chat Completions API structure
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return OpenAIResponse(
                content=content,
                usage=usage,
                model=response.model,
                finish_reason=finish_reason,
                duration_ms=duration_ms,
            )

        except Exception as e:
            print(f"L Error in OpenAI API call: {e}")
            # Return a fallback response
            return OpenAIResponse(
                content=f"Error: {str(e)}",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                model=model_name,
                finish_reason="error",
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def generate_with_images_sync(
        self,
        prompt: str,
        images: List[Image.Image],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> OpenAIResponse:
        """
        Generate text using OpenAI API with images

        Args:
            prompt: The prompt to send to the model
            images: List of PIL Images to include
            temperature: Temperature for generation (overrides instance default)
            max_tokens: Maximum tokens to generate (overrides instance default)
            model: Model to use (overrides instance default)
            system_prompt: Optional system prompt

        Returns:
            OpenAIResponse with the generated content
        """
        start_time = time.time()

        # Use provided values or fall back to instance defaults
        temp = temperature if temperature is not None else self.temperature
        max_toks = max_tokens if max_tokens is not None else self.max_output_tokens
        model_name = model if model is not None else self.model

        # GPT-5 only supports temperature=1
        if model_name.startswith("gpt-5") and temp != 1.0:
            temp = 1.0

        try:
            # Convert images to base64
            image_data_list = []
            for img in images:
                img_data = self._image_to_openai_format(img)
                image_data_list.append(img_data)

            # Build messages with images
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Build user message with text and images
            user_content = [{"type": "text", "text": prompt}]

            for img_data in image_data_list:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{img_data.mime_type};base64,{base64.b64encode(img_data.data).decode()}",
                            "detail": "high",  # For detailed analysis of images
                        },
                    }
                )

            messages.append({"role": "user", "content": user_content})

            # Make the API call
            print(f"\n📡 Calling OpenAI {model_name} with images...")

            # Use max_completion_tokens for newer models, max_tokens for older ones
            api_params = {
                "model": model_name,
                "messages": messages,
                "temperature": temp,
            }

            # Check if model supports max_completion_tokens or max_tokens
            if (
                model_name.startswith("gpt-5")
                or "o1" in model_name
                or "reasoning" in model_name
            ):
                api_params["max_completion_tokens"] = max_toks
            else:
                api_params["max_tokens"] = max_toks

            # Use Responses API for GPT-5, Chat Completions for older models
            if model_name.startswith("gpt-5"):
                # For vision, we need to convert to Responses API format
                # This is more complex with images, may need different approach
                # response = self.client.chat.completions.create(
                response = self.client.responses.create(
                    model=model_name, input="quien eres?"
                )  # Fallback to old API for images
            else:
                response = self.client.chat.completions.create(**api_params)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            print(f"✅ OpenAI {model_name} vision response received in {duration_ms}ms")

            # Extract response data (using Chat Completions structure for images for now)
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            return OpenAIResponse(
                content=content,
                usage=usage,
                model=response.model,
                finish_reason=finish_reason,
                duration_ms=duration_ms,
            )

        except Exception as e:
            print(f"L Error in OpenAI vision API call: {e}")
            # Return a fallback response
            return OpenAIResponse(
                content=f"Error: {str(e)}",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                model=model_name,
                finish_reason="error",
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _image_to_openai_format(self, image: Image.Image) -> OpenAIImageData:
        """
        Convert PIL Image to OpenAI format

        Args:
            image: PIL Image object

        Returns:
            OpenAIImageData with image bytes and mime type
        """
        try:
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Optimize image size if too large (OpenAI recommends max 20MB, optimal < 2048x2048)
            max_size = 2048
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                print(f"🖼️ Resized image to {new_size} for OpenAI")

            # Use JPEG for better compression on larger images, PNG for smaller/simple images
            img_buffer = io.BytesIO()

            # Determine format based on image characteristics
            if image.size[0] * image.size[1] > 512 * 512:  # Large image, use JPEG
                image.save(img_buffer, format="JPEG", quality=85, optimize=True)
                mime_type = "image/jpeg"
            else:  # Small image, use PNG for better quality
                image.save(img_buffer, format="PNG", optimize=True)
                mime_type = "image/png"

            img_bytes = img_buffer.getvalue()

            # Check size limit (OpenAI has a 20MB limit)
            size_mb = len(img_bytes) / (1024 * 1024)
            if size_mb > 20:
                print(
                    f"⚠️ Image size ({size_mb:.1f}MB) exceeds OpenAI limit, compressing..."
                )
                # Retry with more aggressive compression
                img_buffer = io.BytesIO()
                image.save(img_buffer, format="JPEG", quality=60, optimize=True)
                img_bytes = img_buffer.getvalue()
                mime_type = "image/jpeg"

            return OpenAIImageData(data=img_bytes, mime_type=mime_type)

        except Exception as e:
            print(f"L Error converting image for OpenAI: {e}")
            raise

    def get_available_models(self) -> List[str]:
        """
        Get list of available models

        Returns:
            List of available model names
        """
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            print(f"L Error getting available models: {e}")
            return ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo"]

    def set_model(self, model: str):
        """Set the default model to use"""
        self.model = model

    def set_temperature(self, temperature: float):
        """Set the default temperature"""
        self.temperature = temperature

    def set_max_tokens(self, max_tokens: int):
        """Set the default max tokens"""
        self.max_output_tokens = max_tokens
