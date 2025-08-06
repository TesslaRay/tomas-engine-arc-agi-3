import os
import time
from typing import Optional, Dict
from dataclasses import dataclass

import requests


@dataclass
class CerebrasResponse:
    """Cerebras response"""

    content: str
    usage: Dict[str, int]
    model: str
    finish_reason: str
    duration_ms: int


class CerebrasService:
    """Cerebras service using OpenRouter API"""

    # Available models
    AVAILABLE_MODELS = [
        "openai/gpt-oss-120b",
        "qwen/qwen3-235b-a22b-thinking-2507",
        "qwen/qwen3-coder",
        "qwen/qwen3-235b-a22b-2507",
        "qwen/qwen3-32b",
        "meta-llama/llama-4-maverick",
        "meta-llama/llama-4-scout",
        "deepseek/deepseek-r1-distill-llama-70b",
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3.2-11b-instruct",
    ]

    def __init__(
        self, api_key: Optional[str] = None, model: str = "meta-llama/llama-4-maverick"
    ):
        """
        Initialize the Cerebras service

        Args:
            api_key: OpenRouter API key (if not provided, the environment variable is used)
            model: Model to use by default
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.temperature = 0.7
        self.max_output_tokens = 4096
        self.base_url = "https://openrouter.ai/api/v1"

        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required as an environment variable or parameter"
            )

        print(f"✅ Cerebras service initialized with model: {self.model}")

    def is_available(self) -> bool:
        """Check if the service is available"""
        return bool(self.api_key)

    @classmethod
    def get_available_models(cls) -> list[str]:
        """Get list of available models"""
        return cls.AVAILABLE_MODELS.copy()

    def validate_model(self, model: str) -> bool:
        """Validate if model is in available models list"""
        return model in self.AVAILABLE_MODELS

    def generate_text_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> CerebrasResponse:
        """
        Generate text without images

        Args:
            prompt: Text prompt
            system_prompt: System prompt (optional)
            temperature: Temperature for generation (optional)
            model: Specific model to use (optional)

        Returns:
            CerebrasResponse with the generated response
        """
        # Configure parameters
        model_name = model or self.model
        temp = temperature if temperature is not None else self.temperature

        # Prepare messages
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Prepare payload
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
            "max_tokens": self.max_output_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://arc-agi-3-agents.com",
            "X-Title": "ARC AGI 3 Agents",
            "Content-Type": "application/json",
        }

        try:
            start_time = time.time()

            print(f"🧠 Sending text request to Cerebras ({model_name})...")

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )

            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            if not response.ok:
                error_text = response.text
                raise Exception(
                    f"OpenRouter API error: {response.status_code} - {error_text}"
                )

            response_data = response.json()

            content = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            finish_reason = response_data.get("choices", [{}])[0].get(
                "finish_reason", "stop"
            )

            usage_data = response_data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }

            print(f"✅ Cerebras text response received ({duration_ms}ms)")

            return CerebrasResponse(
                content=content,
                usage=usage,
                model=model_name,
                finish_reason=finish_reason,
                duration_ms=duration_ms,
            )

        except Exception as error:
            print(f"❌ Error calling the Cerebras API: {error}")
            raise Exception(f"Error calling the Cerebras API: {str(error)}")
