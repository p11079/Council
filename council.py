from __future__ import annotations

import os
import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


Category = Literal["Career", "Education", "Money", "Relationships", "Other"]


class Perspective(BaseModel):
    summary: str = Field(min_length=1)
    advice: str = Field(min_length=1)
    risk_note: str = Field(min_length=1)


class CouncilResponse(BaseModel):
    logic: Perspective
    risk: Perspective
    human: Perspective
    growth: Perspective
    verdict: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    caution_note: str | None = None
    clarifying_question: str | None = None
    is_fallback: bool = False
    error_message: str | None = None


def demo_response(dilemma: str) -> CouncilResponse:
    """Deterministic fallback for local demos and unavailable model APIs."""
    return CouncilResponse(
        logic=Perspective(summary="Separate facts from assumptions.", advice="List options, constraints, and the next reversible step.", risk_note="Missing context can change the recommendation."),
        risk=Perspective(summary="Protect downside before committing.", advice="Set a time limit and a clear exit condition.", risk_note="Avoid irreversible choices under pressure."),
        human=Perspective(summary="Your values and relationships matter.", advice="Notice how each option affects your energy and support network.", risk_note="Do not ignore persistent discomfort."),
        growth=Perspective(summary="Choose the option that teaches you something useful.", advice="Prefer a small experiment when possible.", risk_note="Growth should not require abandoning basic safety."),
        verdict=f"For now, take the smallest reversible step toward resolving: {dilemma[:180]}",
        confidence=0.45,
        caution_note="This is a local fallback preview, not an AI-generated verdict. Verify important decisions with a qualified person.",
        is_fallback=True,
    )


def analyze(dilemma: str, category: Category) -> CouncilResponse:
    if not dilemma.strip():
        raise ValueError("A dilemma is required")
    if len(dilemma.strip()) < 25:
        response = demo_response(dilemma)
        response.confidence = 0.15
        response.clarifying_question = "What options are you weighing, and what outcome matters most to you?"
        response.caution_note = "There is not enough context for a dependable recommendation yet."
        return response
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return demo_response(dilemma)
    from google import genai
    from tenacity import retry, stop_after_attempt, wait_exponential

    client = genai.Client(api_key=api_key)
    prompt = f"""You are Council, a private decision-support assistant. Analyze this {category} dilemma from four opposing perspectives: Logic, Risk, Human, Growth. Do not provide medical, legal, or emergency advice. Be concrete, balanced, and explicit about uncertainty. Dilemma: {dilemma}"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def call(model: str) -> CouncilResponse:
        result = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": CouncilResponse},
        )
        return CouncilResponse.model_validate_json(result.text)

    try:
        return call(os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    except Exception as primary_error:
        logger.exception("Primary Council model failed")
        fallback = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-lite")
        try:
            return call(fallback)
        except Exception:
            logger.exception("Fallback Council model failed", extra={"primary_error": str(primary_error)})
            fallback = demo_response(dilemma)
            fallback.error_message = "Council could not reach the configured model. This preview was not saved to history."
            return fallback
