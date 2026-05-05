#!/usr/bin/env python3
"""Create a Markdown note in the LLM Wiki vault with standard frontmatter."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path


BEIJING = timezone(timedelta(hours=8))


def today() -> str:
    return datetime.now(BEIJING).date().isoformat()


def resolve_note(root: Path, raw_path: str) -> Path:
    path = (root / raw_path).resolve()
    root = root.resolve()
    if root not in path.parents and path != root:
        raise SystemExit(f"Refusing to write outside vault: {path}")
    if path.suffix.lower() != ".md":
        path = path.with_suffix(".md")
    return path


def yaml_list(values: list[str]) -> str:
    if not values:
        return " []"
    return "\n" + "\n".join(f"  - {value}" for value in values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a standard LLM Wiki note.")
    parser.add_argument("--vault", default=os.environ.get("LLM_WIKI_VAULT"))
    parser.add_argument("--path", required=True, help="Note path relative to the vault.")
    parser.add_argument("--type", required=True, choices=["source", "concept", "entity", "topic", "synthesis", "index", "log"])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--body", default="")
    parser.add_argument("--date", default=today())
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.vault:
        raise SystemExit("Set LLM_WIKI_VAULT or pass --vault <path>.")
    root = Path(args.vault).expanduser().resolve()
    path = resolve_note(root, args.path)
    if path.exists() and not args.overwrite:
        raise SystemExit(f"Note already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    body = args.body.rstrip()
    content = "\n".join(
        [
            "---",
            f"date: {args.date}",
            "tags:" + yaml_list(args.tag),
            f"type: {args.type}",
            "sources:" + yaml_list(args.source),
            "---",
            body,
        ]
    ).rstrip() + "\n"
    path.write_text(content, encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
