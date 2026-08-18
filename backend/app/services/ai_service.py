"""
services/ai_service.py — Gemini LLM integration

Talks to Google's Gemini API via the official google-genai SDK.
All LLM logic lives here so swapping models later means changing one file.

Role mapping note:
    Our database stores role="user" and role="assistant".
    Gemini expects role="user" and role="model" (not "assistant").
    We translate on the way out.
"""

import logging

from google import genai
from google.genai import errors as genai_errors, types

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exception — routes catch this, not raw SDK errors
# ---------------------------------------------------------------------------

class AIServiceError(Exception):
    """Raised when the upstream AI service fails.

    Attributes:
        detail: Human-readable error description for the API response.
        status_code: Suggested HTTP status code (default 502 Bad Gateway).
    """

    def __init__(self, detail: str = "AI service unavailable.", status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = (
    "You are Cortex, a helpful AI search assistant. "
    "You provide clear, accurate, and well-structured answers. "
    "When you don't know something, you say so honestly."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_reply(conversation_history: list[dict]) -> str:
    """Send the full conversation history to Gemini and return the reply text.

    Args:
        conversation_history: List of dicts with keys "role" and "content".
            Roles should be "user" or "assistant" (our DB format).

    Returns:
        The model's text reply.

    Raises:
        AIServiceError: If the Gemini API call fails for any reason.
    """
    # --- Map our message format → Gemini's expected format ---
    # Gemini uses role="model" where we use role="assistant".
    # Each message becomes a Content object with a single text Part.
    gemini_contents = []
    for msg in conversation_history:
        gemini_role = "model" if msg["role"] == "assistant" else msg["role"]
        gemini_contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part(text=msg["content"])],
            )
        )

    # --- Call the Gemini API ---
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )

        # Extract text — response.text is a convenience property
        if response.text is None:
            raise AIServiceError(
                detail="AI returned an empty response.",
                status_code=502,
            )

        return response.text

    except AIServiceError:
        # Don't re-wrap our own exceptions
        raise

    except genai_errors.ClientError as exc:
        # 4xx from Gemini — bad key, rate limit, invalid request
        logger.error("Gemini client error: %s", exc)
        raise AIServiceError(
            detail="AI service request failed (client error).",
            status_code=502,
        ) from exc

    except genai_errors.ServerError as exc:
        # 5xx from Gemini — their infra is down
        logger.error("Gemini server error: %s", exc)
        raise AIServiceError(
            detail="AI service is temporarily unavailable.",
            status_code=502,
        ) from exc

    except Exception as exc:
        # Catch-all: network errors, unexpected SDK issues, etc.
        logger.error("Unexpected error calling Gemini: %s", exc, exc_info=True)
        raise AIServiceError(
            detail="AI service encountered an unexpected error.",
            status_code=502,
        ) from exc
