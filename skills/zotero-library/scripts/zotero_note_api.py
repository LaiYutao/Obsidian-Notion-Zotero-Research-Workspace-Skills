#!/usr/bin/env python3
"""Create Zotero notes through the Zotero Web API."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://api.zotero.org"
H1_START_RE = re.compile(r"^\s*<h1(?:\s[^>]*)?>", re.IGNORECASE)


def config() -> dict[str, str]:
    required = {
        "ZOTERO_LIBRARY_TYPE": os.environ.get("ZOTERO_LIBRARY_TYPE", ""),
        "ZOTERO_LIBRARY_ID": os.environ.get("ZOTERO_LIBRARY_ID", ""),
        "ZOTERO_API_KEY": os.environ.get("ZOTERO_API_KEY", ""),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise SystemExit("Missing required environment variables: " + ", ".join(missing))
    if required["ZOTERO_LIBRARY_TYPE"] not in {"user", "group"}:
        raise SystemExit("ZOTERO_LIBRARY_TYPE must be 'user' or 'group'")
    return required


def library_path(cfg: dict[str, str]) -> str:
    plural = "users" if cfg["ZOTERO_LIBRARY_TYPE"] == "user" else "groups"
    return f"/{plural}/{cfg['ZOTERO_LIBRARY_ID']}"


def request_json(method: str, path: str, cfg: dict[str, str], body: Any | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        method=method,
        headers={
            "Zotero-API-Version": "3",
            "Zotero-API-Key": cfg["ZOTERO_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Zotero API HTTP {exc.code}: {detail}") from exc


def read_note_html(path: str | None, text: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if text:
        return "<p>" + html.escape(text).replace("\n\n", "</p><p>").replace("\n", "<br/>") + "</p>"
    raise SystemExit("Provide --html or --text")


def payload(title: str, note_html: str, parent_key: str | None = None) -> list[dict[str, Any]]:
    note = note_html.strip()
    if title and not H1_START_RE.match(note) and title not in note[:300]:
        note = f"<h1>{html.escape(title)}</h1>\n{note}"
    item: dict[str, Any] = {
        "itemType": "note",
        "note": note,
    }
    if parent_key:
        item["parentItem"] = parent_key
    return [item]


def create_note(args: argparse.Namespace) -> None:
    note_html = read_note_html(args.html, args.text)
    body = payload(args.title, note_html, getattr(args, "parent_key", None))
    if args.dry_run:
        library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "<user-or-group>")
        library_id = os.environ.get("ZOTERO_LIBRARY_ID", "<library-id>")
        plural = "users" if library_type == "user" else "groups" if library_type == "group" else "<users-or-groups>"
        print(
            json.dumps(
                {"endpoint": f"/{plural}/{library_id}/items", "payload": body},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    cfg = config()
    result = request_json("POST", library_path(cfg) + "/items", cfg, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def update_note(args: argparse.Namespace) -> None:
    note_html = read_note_html(args.html, args.text)
    cfg = config()
    current = request_json("GET", library_path(cfg) + f"/items/{args.note_key}", cfg)
    body = dict(current["data"])
    body["note"] = note_html.strip()
    if args.parent_key:
        body["parentItem"] = args.parent_key
    result = request_json("PUT", library_path(cfg) + f"/items/{args.note_key}", cfg, body)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def check_config(_: argparse.Namespace) -> None:
    cfg = config()
    result = request_json("GET", library_path(cfg) + "/items/top?limit=1&format=json", cfg)
    print(json.dumps({"ok": True, "library": library_path(cfg), "sample_items": len(result)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check-config")
    p_check.set_defaults(func=check_config)

    p_standalone = sub.add_parser("create-standalone")
    p_standalone.add_argument("--title", required=True)
    p_standalone.add_argument("--html")
    p_standalone.add_argument("--text")
    p_standalone.add_argument("--dry-run", action="store_true")
    p_standalone.set_defaults(func=create_note)

    p_child = sub.add_parser("create-child")
    p_child.add_argument("--parent-key", required=True)
    p_child.add_argument("--title", required=True)
    p_child.add_argument("--html")
    p_child.add_argument("--text")
    p_child.add_argument("--dry-run", action="store_true")
    p_child.set_defaults(func=create_note)

    p_update = sub.add_parser("update-note")
    p_update.add_argument("--note-key", required=True)
    p_update.add_argument("--parent-key")
    p_update.add_argument("--html")
    p_update.add_argument("--text")
    p_update.set_defaults(func=update_note)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
