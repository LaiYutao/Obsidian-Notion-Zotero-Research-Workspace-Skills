#!/usr/bin/env python3
"""Create an Obsidian Markdown note with date/tags frontmatter."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TZ_NAME = "Asia/Shanghai"


def normalize_tag(tag: str) -> str:
    tag = tag.strip().lstrip("#").strip()
    return re.sub(r"\s+", "-", tag)


def frontmatter(now: datetime, extra: list[str]) -> str:
    lines = [
        "---",
        f"date: {now.date().isoformat()}",
    ]
    lines.extend(extra)
    lines.append("---")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Markdown note with date/tags metadata.")
    parser.add_argument("--vault", default=".", help="Vault root. Defaults to current directory.")
    parser.add_argument("--path", required=True, help="Relative note path inside the vault.")
    parser.add_argument("--title", help="Optional body heading title. Omit to avoid duplicating the filename.")
    parser.add_argument("--body", default="", help="Initial note body after the frontmatter or optional title.")
    parser.add_argument("--tag", action="append", default=[], help="Add a content-derived YAML tag. Repeat for multiple tags.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing file.")
    args = parser.parse_args()

    root = Path(args.vault).expanduser().resolve()
    path = (root / args.path).resolve()
    if root not in path.parents and path != root:
        raise SystemExit(f"Refusing to create outside vault: {path}")
    if path.suffix.lower() != ".md":
        raise SystemExit("Use a .md path for Obsidian notes.")
    if path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing file: {path}")

    now = datetime.now(ZoneInfo(TZ_NAME))
    extra: list[str] = []
    if args.tag:
        tags = list(dict.fromkeys(tag for raw in args.tag if (tag := normalize_tag(raw))))
        if tags:
            extra.append("tags:")
            extra.extend(f"  - {tag}" for tag in tags)

    body = args.body.strip()
    content = frontmatter(now, extra)
    if args.title:
        content += f"\n# {args.title.strip()}\n"
    if body:
        content += f"\n{body}\n"
    elif not args.title:
        content += "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(path.relative_to(root).as_posix())


if __name__ == "__main__":
    main()
