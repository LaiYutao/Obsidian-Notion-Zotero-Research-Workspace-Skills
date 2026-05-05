#!/usr/bin/env python3
"""Append a chronological log entry to the LLM Wiki vault."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path


BEIJING = timezone(timedelta(hours=8))


def now() -> datetime:
    return datetime.now(BEIJING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append an LLM Wiki operation log entry.")
    parser.add_argument("--vault", default=os.environ.get("LLM_WIKI_VAULT"))
    parser.add_argument("--kind", required=True, choices=["ingest", "query", "lint", "maintenance", "init"])
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--path", action="append", default=[], help="Relevant vault-relative paths.")
    args = parser.parse_args()

    if not args.vault:
        raise SystemExit("Set LLM_WIKI_VAULT or pass --vault <path>.")
    root = Path(args.vault).expanduser().resolve()
    timestamp = now()
    log_path = root / "logs" / f"{timestamp:%Y-%m}.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_path.exists():
        log_path.write_text(
            "\n".join(
                [
                    "---",
                    f"date: {timestamp.date().isoformat()}",
                    "tags:",
                    "  - llm-wiki",
                    "type: log",
                    "sources: []",
                    "---",
                    f"# {timestamp:%Y-%m} Log",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    lines = [
        f"## [{timestamp:%Y-%m-%d %H:%M}] {args.kind} | {args.title}",
        "",
        args.summary.strip(),
    ]
    if args.path:
        lines.extend(["", "Paths:"])
        lines.extend(f"- `{item}`" for item in args.path)
    lines.append("")

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(log_path)


if __name__ == "__main__":
    main()
