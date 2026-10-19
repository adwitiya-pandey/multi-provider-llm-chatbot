"""AST boundary tests enforcing SDK isolation and banning third-party wrappers (SPEC 9, S2)."""

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
TESTS_DIR = Path(__file__).resolve().parent.parent / "tests"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

DIRECT_SDKS = {"google.genai", "anthropic", "openai"}
BANNED_FRAMEWORKS = {"langchain", "llama_index", "litellm"}


def _get_all_imports(file_path: Path) -> set[str]:
    """Parses Python file AST and extracts all imported module names."""
    imports = set()
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_no_banned_frameworks_anywhere() -> None:
    """Verifies no LangChain, LlamaIndex, or LiteLLM wrappers exist in the repository."""
    for directory in (SRC_DIR, TESTS_DIR, SCRIPTS_DIR):
        if not directory.exists():
            continue
        for py_file in directory.rglob("*.py"):
            file_imports = _get_all_imports(py_file)
            for imp in file_imports:
                root_module = imp.split(".")[0]
                assert root_module not in BANNED_FRAMEWORKS, (
                    f"Banned framework '{root_module}' imported in {py_file}!"
                )


def test_provider_sdks_isolated_to_providers_py() -> None:
    """Verifies that direct SDKs are ONLY imported in providers.py."""
    providers_py = (SRC_DIR / "chatbot" / "providers.py").resolve()

    for py_file in SRC_DIR.rglob("*.py"):
        resolved = py_file.resolve()
        if resolved == providers_py:
            continue

        file_imports = _get_all_imports(py_file)
        for imp in file_imports:
            # Check if import matches or starts with direct SDK names
            for sdk in DIRECT_SDKS:
                assert not (imp == sdk or imp.startswith(f"{sdk}.")), (
                    f"Direct SDK '{sdk}' illegally imported in {py_file}! "
                    f"All provider SDKs must be isolated strictly to providers.py."
                )
