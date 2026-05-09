#!/usr/bin/env python3
"""Lightweight lint checks for the LLM Wiki vault."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DEFAULT_VAULT = Path("/mnt/d/ACobsidianVault/WiKi")
EXCLUDED_DIRS = {".obsidian", ".trash", ".git", "node_modules", ".cache"}
WIKI_LINK = re.compile(r"\[\[([^\]|#]+)")
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")


def is_note(path: Path, root: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return not any(part in EXCLUDED_DIRS for part in rel.parts)


def iter_notes(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if is_note(path, root))


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def frontmatter(text: str) -> dict[str, object] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return None
    data: dict[str, object] = {}
    current: str | None = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        if line.startswith("  - ") and current:
            data.setdefault(current, [])
            value = line[4:].strip().strip('"')
            if isinstance(data[current], list):
                data[current].append(value)
            continue
        if ":" in line:
            key, raw_value = line.split(":", 1)
            key = key.strip()
            value = raw_value.strip()
            data[key] = [] if value == "" else value
            current = key
    return data


def note_stems(root: Path) -> dict[str, list[Path]]:
    stems: dict[str, list[Path]] = {}
    for path in iter_notes(root):
        stems.setdefault(path.stem, []).append(path)
    return stems


def resolve_wiki(target: str, root: Path, stems: dict[str, list[Path]]) -> bool:
    target = target.strip()
    direct = (root / target).with_suffix(".md") if not target.endswith(".md") else root / target
    if direct.exists():
        return True
    return target in stems


def resolve_md(source: Path, target: str, root: Path) -> bool:
    target = target.split("#", 1)[0]
    if target.startswith(("http://", "https://", "mailto:")):
        return True
    candidate = (source.parent / target).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return candidate.exists()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint an LLM Wiki vault.")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    args = parser.parse_args()

    root = Path(args.vault).expanduser().resolve()
    notes = iter_notes(root)
    stems = note_stems(root)
    incoming: dict[Path, int] = {path: 0 for path in notes}
    issues: list[str] = []
    index_text = (root / "index.md").read_text(encoding="utf-8", errors="replace") if (root / "index.md").exists() else ""

    for path in notes:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        rel_path = rel(path, root)
        if fm is None:
            issues.append(f"missing-frontmatter: {rel_path}")
        else:
            for key in ("date", "tags", "type", "sources"):
                if key not in fm:
                    issues.append(f"missing-frontmatter-key:{key}: {rel_path}")
            note_type = fm.get("type")
            sources = fm.get("sources")
            if note_type not in ("index", "log") and (sources == [] or sources in (None, "")):
                issues.append(f"missing-sources: {rel_path}")

        for target in WIKI_LINK.findall(text):
            if not resolve_wiki(target, root, stems):
                issues.append(f"broken-wiki-link: {rel_path} -> [[{target}]]")
            else:
                for candidate in stems.get(target, []):
                    incoming[candidate] = incoming.get(candidate, 0) + 1

        for target in MD_LINK.findall(text):
            if not resolve_md(path, target, root):
                issues.append(f"broken-md-link: {rel_path} -> {target}")

        if rel_path != "index.md" and rel_path not in index_text and not rel_path.startswith("logs/"):
            issues.append(f"not-in-index: {rel_path}")

    for path, count in incoming.items():
        rel_path = rel(path, root)
        if count == 0 and rel_path != "index.md" and not rel_path.startswith("logs/"):
            issues.append(f"orphan-note: {rel_path}")

    print(f"# LLM Wiki lint\nvault: {root}\nnotes: {len(notes)}\nissues: {len(issues)}")
    for issue in issues:
        print(f"- {issue}")


if __name__ == "__main__":
    main()
