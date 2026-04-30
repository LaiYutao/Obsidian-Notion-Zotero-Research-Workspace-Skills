#!/usr/bin/env python3
"""Compact Obsidian vault search and preview helper."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


EXCLUDED_DIRS = {".obsidian", ".trash", ".git", "node_modules", ".cache"}


def vault_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


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


def read_text(path: Path, max_chars: int | None = None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]"
    return text


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.strip("# ").strip()
    return ""


def frontmatter(text: str, max_lines: int = 40) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    end = None
    for idx, line in enumerate(lines[1:max_lines], start=1):
        if line.strip() == "---":
            end = idx
            break
    if end is None:
        return ""
    return "\n".join(lines[: end + 1])


def compact_line(line: str, width: int = 220) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    if len(line) > width:
        return line[: width - 15].rstrip() + " ...[truncated]"
    return line


def rg_available() -> bool:
    try:
        subprocess.run(["rg", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except FileNotFoundError:
        return False


def search_with_rg(root: Path, query: str, fixed: bool) -> list[tuple[Path, int, str]]:
    cmd = [
        "rg",
        "--line-number",
        "--ignore-case",
        "--glob",
        "*.md",
        "--glob",
        "!**/.obsidian/**",
        "--glob",
        "!**/.trash/**",
        "--glob",
        "!**/.git/**",
        "--color",
        "never",
    ]
    if fixed:
        cmd.append("--fixed-strings")
    cmd.append("--")
    cmd.append(query)
    proc = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    matches: list[tuple[Path, int, str]] = []
    for raw in proc.stdout.splitlines():
        parts = raw.split(":", 2)
        if len(parts) != 3:
            continue
        path, line_no, line = parts
        try:
            matches.append((root / path, int(line_no), compact_line(line)))
        except ValueError:
            continue
    return matches


def search_with_python(root: Path, query: str, fixed: bool) -> list[tuple[Path, int, str]]:
    flags = re.IGNORECASE
    pattern = re.escape(query) if fixed else query
    regex = re.compile(pattern, flags)
    matches: list[tuple[Path, int, str]] = []
    for path in iter_notes(root):
        try:
            for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                if regex.search(line):
                    matches.append((path, idx, compact_line(line)))
        except OSError:
            continue
    return matches


def cmd_search(args: argparse.Namespace) -> None:
    root = vault_path(args.vault)
    matches = search_with_rg(root, args.query, args.fixed) if rg_available() else search_with_python(root, args.query, args.fixed)
    grouped: dict[Path, list[tuple[int, str]]] = {}
    for path, line_no, line in matches:
        grouped.setdefault(path, []).append((line_no, line))

    print(f"# Search: {args.query}")
    print(f"vault: {root}")
    print(f"files_matched: {len(grouped)}")
    for idx, (path, lines) in enumerate(grouped.items()):
        if idx >= args.limit:
            print(f"... {len(grouped) - args.limit} more files omitted")
            break
        try:
            text = read_text(path, args.heading_scan_chars)
        except OSError:
            text = ""
        print(f"\n- {rel(path, root)}")
        heading = first_heading(text)
        if heading:
            print(f"  title: {heading}")
        print(f"  modified: {datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')}")
        for line_no, line in lines[: args.max_lines_per_file]:
            print(f"  {line_no}: {line}")
        if len(lines) > args.max_lines_per_file:
            print(f"  ... {len(lines) - args.max_lines_per_file} more matches in file")


def cmd_preview(args: argparse.Namespace) -> None:
    root = vault_path(args.vault)
    for raw in args.paths:
        path = (root / raw).resolve()
        if not is_note(path, root):
            print(f"\n# {raw}\nskipped: not a Markdown note inside vault")
            continue
        text = read_text(path, args.max_chars)
        fm = frontmatter(text)
        headings = [line for line in text.splitlines() if line.startswith("#")][: args.max_headings]
        print(f"\n# {rel(path, root)}")
        print(f"modified: {datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')}")
        if fm:
            print("\nfrontmatter:")
            print(fm)
        if headings:
            print("\nheadings:")
            for heading in headings:
                print(f"- {heading}")
        print("\nexcerpt:")
        print(text)


def cmd_recent(args: argparse.Namespace) -> None:
    root = vault_path(args.vault)
    notes = sorted(iter_notes(root), key=lambda path: path.stat().st_mtime, reverse=True)
    print(f"# Recent notes\nvault: {root}")
    for path in notes[: args.limit]:
        try:
            text = read_text(path, args.heading_scan_chars)
        except OSError:
            text = ""
        title = first_heading(text)
        suffix = f" | {title}" if title else ""
        print(f"- {datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')} | {rel(path, root)}{suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search and preview Obsidian Markdown notes with compact output.")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--vault", default=".")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--max-lines-per-file", type=int, default=3)
    search.add_argument("--heading-scan-chars", type=int, default=6000)
    search.add_argument("--fixed", action="store_true", help="Treat query as a literal string.")
    search.set_defaults(func=cmd_search)

    preview = sub.add_parser("preview")
    preview.add_argument("paths", nargs="+")
    preview.add_argument("--vault", default=".")
    preview.add_argument("--max-chars", type=int, default=4000)
    preview.add_argument("--max-headings", type=int, default=30)
    preview.set_defaults(func=cmd_preview)

    recent = sub.add_parser("recent")
    recent.add_argument("--vault", default=".")
    recent.add_argument("--limit", type=int, default=30)
    recent.add_argument("--heading-scan-chars", type=int, default=6000)
    recent.set_defaults(func=cmd_recent)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
