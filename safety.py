from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyResult:
    is_crisis: bool
    category: str | None = None
    message: str | None = None


HELPLINES = {
    "IN": {"emergency": "112", "suicide": "Tele-MANAS: 14416"},
    "US": {"emergency": "911", "suicide": "988 Suicide & Crisis Lifeline"},
    "GB": {"emergency": "999", "suicide": "Samaritans: 116 123"},
}


def support_for_country(country: str) -> dict[str, str]:
    return HELPLINES.get(country.strip().upper(), {"emergency": "your local emergency number", "suicide": "a local crisis line or trusted person"})


def support_card(country: str, category: str, emergency_contact: str = "") -> dict[str, str]:
    base = support_for_country(country)
    if category == "self-harm":
        return {"title": "Immediate emotional support", "body": f"Call {base['suicide']} now. If you may act soon, call {base['emergency']} and stay with a trusted person."}
    if category == "physical danger":
        return {"title": "Get to safety", "body": f"Call {base['emergency']}. Move to a safer public place and contact someone you trust."}
    contact = f" Your trusted contact is {emergency_contact}." if emergency_contact else ""
    return {"title": "Report and protect yourself", "body": f"Preserve evidence, do not pay or share more information, and report it to local authorities or the relevant platform.{contact}"}


PATTERNS = {
    "self-harm": r"\b(kill myself|hurt myself|suicid\w*|self[- ]harm|end my life|ending it all|want to die|don't want to live|do not want to live|no point in living|wish i could disappear)\b",
    "physical danger": r"\b(being beaten|hits me|hitting me|threatening me|in danger|unsafe at home|stalk(?:ing|ed)|someone may hurt me)\b",
    "cybercrime or extortion": r"\b(ransomware|blackmail(?:ed|ing)?|extort(?:ion|ed|ing)?|stolen password|password (?:was )?stolen)\b",
}


def detect_crisis(text: str) -> SafetyResult:
    lowered = text.lower()
    for category, pattern in PATTERNS.items():
        if re.search(pattern, lowered):
            return SafetyResult(True, category, "Your safety matters more than this app. Contact local emergency services or a trusted person now. If you may act soon, move away from anything dangerous and do not stay alone.")
    return SafetyResult(False)
