"""Automated verification test ensuring the README file tree matches git-tracked files."""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"


def _get_tree_text_from_readme() -> str:
    content = README_PATH.read_text(encoding="utf-8")
    match = re.search(r"## Repository Structure\s+```(?:text)?\n(.*?)\n```", content, re.DOTALL)
    assert match, "Could not find '## Repository Structure' code block in README.md"
    return match.group(1)


def _get_git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_readme_tree_files_exist_on_disk() -> None:
    tree_text = _get_tree_text_from_readme()
    # Extract file basenames from tree lines (e.g. "├── app.py # Streamlit ...")
    lines = tree_text.splitlines()
    for line in lines:
        cleaned = re.sub(r"^[│├└──\s]+", "", line).strip()
        if not cleaned or cleaned.startswith("multi-provider-llm-chatbot"):
            continue
        # Split off comment if present
        part = cleaned.split("#")[0].strip()
        if not part or part.endswith("/"):
            continue
        # Match filename
        filename = Path(part).name
        # Find if this file exists anywhere under REPO_ROOT
        matches = list(REPO_ROOT.rglob(filename))
        assert matches, f"File '{filename}' listed in README tree does not exist on disk!"


def test_all_core_tracked_files_present_in_readme_tree() -> None:
    tree_text = _get_tree_text_from_readme()
    tracked = _get_git_tracked_files()

    # Verify that all tracked python files in src/, scripts/, tests/ and files in prompts/, docs/
    # are mentioned in the README tree
    for rel_path in tracked:
        p = Path(rel_path)
        prefixes = ("src/", "scripts/", "tests/", "prompts/", "docs/")
        if p.suffix in (".py", ".md") and any(rel_path.startswith(prefix) for prefix in prefixes):
            err_msg = f"Tracked file '{rel_path}' is missing from README repository tree!"
            assert p.name in tree_text, err_msg
