"""Input sanitization, control character stripping, and prompt injection detection."""

import re
from dataclasses import dataclass

MAX_INPUT_LENGTH = 4000

# Regex patterns for prompt injection attempts (case-insensitive)
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|directions|rules)",
    r"forget\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules)",
    r"reveal\s+(?:your\s+|the\s+)?(?:system\s+prompt|system\s+instructions|rules|instructions)",
    r"show\s+(?:your\s+|the\s+)?(?:system\s+prompt|system\s+instructions|rules|initial\s+instructions)",
    r"what\s+(?:is|are)\s+your\s+(?:system\s+prompt|initial\s+instructions|system\s+instructions|secret\s+rules)",
    r"print\s+(?:your\s+|the\s+)?(?:system\s+prompt|system\s+instructions|instructions|initial\s+instructions)",
    r"output\s+(?:your\s+|the\s+)?(?:initial\s+instructions|system\s+prompt|system\s+instructions)",
    r"bypass\s+(?:safety|content|all)\s+filters",
    r"(?:jailbreak|dan\s+mode|developer\s+mode)",
    r"you\s+are\s+now\s+(?:an\s+unrestricted|in\s+developer\s+mode|dan)",
    r"act\s+as\s+an\s+unrestricted",
    r"override\s+previous\s+(?:instructions|rules)",
    r"</user_message>",
]

_COMPILED_INJECTION_REGEXES = [re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS]


@dataclass(frozen=True)
class SanitizeResult:
    """Outcome of input sanitization."""

    clean_text: str
    wrapped_text: str
    is_injection: bool
    detected_pattern: str | None = None


def strip_control_characters(text: str) -> str:
    """Strips ASCII control characters except newline, tab, and carriage return."""
    clean_chars: list[str] = []
    for ch in text:
        code = ord(ch)
        # Keep newline (\n=10), tab (\t=9), carriage return (\r=13)
        if code in (9, 10, 13) or (code >= 32 and code != 127):
            clean_chars.append(ch)
    return "".join(clean_chars)


def check_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Scans text for known prompt injection signatures."""
    for pattern, regex in zip(INJECTION_PATTERNS, _COMPILED_INJECTION_REGEXES, strict=False):
        if regex.search(text):
            return True, pattern
    return False, None


def sanitize_input(raw_text: str) -> SanitizeResult:
    """Sanitizes raw user input:

    1. Strips harmful control characters.
    2. Capping at 4,000 characters.
    3. Scans for prompt injection attacks.
    4. Wraps clean text in <user_message> tags.
    """
    stripped = strip_control_characters(raw_text)
    capped = stripped[:MAX_INPUT_LENGTH].strip()
    is_injection, detected_pattern = check_prompt_injection(capped)
    wrapped = f"<user_message>\n{capped}\n</user_message>"

    return SanitizeResult(
        clean_text=capped,
        wrapped_text=wrapped,
        is_injection=is_injection,
        detected_pattern=detected_pattern,
    )
