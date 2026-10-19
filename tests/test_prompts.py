"""Unit tests for prompt templates and placeholder validation."""

import pytest

from chatbot.prompts import (
    get_default_response_schema,
    load_template,
    render_repair_prompt,
    render_system_prompt,
)


def test_template_loading() -> None:
    sys_tmpl = load_template("system_v1.md")
    assert "{assistant_name}" in sys_tmpl
    assert "{domain_focus}" in sys_tmpl
    assert "{json_schema}" in sys_tmpl

    repair_tmpl = load_template("repair_v1.md")
    assert "{validation_errors}" in repair_tmpl
    assert "{json_schema}" in repair_tmpl

    with pytest.raises(FileNotFoundError):
        load_template("non_existent_template.md")


def test_render_system_prompt_success() -> None:
    prompt = render_system_prompt(
        assistant_name="CustomBot",
        domain_focus="Distributed Systems",
    )
    assert "CustomBot" in prompt
    assert "Distributed Systems" in prompt
    assert "StructuredReply" in prompt
    assert "{assistant_name}" not in prompt
    assert "{domain_focus}" not in prompt
    assert "{json_schema}" not in prompt


def test_render_system_prompt_empty_args() -> None:
    with pytest.raises(ValueError, match="assistant_name"):
        render_system_prompt(assistant_name="")

    with pytest.raises(ValueError, match="domain_focus"):
        render_system_prompt(domain_focus="   ")


def test_render_repair_prompt_success() -> None:
    repair_prompt = render_repair_prompt(
        validation_errors="Field 'category' must be one of: general, technical, refusal"
    )
    assert "validation_errors" in repair_prompt
    assert "Field 'category' must be one of" in repair_prompt
    assert "{validation_errors}" not in repair_prompt
    assert "{json_schema}" not in repair_prompt


def test_render_repair_prompt_empty_errors() -> None:
    with pytest.raises(ValueError, match="validation_errors"):
        render_repair_prompt(validation_errors="")


def test_default_schema_generation() -> None:
    schema_str = get_default_response_schema()
    assert "answer" in schema_str
    assert "category" in schema_str
    assert "key_points" in schema_str
    assert "follow_up_questions" in schema_str
    assert "confidence" in schema_str
