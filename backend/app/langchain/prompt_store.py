"""Load versioned Markdown prompt templates from the project prompt registry."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DEFAULT_PROMPT_DIRECTORY = Path(__file__).resolve().parents[3] / "prompts"
_DEFAULT_MASTER_PROMPT = _DEFAULT_PROMPT_DIRECTORY / "oncology_ai_master_prompt.md"
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)
_VALID_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")


class PromptDocumentError(RuntimeError):
    """Raised when the prompt registry is absent or malformed."""


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    version: str
    purpose: str
    template: str
    path: Path


def _parse_prompt(path: Path) -> PromptDefinition:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PromptDocumentError(f"Could not read prompt file: {path}") from error
    match = _FRONTMATTER.match(raw)
    if not match:
        raise PromptDocumentError(f"Prompt file requires YAML-style frontmatter: {path}")
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise PromptDocumentError(f"Invalid prompt metadata in {path}: {line}")
        metadata[key.strip()] = value.strip().strip('"\'')
    prompt_id = metadata.get("prompt_id", "")
    version = metadata.get("version", "")
    purpose = metadata.get("purpose", "")
    template = match.group(2).strip()
    if not _VALID_ID.fullmatch(prompt_id) or not version or not purpose or not template:
        raise PromptDocumentError(f"Incomplete prompt metadata or body: {path}")
    return PromptDefinition(prompt_id, version, purpose, template, path)


def _parse_master_prompt(path: Path) -> dict[str, PromptDefinition]:
    raw = path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ([A-Z][A-Z0-9_]*)\s*$", raw)
    registry: dict[str, PromptDefinition] = {}
    for index in range(1, len(sections), 2):
        prompt_id = sections[index]
        body = sections[index + 1].strip()
        lines = body.splitlines()
        metadata: dict[str, str] = {}
        while lines and (not lines[0].strip() or ":" in lines[0] and not lines[0].startswith(("Return", "Repair"))):
            line = lines.pop(0)
            key, separator, value = line.partition(":")
            if separator and key.strip() in {"version", "purpose"}:
                metadata[key.strip()] = value.strip()
            elif line.strip():
                lines.insert(0, line)
                break
        template = "\n".join(lines).strip()
        if not metadata.get("version") or not metadata.get("purpose") or not template:
            raise PromptDocumentError(f"Incomplete master prompt section: {prompt_id}")
        if prompt_id in registry:
            raise PromptDocumentError(f"Duplicate prompt ID: {prompt_id}")
        registry[prompt_id] = PromptDefinition(prompt_id, metadata["version"], metadata["purpose"], template, path)
    if not registry:
        raise PromptDocumentError(f"No prompt sections found in {path}")
    return registry


@lru_cache(maxsize=4)
def load_prompt_registry(path: str | None = None) -> dict[str, PromptDefinition]:
    """Return a stable prompt-ID registry assembled from Markdown files."""
    configured = path or os.getenv("ONCOLOGY_PROMPT_DIRECTORY")
    if configured is None and _DEFAULT_MASTER_PROMPT.is_file():
        return _parse_master_prompt(_DEFAULT_MASTER_PROMPT)
    directory = Path(configured or _DEFAULT_PROMPT_DIRECTORY)
    if not directory.is_dir():
        raise PromptDocumentError(f"Prompt directory not found: {directory}")
    registry: dict[str, PromptDefinition] = {}
    for prompt_path in sorted(path for path in directory.rglob("*.md") if path.name.lower() != "readme.md"):
        definition = _parse_prompt(prompt_path)
        if definition.prompt_id in registry:
            raise PromptDocumentError(f"Duplicate prompt ID: {definition.prompt_id}")
        registry[definition.prompt_id] = definition
    if not registry:
        raise PromptDocumentError(f"No usable Markdown prompts found in {directory}")
    return registry


def load_prompt_document(path: str | None = None) -> dict[str, str]:
    """Backward-compatible template view; Markdown is the sole runtime source."""
    return {key: value.template for key, value in load_prompt_registry(path).items()}


def prompt_metadata(prompt_id: str) -> dict[str, str]:
    try:
        prompt = load_prompt_registry()[prompt_id]
    except KeyError as error:
        raise PromptDocumentError(f"Prompt ID not found: {prompt_id}") from error
    return {"prompt_id": prompt.prompt_id, "version": prompt.version, "purpose": prompt.purpose}


def prompt_template(prompt_id: str, **values: object) -> str:
    """Load and format one prompt template, failing clearly on bad placeholders."""
    try:
        template = load_prompt_registry()[prompt_id].template
    except KeyError as error:
        raise PromptDocumentError(f"Prompt ID not found: {prompt_id}") from error
    try:
        return template.format(**values)
    except KeyError as error:
        raise PromptDocumentError(
            f"Missing value {error.args[0]!r} for prompt ID {prompt_id}"
        ) from error
