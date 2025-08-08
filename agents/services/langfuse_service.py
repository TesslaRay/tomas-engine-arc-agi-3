import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from uuid import uuid4

try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    print("⚠️ Langfuse not installed. Run: pip install langfuse")


@dataclass
class LangfuseTrace:
    """Langfuse trace data"""

    trace_id: str
    generation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class LangfuseService:
    """Simplified Langfuse service for observability"""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        public_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: bool = True,
    ):
        """
        Initialize Langfuse service

        Args:
            secret_key: Langfuse secret key (from env if not provided)
            public_key: Langfuse public key (from env if not provided)
            host: Langfuse host URL (from env if not provided)
            enabled: Whether to enable Langfuse tracking
        """
        self.enabled = enabled and LANGFUSE_AVAILABLE

        if not self.enabled:
            print("🔕 Langfuse observability disabled")
            self.client = None
            return

        # Get credentials from environment or parameters
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.host = "https://us.cloud.langfuse.com"

        if not self.secret_key or not self.public_key:
            print(
                "⚠️ Langfuse credentials not found. Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY"
            )
            self.enabled = False
            self.client = None
            return

        try:
            # Initialize Langfuse client
            self.client = Langfuse(
                secret_key=self.secret_key, public_key=self.public_key, host=self.host
            )

        except Exception as e:
            print(f"❌ Failed to initialize Langfuse: {e}")
            self.enabled = False
            self.client = None

    def is_enabled(self) -> bool:
        """Check if Langfuse is enabled and available"""
        return self.enabled and self.client is not None

    def create_trace(
        self,
        name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> LangfuseTrace:
        """
        Create a new trace for tracking

        Args:
            name: Name of the trace
            user_id: Optional user identifier
            session_id: Optional session identifier
            metadata: Optional metadata dict
            tags: Optional list of tags

        Returns:
            LangfuseTrace object
        """
        trace_id = str(uuid4())

        if not self.is_enabled():
            return LangfuseTrace(trace_id=trace_id)

        try:
            # Using simple trace creation - just return ID for context
            return LangfuseTrace(
                trace_id=trace_id, session_id=session_id, user_id=user_id
            )
        except Exception as e:
            print(f"❌ Error creating Langfuse trace: {e}")
            return LangfuseTrace(trace_id=trace_id)

    def track_gemini_call(
        self,
        trace_id: str,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        response: str,
        usage: Dict[str, int],
        start_time: float,
        end_time: float,
        temperature: float,
        metadata: Optional[Dict[str, Any]] = None,
        has_images: bool = False,
        game_id: Optional[str] = None,
        nuclei: Optional[str] = None,
    ) -> Optional[str]:
        """
        Track a Gemini API call using Langfuse v3 API
        """
        if not self.is_enabled():
            return None

        try:
            from datetime import datetime

            duration_ms = int((end_time - start_time) * 1000)

            # Prepare tags
            tags = []

            if has_images:
                tags.append("vision")
            else:
                tags.append("text")

            if game_id:
                tags.append(f"game:{game_id}")
            if nuclei:
                tags.append(f"{nuclei}")

            # Usar OpenTelemetry directamente para timestamps reales
            from opentelemetry import trace

            tracer = trace.get_tracer(__name__)

            # Crear span con timestamps reales
            with tracer.start_as_current_span(
                name=f"gemini_{model}" + ("_vision" if has_images else "_text"),
                start_time=int(start_time * 1_000_000_000),  # nanoseconds
                end_on_exit=False,
            ) as otel_span:
                # Set attributes para Langfuse
                otel_span.set_attribute("gen_ai.request.model", model)
                otel_span.set_attribute("gen_ai.request.temperature", temperature)
                otel_span.set_attribute(
                    "gen_ai.usage.prompt_tokens", usage.get("prompt_tokens", 0)
                )
                otel_span.set_attribute(
                    "gen_ai.usage.completion_tokens", usage.get("completion_tokens", 0)
                )
                otel_span.set_attribute(
                    "gen_ai.usage.total_tokens", usage.get("total_tokens", 0)
                )
                otel_span.set_attribute("langfuse.tags", tags)
                otel_span.set_attribute("game_id", game_id or "")

                # Terminar con timestamp real
                otel_span.end(int(end_time * 1_000_000_000))

            # Flush para asegurar que se envíe inmediatamente
            self.client.flush()

            print(
                f"📊 Tracked Gemini call in Langfuse (latency: {duration_ms}ms, game: {game_id or 'N/A'})"
            )
            return trace_id

        except Exception as e:
            print(f"❌ Error tracking in Langfuse: {e}")
            return None

    def flush(self):
        """Flush any pending data to Langfuse"""
        if self.is_enabled():
            try:
                self.client.flush()
            except Exception as e:
                print(f"❌ Error flushing Langfuse data: {e}")

    def shutdown(self):
        """Shutdown Langfuse client"""
        if self.is_enabled():
            try:
                self.client.flush()
                print("📊 Langfuse observability shutdown")
            except Exception as e:
                print(f"❌ Error shutting down Langfuse: {e}")
