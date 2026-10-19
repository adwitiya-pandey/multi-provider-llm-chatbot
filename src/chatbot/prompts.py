"""File-based prompt template loader with placeholder validation."""

import json
from pathlib import Path

from chatbot.models import StructuredReply

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def get_default_response_schema() -> str:
    """Returns the formatted JSON schema string for StructuredReply."""
    return json.dumps(StructuredReply.model_json_schema(), indent=2)


def load_template(filename: str) -> str:
    """Loads a prompt template markdown file from the prompts directory."""
    path = PROMPTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_system_prompt(
    assistant_name: str = "OmniBot",
    domain_focus: str = "General AI & Data Engineering",
    custom_schema: str | None = None,
) -> str:
    """Renders the system prompt from prompts/system_v1.md with validated variables."""
    if not assistant_name.strip():
        raise ValueError("assistant_name must not be empty")
    if not domain_focus.strip():
        raise ValueError("domain_focus must not be empty")

    template = load_template("system_v1.md")
    schema_str = custom_schema or get_default_response_schema()

    rendered = template.replace("{assistant_name}", assistant_name)
    rendered = rendered.replace("{domain_focus}", domain_focus)
    rendered = rendered.replace("{json_schema}", schema_str)

    # Validate that placeholders were replaced
    for placeholder in ("{assistant_name}", "{domain_focus}", "{json_schema}"):
        if placeholder in rendered:
            raise ValueError(f"Unreplaced template placeholder: {placeholder}")

    return rendered


def render_repair_prompt(
    validation_errors: str,
    custom_schema: str | None = None,
) -> str:
    """Renders the repair prompt from prompts/repair_v1.md."""
    if not validation_errors.strip():
        raise ValueError("validation_errors must not be empty")

    template = load_template("repair_v1.md")
    schema_str = custom_schema or get_default_response_schema()

    rendered = template.replace("{validation_errors}", validation_errors)
    rendered = rendered.replace("{json_schema}", schema_str)

    for placeholder in ("{validation_errors}", "{json_schema}"):
        if placeholder in rendered:
            raise ValueError(f"Unreplaced template placeholder: {placeholder}")

    return rendered
