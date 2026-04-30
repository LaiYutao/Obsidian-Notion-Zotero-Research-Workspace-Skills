#!/usr/bin/env python3
"""Read a local Zotero library without modifying zotero.sqlite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_DATA_DIR = ""
TEXT_LIMIT = 12000
NOTE_LIMIT = 4000
SEARCH_CONTEXT = 1200


SEARCH_FIELDS = ("title", "shortTitle", "DOI", "archiveID", "url")
DEFAULT_CHUNK_SIZE = 24000
MAX_EMIT_FULLTEXT_CHARS = 24000
RECOMMENDED_EXEC_MAX_OUTPUT_TOKENS = 20000
RECEIPT_RULE = (
    "Treat this range as received only if BEGIN and END markers are both visible "
    "and the command output contains no tool-level truncation/omission notice."
)


def data_dir() -> Path:
    raw = os.environ.get("ZOTERO_DATA_DIR", DEFAULT_DATA_DIR)
    if not raw:
        raise SystemExit("Set ZOTERO_DATA_DIR to your Zotero data directory.")
    return Path(raw).expanduser().resolve()


def connect() -> sqlite3.Connection:
    db_path = data_dir() / "zotero.sqlite"
    if not db_path.exists():
        raise SystemExit(f"zotero.sqlite not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def all_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def collection_paths(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = all_rows(
        conn,
        """
        SELECT collectionID, collectionName, parentCollectionID, key
        FROM collections
        ORDER BY parentCollectionID IS NOT NULL, collectionName COLLATE NOCASE
        """,
    )
    by_id = {r["collectionID"]: dict(r) for r in rows}

    def build_path(collection_id: int) -> str:
        parts: list[str] = []
        seen: set[int] = set()
        cur = collection_id
        while cur and cur not in seen:
            seen.add(cur)
            item = by_id[cur]
            parts.append(item["collectionName"])
            cur = item["parentCollectionID"]
        return "/".join(reversed(parts))

    out = []
    for row in rows:
        item = dict(row)
        item["path"] = build_path(row["collectionID"])
        out.append(item)
    return sorted(out, key=lambda x: x["path"].lower())


def find_collection(conn: sqlite3.Connection, path_or_name: str) -> dict[str, Any]:
    target = path_or_name.strip("/")
    matches = [c for c in collection_paths(conn) if c["path"] == target or c["collectionName"] == target]
    if not matches:
        raise SystemExit(f"No collection matched: {path_or_name}")
    if len(matches) > 1 and "/" not in target:
        raise SystemExit(
            "Multiple collections matched that name. Use a full path:\n"
            + "\n".join(f"- {m['path']} ({m['key']})" for m in matches[:20])
        )
    return matches[0]


def descendant_collection_ids(conn: sqlite3.Connection, collection_id: int) -> list[int]:
    ids = [collection_id]
    index: dict[int | None, list[int]] = {}
    for row in all_rows(conn, "SELECT collectionID, parentCollectionID FROM collections"):
        index.setdefault(row["parentCollectionID"], []).append(row["collectionID"])
    for cid in list(ids):
        children = index.get(cid, [])
        ids.extend(children)
    return ids


def item_fields(conn: sqlite3.Connection, item_id: int) -> dict[str, str]:
    rows = all_rows(
        conn,
        """
        SELECT f.fieldName, v.value
        FROM itemData d
        JOIN fields f ON f.fieldID = d.fieldID
        JOIN itemDataValues v ON v.valueID = d.valueID
        WHERE d.itemID = ?
        ORDER BY f.fieldName
        """,
        (item_id,),
    )
    return {r["fieldName"]: r["value"] for r in rows}


def item_creators(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    return rows_to_dicts(
        all_rows(
            conn,
            """
            SELECT ct.creatorType, c.firstName, c.lastName, c.fieldMode, ic.orderIndex
            FROM itemCreators ic
            JOIN creators c ON c.creatorID = ic.creatorID
            JOIN creatorTypes ct ON ct.creatorTypeID = ic.creatorTypeID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
            """,
            (item_id,),
        )
    )


def item_tags(conn: sqlite3.Connection, item_id: int) -> list[str]:
    return [
        r["name"]
        for r in all_rows(
            conn,
            """
            SELECT t.name
            FROM itemTags it
            JOIN tags t ON t.tagID = it.tagID
            WHERE it.itemID = ?
            ORDER BY t.name COLLATE NOCASE
            """,
            (item_id,),
        )
    ]


def item_collections(conn: sqlite3.Connection, item_id: int) -> list[str]:
    paths_by_id = {c["collectionID"]: c["path"] for c in collection_paths(conn)}
    return [
        paths_by_id[r["collectionID"]]
        for r in all_rows(conn, "SELECT collectionID FROM collectionItems WHERE itemID = ?", (item_id,))
        if r["collectionID"] in paths_by_id
    ]


def item_counts(conn: sqlite3.Connection, item_id: int) -> dict[str, int]:
    attachments = one(conn, "SELECT COUNT(*) AS n FROM itemAttachments WHERE parentItemID = ?", (item_id,))
    notes = one(conn, "SELECT COUNT(*) AS n FROM itemNotes WHERE parentItemID = ?", (item_id,))
    return {
        "attachmentCount": int(attachments["n"] if attachments else 0),
        "noteCount": int(notes["n"] if notes else 0),
    }


def creator_brief(creators: list[dict[str, Any]], limit: int = 4) -> list[str]:
    out = []
    for creator in creators[:limit]:
        name = " ".join(
            part
            for part in (creator.get("firstName"), creator.get("lastName"))
            if part
        ).strip()
        if name:
            out.append(name)
    if len(creators) > limit:
        out.append(f"+{len(creators) - limit} more")
    return out


def item_brief(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    row = one(
        conn,
        """
        SELECT i.itemID, i.key, it.typeName, i.dateAdded, i.dateModified
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE i.itemID = ?
        """,
        (item_id,),
    )
    if row is None:
        raise SystemExit(f"No itemID: {item_id}")
    fields = item_fields(conn, item_id)
    out = dict(row)
    out["title"] = fields.get("title")
    out["shortTitle"] = fields.get("shortTitle")
    out["date"] = fields.get("date")
    out["DOI"] = fields.get("DOI")
    out["archiveID"] = fields.get("archiveID")
    out["url"] = fields.get("url")
    out["creators"] = creator_brief(item_creators(conn, item_id))
    out["collections"] = item_collections(conn, item_id)
    out.update(item_counts(conn, item_id))
    return out


def resolve_attachment_path(att_key: str, raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    if raw_path.startswith("storage:"):
        return str(data_dir() / "storage" / att_key / raw_path.split(":", 1)[1])
    return raw_path


def read_fulltext_cache(att_key: str) -> tuple[Path, str | None]:
    cache = data_dir() / "storage" / att_key / ".zotero-ft-cache"
    if not cache.exists():
        return cache, None
    return cache, cache.read_text(errors="replace")


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_window(text: str, start: int = 0, limit: int = TEXT_LIMIT) -> dict[str, Any]:
    if start < 0:
        start = max(0, len(text) + start)
    start = min(start, len(text))
    if limit < 0:
        end = len(text)
    else:
        end = min(len(text), start + limit)
    selected = text[start:end]
    return {
        "chars": len(text),
        "start": start,
        "end": end,
        "selection_complete": start == 0 and end == len(text),
        "text": selected,
        "window_sha256": text_sha256(selected),
        "truncated_before": start > 0,
        "truncated_after": end < len(text),
    }


def attachment_fulltext(att_key: str, limit: int = TEXT_LIMIT, start: int = 0) -> dict[str, Any]:
    cache, text = read_fulltext_cache(att_key)
    if text is None:
        return {"cache_path": str(cache), "available": False}
    out = {"cache_path": str(cache), "available": True}
    out.update(text_window(text, start=start, limit=limit))
    return out


def item_attachments(
    conn: sqlite3.Connection,
    item_id: int,
    include_fulltext: bool,
    fulltext_limit: int = TEXT_LIMIT,
    fulltext_start: int = 0,
) -> list[dict[str, Any]]:
    rows = all_rows(
        conn,
        """
        SELECT a.itemID, i.key, a.parentItemID, a.linkMode, a.contentType, a.path
        FROM itemAttachments a
        JOIN items i ON i.itemID = a.itemID
        WHERE a.parentItemID = ?
        ORDER BY a.itemID
        """,
        (item_id,),
    )
    attachments = []
    for r in rows:
        item = dict(r)
        item["resolved_path"] = resolve_attachment_path(r["key"], r["path"])
        if include_fulltext:
            item["fulltext"] = attachment_fulltext(r["key"], limit=fulltext_limit, start=fulltext_start)
        attachments.append(item)
    return attachments


def item_notes(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    notes = rows_to_dicts(
        all_rows(
            conn,
            """
            SELECT n.itemID, i.key, n.parentItemID, n.title, n.note
            FROM itemNotes n
            JOIN items i ON i.itemID = n.itemID
            WHERE n.parentItemID = ?
            ORDER BY i.dateModified DESC
            """,
            (item_id,),
        )
    )
    for note in notes:
        text = note.get("note") or ""
        note["chars"] = len(text)
        note["truncated"] = len(text) > NOTE_LIMIT
        note["note"] = text[:NOTE_LIMIT]
    return notes


def item_summary(
    conn: sqlite3.Connection,
    item_id: int,
    include_fulltext: bool = False,
    fulltext_limit: int = TEXT_LIMIT,
    fulltext_start: int = 0,
) -> dict[str, Any]:
    row = one(
        conn,
        """
        SELECT i.itemID, i.key, it.typeName, i.dateAdded, i.dateModified
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE i.itemID = ?
        """,
        (item_id,),
    )
    if row is None:
        raise SystemExit(f"No itemID: {item_id}")
    out = dict(row)
    out["fields"] = item_fields(conn, item_id)
    out["creators"] = item_creators(conn, item_id)
    out["tags"] = item_tags(conn, item_id)
    out["collections"] = item_collections(conn, item_id)
    out["notes"] = item_notes(conn, item_id)
    out["attachments"] = item_attachments(
        conn,
        item_id,
        include_fulltext,
        fulltext_limit=fulltext_limit,
        fulltext_start=fulltext_start,
    )
    return out


def item_attachment_rows(conn: sqlite3.Connection, item_id: int) -> list[sqlite3.Row]:
    return all_rows(
        conn,
        """
        SELECT a.itemID, i.key, a.parentItemID, a.linkMode, a.contentType, a.path
        FROM itemAttachments a
        JOIN items i ON i.itemID = a.itemID
        WHERE a.parentItemID = ?
        ORDER BY
          CASE WHEN a.contentType = 'application/pdf' THEN 0 ELSE 1 END,
          a.itemID
        """,
        (item_id,),
    )


def resolve_attachment_key(conn: sqlite3.Connection, item_id: int, attachment_key: str | None) -> str:
    rows = item_attachment_rows(conn, item_id)
    if not rows:
        raise SystemExit("Selected item has no attachments")
    if attachment_key:
        for row in rows:
            if row["key"] == attachment_key:
                return attachment_key
        raise SystemExit(f"Attachment key {attachment_key} is not a child of selected item")
    for row in rows:
        cache, text = read_fulltext_cache(row["key"])
        if text is not None:
            return row["key"]
    raise SystemExit("Selected item has attachments, but no full-text cache is available")


def resolve_pdf_attachment(conn: sqlite3.Connection, item_id: int, attachment_key: str | None) -> dict[str, Any]:
    rows = item_attachment_rows(conn, item_id)
    if not rows:
        raise SystemExit("Selected item has no attachments")
    candidates = []
    for row in rows:
        item = dict(row)
        item["resolved_path"] = resolve_attachment_path(row["key"], row["path"])
        if attachment_key and row["key"] != attachment_key:
            continue
        if item["contentType"] == "application/pdf" or str(item.get("resolved_path") or "").casefold().endswith(".pdf"):
            candidates.append(item)
    if attachment_key and not candidates:
        raise SystemExit(f"Attachment key {attachment_key} is not a PDF child of selected item")
    if not candidates:
        raise SystemExit("Selected item has no PDF attachment")
    pdf = candidates[0]
    if not pdf.get("resolved_path") or not Path(pdf["resolved_path"]).exists():
        raise SystemExit(f"PDF attachment path not found: {pdf.get('resolved_path')}")
    return pdf


def zotero_tmp_dir(item_key: str) -> Path:
    path = Path("/tmp") / "zotero-library" / item_key
    path.mkdir(parents=True, exist_ok=True)
    return path


def coverage_file(item_key: str) -> Path:
    return zotero_tmp_dir(item_key) / "coverage.json"


def load_coverage(item_key: str) -> dict[str, Any]:
    path = coverage_file(item_key)
    if not path.exists():
        return {"item_key": item_key, "text_reads": [], "visual_pages": [], "inspections": []}
    try:
        return json.loads(path.read_text(errors="replace"))
    except json.JSONDecodeError:
        return {"item_key": item_key, "text_reads": [], "visual_pages": [], "inspections": []}


def save_coverage(item_key: str, state: dict[str, Any]) -> None:
    path = coverage_file(item_key)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def record_text_read(item_key: str, read: dict[str, Any]) -> None:
    state = load_coverage(item_key)
    read["timestamp"] = int(time.time())
    read.setdefault("coverage_kind", "tool-selected")
    state.setdefault("text_reads", []).append(read)
    save_coverage(item_key, state)


def record_visual_pages(
    item_key: str,
    pages: list[int],
    image_paths: list[str],
    source: str,
    inspected: bool = False,
    note: str | None = None,
) -> None:
    state = load_coverage(item_key)
    known = {(entry.get("page"), entry.get("image_path")) for entry in state.setdefault("visual_pages", [])}
    for page, image_path in zip(pages, image_paths):
        key = (page, image_path)
        if key not in known:
            entry = {"page": page, "image_path": image_path, "source": source, "timestamp": int(time.time())}
            if inspected:
                entry["visually_inspected"] = True
                entry["inspected_timestamp"] = int(time.time())
            if note:
                entry["note"] = note
            state["visual_pages"].append(entry)
        elif inspected:
            for entry in state["visual_pages"]:
                if (entry.get("page"), entry.get("image_path")) == key:
                    entry["visually_inspected"] = True
                    entry["inspected_timestamp"] = int(time.time())
                    if note:
                        entry["note"] = note
    save_coverage(item_key, state)


def record_inspection(item_key: str, inspection: dict[str, Any]) -> None:
    state = load_coverage(item_key)
    state.setdefault("inspections", []).append(
        {
            "timestamp": int(time.time()),
            "attachment_key": inspection.get("attachment_key"),
            "page_count": inspection.get("page_count"),
            "extraction_quality": inspection.get("extraction_quality"),
            "figure_table_index_count": len(inspection.get("figure_table_index", [])),
        }
    )
    save_coverage(item_key, state)


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted((s, e) for s, e in ranges if e > s):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def coverage_intervals(reads: list[dict[str, Any]], kind: str | None = None) -> list[tuple[int, int]]:
    return merge_ranges(
        [
            (int(read["start"]), int(read["end"]))
            for read in reads
            if isinstance(read.get("start"), int)
            and isinstance(read.get("end"), int)
            and (kind is None or read.get("coverage_kind") == kind)
        ]
    )


def interval_stats(intervals: list[tuple[int, int]], total_chars: int | None) -> dict[str, Any]:
    covered_chars = sum(end - start for start, end in intervals)
    gaps = []
    if total_chars is not None:
        cursor = 0
        for start, end in intervals:
            if start > cursor:
                gaps.append({"start": cursor, "end": start})
            cursor = max(cursor, end)
        if cursor < total_chars:
            gaps.append({"start": cursor, "end": total_chars})
    return {
        "covered_chars": covered_chars,
        "covered_ratio": (covered_chars / total_chars) if total_chars else None,
        "covered_intervals": [{"start": s, "end": e} for s, e in intervals],
        "gaps": gaps,
    }


def normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def likely_heading(line: str) -> bool:
    stripped = line.strip()
    if not 3 <= len(stripped) <= 120:
        return False
    if stripped in {"Abstract", "Introduction", "Conclusion", "Limitations", "References"}:
        return True
    numbered = re.match(r"^\d{1,2}(\.\d{1,2})*\s+(.+)$", stripped)
    if numbered:
        title = numbered.group(2).strip()
        if len(title) >= 8 and re.match(r"^[A-Za-z][A-Za-z ,:()/\-]+$", title):
            return True
    appendix = re.match(r"^(Appendix\s+)?[A-Z]\.?\s+(.+)$", stripped)
    if appendix:
        title = appendix.group(2).strip()
        if len(title) >= 8 and re.match(r"^[A-Za-z][A-Za-z ,:()/\-]+$", title):
            return True
    if re.match(r"^Appendix\s+[A-Z]\b", stripped):
        return True
    return False


def fulltext_outline(text: str, limit: int = 80) -> list[dict[str, Any]]:
    headings = []
    offset = 0
    for line in text.splitlines(keepends=True):
        clean = line.strip()
        if likely_heading(clean):
            headings.append({"offset": offset, "heading": clean})
            if len(headings) >= limit:
                break
        offset += len(line)
    return headings


def evidence_index_suggestion(text: str | None, outline: list[dict[str, Any]], has_pdf: bool) -> dict[str, Any]:
    if text is None or not has_pdf:
        return {"suggested": False, "reason": None, "message": None}
    heading_text = " ".join(str(entry.get("heading") or "") for entry in outline).casefold()
    deep_read_headings = (
        "experiment",
        "evaluation",
        "result",
        "ablation",
        "benchmark",
        "empirical",
        "analysis",
    )
    has_deep_read_heading = any(term in heading_text for term in deep_read_headings)
    labels = {
        (match.group("kind").rstrip(".").casefold(), match.group("num"))
        for match in LABEL_RE.finditer(text)
    }
    evidence_labels = [
        label
        for label in labels
        if label[0] in {"table", "algorithm", "equation", "eq"}
    ]
    if not has_deep_read_heading or len(evidence_labels) < 3:
        return {"suggested": False, "reason": None, "message": None}
    return {
        "suggested": True,
        "reason": "experimental/result headings and multiple table/equation/algorithm labels detected",
        "message": (
            "For review-style reading or evidence checks, consider rerunning with "
            "--include-evidence-index. Ordinary full-paper reading can skip this."
        ),
    }


def find_section_window(text: str, section: str, limit: int) -> dict[str, Any]:
    target = normalize_heading_text(section)
    headings = fulltext_outline(text, limit=500)
    for index, heading in enumerate(headings):
        heading_norm = normalize_heading_text(heading["heading"])
        if target in heading_norm:
            start = heading["offset"]
            section_end = headings[index + 1]["offset"] if index + 1 < len(headings) else len(text)
            end = section_end
            if limit >= 0:
                end = min(end, start + limit)
            out = {
                "section": heading["heading"],
                **text_window(text, start=start, limit=end - start),
            }
            out["section_start"] = start
            out["section_end"] = section_end
            out["section_chars"] = section_end - start
            out["selection_complete"] = end >= section_end
            return out
    raise SystemExit(f"No section heading matched: {section}")


def search_fulltext_windows(text: str, query: str, context: int, limit: int) -> list[dict[str, Any]]:
    if not query:
        raise SystemExit("--search must not be empty")
    if context < 0:
        raise SystemExit("--context must be >= 0")
    flags = re.IGNORECASE
    matches = list(re.finditer(re.escape(query), text, flags))
    out = []
    for match in matches[:limit]:
        start = max(0, match.start() - context)
        end = min(len(text), match.end() + context)
        out.append(
            {
                "match_start": match.start(),
                "match_end": match.end(),
                **text_window(text, start=start, limit=end - start),
            }
        )
    return out


def read_fulltext(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    start: int,
    chars: int,
    section: str | None,
    search: str | None,
    context: int,
    matches: int,
    outline: bool,
    text_only: bool,
    delivery_window: bool,
    record_ledger: bool,
) -> dict[str, Any]:
    item_id = resolve_item(conn, key, query)
    att_key = resolve_attachment_key(conn, item_id, attachment_key)
    cache, text = read_fulltext_cache(att_key)
    if text is None:
        raise SystemExit(f"No full-text cache available for attachment: {att_key}")
    out: dict[str, Any] = {
        "item": item_brief(conn, item_id),
        "attachment_key": att_key,
        "cache_path": str(cache),
        "chars": len(text),
        "fulltext_sha256": text_sha256(text),
    }
    if text_only and (outline or search):
        raise SystemExit("--text-only cannot be combined with --outline or --search")
    if delivery_window and (outline or search):
        raise SystemExit("--delivery-window cannot be combined with --outline or --search")
    if outline:
        out["outline"] = fulltext_outline(text)
    if section:
        out["window"] = find_section_window(text, section, chars)
        if record_ledger:
            record_text_read(
                out["item"]["key"],
                {
                    "scope": "section",
                    "section": out["window"].get("section"),
                    "start": out["window"].get("start"),
                    "end": out["window"].get("end"),
                    "total_chars": len(text),
                    "selection_complete": out["window"].get("selection_complete"),
                    "coverage_kind": "delivery-envelope-emitted" if delivery_window else "tool-selected",
                    "source": "read-fulltext --delivery-window" if delivery_window else "read-fulltext",
                },
            )
    elif search:
        out["matches"] = search_fulltext_windows(text, search, context, matches)
        if record_ledger:
            for match in out["matches"]:
                record_text_read(
                    out["item"]["key"],
                    {
                        "scope": "search-window",
                        "query": search,
                        "start": match.get("start"),
                        "end": match.get("end"),
                        "total_chars": len(text),
                        "selection_complete": match.get("selection_complete"),
                    },
                )
    else:
        out["window"] = text_window(text, start=start, limit=chars)
        if record_ledger:
            record_text_read(
                out["item"]["key"],
                {
                    "scope": "fulltext" if out["window"].get("selection_complete") else "window",
                    "start": out["window"].get("start"),
                    "end": out["window"].get("end"),
                    "total_chars": len(text),
                    "selection_complete": out["window"].get("selection_complete"),
                    "coverage_kind": "delivery-envelope-emitted" if delivery_window else "tool-selected",
                    "source": "read-fulltext --delivery-window" if delivery_window else "read-fulltext",
                },
            )
    return out


def format_delivery_window(result: dict[str, Any]) -> str:
    window = result.get("window")
    if not isinstance(window, dict):
        raise SystemExit("--delivery-window requires a single text window")
    item = result.get("item") or {}
    meta = {
        "item_key": item.get("key"),
        "attachment_key": result.get("attachment_key"),
        "cache_path": result.get("cache_path"),
        "start": window.get("start"),
        "end": window.get("end"),
        "total_chars": result.get("chars"),
        "selection_complete": window.get("selection_complete"),
        "window_sha256": window.get("window_sha256"),
        "fulltext_sha256": result.get("fulltext_sha256"),
        "receipt_rule": RECEIPT_RULE,
    }
    meta_json = json.dumps(meta, ensure_ascii=False, sort_keys=True)
    return "\n".join(
        [
            "ZOTERO_FULLTEXT_WINDOW_BEGIN",
            meta_json,
            "ZOTERO_FULLTEXT_WINDOW_TEXT",
            str(window.get("text") or ""),
            "ZOTERO_FULLTEXT_WINDOW_END",
            meta_json,
        ]
    )


def normalize_search_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def search_tokens(query: str) -> list[str]:
    return [token for token in normalize_search_text(query).split() if token]


def row_search_blob(row: sqlite3.Row | dict[str, Any]) -> str:
    return normalize_search_text(" ".join(str(row[field] or "") for field in SEARCH_FIELDS))


def score_search_row(row: sqlite3.Row | dict[str, Any], query: str) -> tuple[int, str]:
    query_norm = normalize_search_text(query)
    title_norm = normalize_search_text(row["title"])
    doi_norm = normalize_search_text(row["DOI"])
    archive_norm = normalize_search_text(row["archiveID"])
    url_norm = normalize_search_text(row["url"])
    key_norm = normalize_search_text(row["key"])
    blob = row_search_blob(row)
    tokens = search_tokens(query)

    if query_norm and query_norm in {key_norm, doi_norm, archive_norm}:
        return 100, "exact key/DOI/archiveID"
    if query_norm and title_norm == query_norm:
        return 95, "exact title"
    if query_norm and query_norm in title_norm:
        return 90, "title phrase"
    if tokens and all(token in title_norm for token in tokens):
        return 80, "all title tokens"
    if tokens and all(token in blob for token in tokens):
        return 70, "all query tokens"
    if query_norm and any(query_norm in field for field in (doi_norm, archive_norm, url_norm)):
        return 60, "identifier/url phrase"
    overlap = sum(1 for token in tokens if token in blob)
    if overlap and len(tokens) == 1:
        return 20 + overlap, f"{overlap}/{len(tokens)} query tokens"
    return 0, "no match"


def collection_item_ids(conn: sqlite3.Connection, collection_path: str | None, recursive: bool) -> list[int] | None:
    if not collection_path:
        return None
    coll = find_collection(conn, collection_path)
    ids = descendant_collection_ids(conn, coll["collectionID"]) if recursive else [coll["collectionID"]]
    placeholders = ",".join("?" for _ in ids)
    rows = all_rows(
        conn,
        f"""
        SELECT DISTINCT ci.itemID
        FROM collectionItems ci
        WHERE ci.collectionID IN ({placeholders})
        """,
        tuple(ids),
    )
    return [r["itemID"] for r in rows]


def candidate_item_rows(conn: sqlite3.Connection, collection_path: str | None = None, recursive: bool = False) -> list[sqlite3.Row]:
    item_ids = collection_item_ids(conn, collection_path, recursive)
    item_filter = ""
    params: tuple[Any, ...] = ()
    if item_ids is not None:
        if not item_ids:
            return []
        placeholders = ",".join("?" for _ in item_ids)
        item_filter = f"AND i.itemID IN ({placeholders})"
        params = tuple(item_ids)
    rows = all_rows(
        conn,
        f"""
        SELECT DISTINCT i.itemID, i.key, it.typeName,
               MAX(CASE WHEN f.fieldName = 'title' THEN v.value END) AS title,
               MAX(CASE WHEN f.fieldName = 'shortTitle' THEN v.value END) AS shortTitle,
               MAX(CASE WHEN f.fieldName = 'DOI' THEN v.value END) AS DOI,
               MAX(CASE WHEN f.fieldName = 'archiveID' THEN v.value END) AS archiveID,
               MAX(CASE WHEN f.fieldName = 'url' THEN v.value END) AS url,
               MAX(CASE WHEN f.fieldName = 'date' THEN v.value END) AS date
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        LEFT JOIN itemData d ON d.itemID = i.itemID
        LEFT JOIN fields f ON f.fieldID = d.fieldID
        LEFT JOIN itemDataValues v ON v.valueID = d.valueID
        WHERE it.typeName NOT IN ('attachment', 'note')
          {item_filter}
        GROUP BY i.itemID
        ORDER BY title COLLATE NOCASE
        """,
        params,
    )
    return rows


def search_items(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    collection_path: str | None = None,
    recursive: bool = False,
) -> list[dict[str, Any]]:
    scored = []
    for row in candidate_item_rows(conn, collection_path, recursive):
        score, reason = score_search_row(row, query)
        if score <= 0:
            continue
        item = dict(row)
        item["score"] = score
        item["matchReason"] = reason
        scored.append(item)
    scored.sort(key=lambda item: (-item["score"], normalize_search_text(item.get("title")), item["key"]))
    return scored[:limit]


def find_items(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    collection_path: str | None = None,
    recursive: bool = False,
) -> list[dict[str, Any]]:
    out = []
    for match in search_items(conn, query, limit, collection_path, recursive):
        brief = item_brief(conn, match["itemID"])
        brief["score"] = match["score"]
        brief["matchReason"] = match["matchReason"]
        out.append(brief)
    return out


def resolve_item(conn: sqlite3.Connection, key: str | None, query: str | None) -> int:
    if key:
        row = one(conn, "SELECT itemID FROM items WHERE key = ?", (key,))
        if not row:
            raise SystemExit(f"No item matched key: {key}")
        return row["itemID"]
    if not query:
        raise SystemExit("Provide --key or --query")
    matches = search_items(conn, query, 20)
    if not matches:
        raise SystemExit(f"No item matched query: {query}")
    if len(matches) > 1:
        exact_key = [m for m in matches if m["key"] == query]
        if len(exact_key) == 1:
            return exact_key[0]["itemID"]
        raise SystemExit(
            "Multiple items matched. Re-run with --key:\n"
            + "\n".join(f"- {m['key']}: {m.get('title') or '(no title)'}" for m in matches)
        )
    return matches[0]["itemID"]


def resolve_paper_item(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    collection_path: str | None,
    recursive: bool,
) -> tuple[int, dict[str, Any]]:
    if key:
        item_id = resolve_item(conn, key, None)
        return item_id, {"method": "key", "key": key, "collection": collection_path}
    if not query:
        raise SystemExit("Provide --key or --query")
    matches = search_items(conn, query, 20, collection_path, recursive)
    if not matches:
        scope = f" in collection {collection_path!r}" if collection_path else ""
        raise SystemExit(f"No item matched query{scope}: {query}")
    exact = [
        match
        for match in matches
        if match.get("matchReason") in {"exact key/DOI/archiveID", "exact title"}
    ]
    if len(exact) == 1:
        return exact[0]["itemID"], {
            "method": "query",
            "query": query,
            "collection": collection_path,
            "selected_reason": exact[0].get("matchReason"),
            "candidate_count": len(matches),
        }
    if len(matches) == 1:
        return matches[0]["itemID"], {
            "method": "query",
            "query": query,
            "collection": collection_path,
            "selected_reason": matches[0].get("matchReason"),
            "candidate_count": 1,
        }
    top, second = matches[0], matches[1]
    if int(top.get("score") or 0) >= 90 and int(top.get("score") or 0) > int(second.get("score") or 0):
        return top["itemID"], {
            "method": "query",
            "query": query,
            "collection": collection_path,
            "selected_reason": top.get("matchReason"),
            "candidate_count": len(matches),
            "note": "Selected a dominant title/identifier match.",
        }
    raise SystemExit(
        "Multiple items matched. Re-run with --key:\n"
        + "\n".join(f"- {m['key']}: {m.get('title') or '(no title)'} [{m.get('matchReason')}]" for m in matches)
    )


def collection_items(
    conn: sqlite3.Connection,
    collection_id: int,
    recursive: bool,
    limit: int,
    brief: bool,
    fulltext_limit: int = TEXT_LIMIT,
    fulltext_start: int = 0,
) -> list[dict[str, Any]]:
    ids = descendant_collection_ids(conn, collection_id) if recursive else [collection_id]
    placeholders = ",".join("?" for _ in ids)
    rows = all_rows(
        conn,
        f"""
        SELECT DISTINCT ci.itemID
        FROM collectionItems ci
        JOIN items i ON i.itemID = ci.itemID
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE ci.collectionID IN ({placeholders})
          AND it.typeName NOT IN ('attachment', 'note')
        ORDER BY ci.orderIndex, ci.itemID
        LIMIT ?
        """,
        (*ids, limit),
    )
    reader = item_brief if brief else lambda c, item_id: item_summary(c, item_id, include_fulltext=False)
    return [reader(conn, r["itemID"]) for r in rows]


def run_text_command(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemExit(f"Required command not found: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        raise SystemExit(f"Command failed ({' '.join(cmd)}): {detail}")
    return proc.stdout


def tool_availability() -> dict[str, bool]:
    try:
        import fitz  # type: ignore  # noqa: F401

        has_fitz = True
    except Exception:
        has_fitz = False
    return {
        "pymupdf": has_fitz,
        "pdfinfo": shutil.which("pdfinfo") is not None,
        "pdftotext": shutil.which("pdftotext") is not None,
        "pdftoppm": shutil.which("pdftoppm") is not None,
    }


def pdfinfo_metadata(pdf_path: str) -> dict[str, Any]:
    if not shutil.which("pdfinfo"):
        return {"available": False}
    text = run_text_command(["pdfinfo", pdf_path])
    meta: dict[str, Any] = {"available": True}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key == "pages":
            try:
                meta["pages"] = int(value)
            except ValueError:
                meta["pages"] = value
        else:
            meta[key] = value
    return meta


def pdftotext_pages(pdf_path: str) -> list[str]:
    if not shutil.which("pdftotext"):
        return []
    text = run_text_command(["pdftotext", "-layout", pdf_path, "-"])
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def fitz_pages(pdf_path: str) -> list[dict[str, Any]] | None:
    try:
        import fitz  # type: ignore
    except Exception:
        return None
    doc = fitz.open(pdf_path)
    pages = []
    for index, page in enumerate(doc):
        text = page.get_text("text")
        pages.append(
            {
                "page": index + 1,
                "text": text,
                "text_chars": len(text),
                "image_count": len(page.get_images(full=True)),
                "width": page.rect.width,
                "height": page.rect.height,
            }
        )
    doc.close()
    return pages


LABEL_RE = re.compile(
    r"\b(?P<kind>Figure|Fig\.|Table|Algorithm|Equation|Eq\.)\s*(?P<num>[A-Za-z]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
SECTION_LINE_RE = re.compile(r"^\s*(\d{1,2}(\.\d{1,2})*|[A-Z])\s+[A-Z][A-Za-z0-9 ,:()/\-]+$")
FIGURE_CAPTION_RE = re.compile(r"\b(?P<kind>Figure|Fig\.)\s+(?P<num>[A-Za-z]?\d+(?:\.\d+)?)\s*:", re.IGNORECASE)
TABLE_CAPTION_RE = re.compile(r"\bTable\s+(?P<num>[A-Za-z]?\d+(?:\.\d+)?)\s*:", re.IGNORECASE)
ALGORITHM_RE = re.compile(r"\bAlgorithm\s+(?P<num>[A-Za-z]?\d+(?:\.\d+)?)\s*:", re.IGNORECASE)
EQUATION_NUMBER_RE = re.compile(r"(?:^|\s)\((?P<num>\d{1,3}(?:\.\d+)?)\)\s*$")


def excerpt_around(text: str, start: int, end: int, context: int = 220) -> str:
    left = max(0, start - context)
    right = min(len(text), end + context)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def page_label_index(page_texts: list[str]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, int]] = set()
    out = []
    for page_num, text in enumerate(page_texts, start=1):
        for match in LABEL_RE.finditer(text):
            kind = match.group("kind").rstrip(".")
            number = match.group("num")
            key = (kind.casefold(), number, page_num)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "kind": kind,
                    "number": number,
                    "label": f"{kind} {number}",
                    "page": page_num,
                    "excerpt": excerpt_around(text, match.start(), match.end()),
                }
            )
    return out


def page_evidence_index(page_texts: list[str]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, int]] = set()
    out = []

    def add_label(kind: str, number: str, page_num: int, text: str, start: int, end: int) -> None:
        normalized_kind = kind.rstrip(".")
        key = (normalized_kind.casefold(), number, page_num)
        if key in seen:
            return
        seen.add(key)
        out.append(
            {
                "kind": normalized_kind,
                "number": number,
                "label": f"{normalized_kind} {number}",
                "page": page_num,
                "excerpt": excerpt_around(text, start, end, context=90),
            }
        )

    for page_num, text in enumerate(page_texts, start=1):
        for match in FIGURE_CAPTION_RE.finditer(text):
            add_label(match.group("kind"), match.group("num"), page_num, text, match.start(), match.end())
        for match in TABLE_CAPTION_RE.finditer(text):
            add_label("Table", match.group("num"), page_num, text, match.start(), match.end())
        for match in ALGORITHM_RE.finditer(text):
            add_label("Algorithm", match.group("num"), page_num, text, match.start(), match.end())
        offset = 0
        for line in text.splitlines(keepends=True):
            match = EQUATION_NUMBER_RE.search(line)
            if match:
                num = match.group("num")
                if "." in num and len(num.rsplit(".", 1)[1]) > 2:
                    offset += len(line)
                    continue
                add_label("Equation", num, page_num, text, offset + match.start(), offset + match.end())
            offset += len(line)
    return out


def layout_pages_for_item(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    item_id = resolve_item(conn, key, query)
    item = item_brief(conn, item_id)
    pdf = resolve_pdf_attachment(conn, item_id, attachment_key)
    pages = pdftotext_pages(pdf["resolved_path"])
    if not pages:
        fitz_data = fitz_pages(pdf["resolved_path"])
        pages = [page["text"] for page in fitz_data] if fitz_data else []
    if not pages:
        raise SystemExit("No page-level text could be extracted from the PDF")
    return item, pdf, pages


def line_window(lines: list[str], line_index: int, before: int, after: int) -> dict[str, Any]:
    start = max(0, line_index - before)
    end = min(len(lines), line_index + after + 1)
    return {
        "line_start": start + 1,
        "line_end": end,
        "selection_complete": start == 0 and end == len(lines),
        "text": "\n".join(lines[start:end]).rstrip(),
    }


def page_window_for_match(text: str, match: re.Match[str], context_chars: int) -> dict[str, Any]:
    if context_chars < 0:
        start, end = 0, len(text)
    else:
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)
    return {
        "start": start,
        "end": end,
        "selection_complete": start == 0 and end == len(text),
        "text": text[start:end].strip(),
    }


def label_matches(label: str | None, kind: str, number: str) -> bool:
    if not label:
        return True
    label_norm = normalize_search_text(label)
    kind_label_norm = normalize_search_text(f"{kind} {number}")
    short_kind_norm = normalize_search_text(f"{kind[:3]} {number}")
    number_norm = normalize_search_text(number)
    aliases = {
        "equation": "eq",
        "figure": "fig",
        "algorithm": "alg",
        "table": "tab",
    }
    alias_norm = normalize_search_text(f"{aliases.get(kind.casefold(), kind[:3])} {number}")
    return label_norm in {kind_label_norm, short_kind_norm, alias_norm, number_norm}


def ambiguity_report(reasons: list[str]) -> dict[str, Any]:
    return {
        "ambiguous": bool(reasons),
        "reasons": reasons,
        "policy": "If ambiguous is true, render and visually inspect the page before relying on exact symbols, columns, or numeric values.",
    }


def has_bad_control_chars(text: str) -> bool:
    return any(ord(ch) < 32 and ch not in "\n\r\t\f" for ch in text)


def table_ambiguity(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    reasons = []
    if "\ufffd" in text or "(cid:" in text:
        reasons.append("PDF text contains replacement/cid glyphs")
    if has_bad_control_chars(text):
        reasons.append("PDF text contains non-printing control characters")
    if len(lines) < 4:
        reasons.append("table block is very short")
    numeric_count = len(re.findall(r"[-+]?\d+(?:\.\d+)?", text))
    has_column_spacing = any(re.search(r"\S\s{2,}\S", line) for line in lines)
    if numeric_count >= 8 and not has_column_spacing:
        reasons.append("many numeric values but no clear column spacing")
    if sum(1 for line in lines if len(line) > 160) >= 2:
        reasons.append("multiple very wide lines may indicate wrapped or collapsed columns")
    if numeric_count >= 8:
        numeric_lines = [line for line in lines if re.search(r"\d", line)]
        if numeric_lines and len(numeric_lines) <= 2:
            reasons.append("many numeric values are compressed into very few lines")
    return ambiguity_report(reasons)


def equation_ambiguity(text: str, number: str) -> dict[str, Any]:
    reasons = []
    if "\ufffd" in text or "(cid:" in text:
        reasons.append("PDF text contains replacement/cid glyphs")
    if has_bad_control_chars(text):
        reasons.append("PDF text contains non-printing control characters")
    marker = f"({number})"
    marker_index = text.rfind(marker)
    formula_region = text[:marker_index] if marker_index >= 0 else text
    formula_region = formula_region.strip()
    if len(formula_region) < 12:
        reasons.append("equation text before the number is very short")
    math_markers = r"=+\-*/∑∏∫√≤≥<>∇∂∞∈⊙⊗×÷^_"
    if not re.search(f"[{re.escape(math_markers)}]", formula_region):
        reasons.append("few recognizable math/operator symbols near equation number")
    if re.search(r"\s{8,}\S+\s{8,}", formula_region):
        reasons.append("large spacing gaps may indicate broken multi-column or aligned math extraction")
    return ambiguity_report(reasons)


def render_ambiguous_pages(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    pdf: dict[str, Any],
    pages: list[int],
    render_on_ambiguous: bool,
    dpi: int,
) -> dict[str, Any] | None:
    page_nums = sorted(set(pages))
    if not render_on_ambiguous or not page_nums:
        return None
    if not shutil.which("pdftoppm"):
        return {
            "pages": page_nums,
            "rendered": False,
            "error": "pdftoppm is required for page rendering",
        }
    rendered = render_pdf_pages(
        conn,
        item["key"],
        None,
        pdf["key"],
        ",".join(str(page) for page in page_nums),
        dpi,
        False,
    )
    rendered["reason"] = "One or more extracted table/equation blocks were marked ambiguous."
    rendered["rendered"] = True
    return rendered


def read_tables(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    label: str | None,
    pages_arg: str | None,
    context_chars: int,
    render_on_ambiguous: bool,
    dpi: int,
) -> dict[str, Any]:
    item, pdf, pages = layout_pages_for_item(conn, key, query, attachment_key)
    wanted_pages = set(parse_pages(pages_arg, len(pages))) if pages_arg else None
    tables = []
    for page_num, text in enumerate(pages, start=1):
        if wanted_pages and page_num not in wanted_pages:
            continue
        for match in TABLE_CAPTION_RE.finditer(text):
            num = match.group("num")
            table_label = f"Table {num}"
            if not label_matches(label, "Table", num):
                continue
            window = page_window_for_match(text, match, context_chars)
            ambiguity = table_ambiguity(window["text"])
            if not window["selection_complete"]:
                ambiguity["ambiguous"] = True
                ambiguity["reasons"].append("table page block is truncated by context-chars")
            tables.append(
                {
                    "label": table_label,
                    "page": page_num,
                    "text_is_layout_preserved": True,
                    "window": window,
                    "ambiguity": ambiguity,
                    "note": "For exact numeric/layout claims, inspect the rendered page if this text block appears misaligned.",
                }
            )
    if pages_arg and not tables:
        for page_num in sorted(wanted_pages or []):
            text = pages[page_num - 1]
            tables.append(
                {
                    "label": None,
                    "page": page_num,
                    "text_is_layout_preserved": True,
                    "window": {
                        "start": 0,
                        "end": len(text),
                        "selection_complete": True,
                        "text": text.rstrip(),
                    },
                    "ambiguity": table_ambiguity(text),
                    "note": "Explicit page read; no Table caption was detected on this page.",
                }
            )
    ambiguous_pages = [entry["page"] for entry in tables if entry.get("ambiguity", {}).get("ambiguous")]
    return {
        "item": item,
        "attachment_key": pdf["key"],
        "pdf_path": pdf["resolved_path"],
        "source": "pdftotext -layout",
        "tables": tables,
        "ambiguous_pages": sorted(set(ambiguous_pages)),
        "rendered_ambiguous_pages": render_ambiguous_pages(
            conn, item, pdf, ambiguous_pages, render_on_ambiguous, dpi
        ),
        "policy": "Use these layout-preserved blocks for table evidence. If values/columns are ambiguous, render the page and visually inspect it.",
    }


def read_equations(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    label: str | None,
    pages_arg: str | None,
    context_lines: int,
    render_on_ambiguous: bool,
    dpi: int,
) -> dict[str, Any]:
    item, pdf, pages = layout_pages_for_item(conn, key, query, attachment_key)
    wanted_pages = set(parse_pages(pages_arg, len(pages))) if pages_arg else None
    equations = []
    for page_num, text in enumerate(pages, start=1):
        if wanted_pages and page_num not in wanted_pages:
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = EQUATION_NUMBER_RE.search(line)
            if not match:
                continue
            num = match.group("num")
            if not label_matches(label, "Equation", num):
                continue
            window = line_window(lines, index, context_lines, context_lines)
            ambiguity = equation_ambiguity(window["text"], num)
            equations.append(
                {
                    "label": f"Equation {num}",
                    "number": num,
                    "page": page_num,
                    "text_is_layout_preserved": True,
                    "window": window,
                    "ambiguity": ambiguity,
                    "note": "Formula text is extracted from the PDF layout layer. Render the page for exact typography if symbols are ambiguous.",
                }
            )
    ambiguous_pages = [entry["page"] for entry in equations if entry.get("ambiguity", {}).get("ambiguous")]
    return {
        "item": item,
        "attachment_key": pdf["key"],
        "pdf_path": pdf["resolved_path"],
        "source": "pdftotext -layout",
        "equations": equations,
        "ambiguous_pages": sorted(set(ambiguous_pages)),
        "rendered_ambiguous_pages": render_ambiguous_pages(
            conn, item, pdf, ambiguous_pages, render_on_ambiguous, dpi
        ),
        "policy": "Use numbered equation windows as primary formula evidence; visually inspect the page when symbol fidelity matters.",
    }


def read_algorithms(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    label: str | None,
    pages_arg: str | None,
    context_lines: int,
) -> dict[str, Any]:
    item, pdf, pages = layout_pages_for_item(conn, key, query, attachment_key)
    wanted_pages = set(parse_pages(pages_arg, len(pages))) if pages_arg else None
    algorithms = []
    for page_num, text in enumerate(pages, start=1):
        if wanted_pages and page_num not in wanted_pages:
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = ALGORITHM_RE.search(line)
            if not match:
                continue
            num = match.group("num")
            alg_label = f"Algorithm {num}"
            if not label_matches(label, "Algorithm", num):
                continue
            algorithms.append(
                {
                    "label": alg_label,
                    "page": page_num,
                    "text_is_layout_preserved": True,
                    "window": line_window(lines, index, 2, context_lines),
                    "note": "Algorithm block is extracted from layout text; render the page if indentation or symbols are critical.",
                }
            )
    return {
        "item": item,
        "attachment_key": pdf["key"],
        "pdf_path": pdf["resolved_path"],
        "source": "pdftotext -layout",
        "algorithms": algorithms,
        "policy": "Use these blocks for pseudocode evidence; visually inspect when indentation or math symbols are ambiguous.",
    }


def extraction_quality(page_texts: list[str], page_count: int) -> dict[str, Any]:
    chars = [len(text.strip()) for text in page_texts]
    empty_pages = sum(1 for n in chars if n < 40)
    mean_chars = int(sum(chars) / len(chars)) if chars else 0
    likely_scanned = page_count > 0 and (not chars or empty_pages / max(page_count, 1) > 0.5 or mean_chars < 200)
    return {
        "page_text_available": bool(chars),
        "page_count": page_count,
        "pages_with_text": sum(1 for n in chars if n >= 40),
        "empty_or_low_text_pages": empty_pages,
        "mean_text_chars_per_page": mean_chars,
        "likely_scanned_or_bad_text_layer": likely_scanned,
    }


def inspect_pdf(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    record_ledger: bool,
) -> dict[str, Any]:
    item_id = resolve_item(conn, key, query)
    item = item_brief(conn, item_id)
    pdf = resolve_pdf_attachment(conn, item_id, attachment_key)
    pdf_path = pdf["resolved_path"]
    tools = tool_availability()
    info = pdfinfo_metadata(pdf_path)
    fitz_data = fitz_pages(pdf_path)
    if fitz_data is not None:
        page_texts = [page["text"] for page in fitz_data]
        page_count = len(fitz_data)
        page_summaries = [
            {k: v for k, v in page.items() if k != "text"}
            for page in fitz_data[:20]
        ]
        parser = "pymupdf"
    else:
        page_texts = pdftotext_pages(pdf_path)
        page_count = int(info.get("pages") or len(page_texts) or 0)
        page_summaries = [
            {"page": i + 1, "text_chars": len(text)}
            for i, text in enumerate(page_texts[:20])
        ]
        parser = "pdftotext"
    labels = page_label_index(page_texts)
    inspection = {
        "item": item,
        "attachment_key": pdf["key"],
        "pdf_path": pdf_path,
        "tools": tools,
        "parser": parser,
        "pdfinfo": info,
        "page_count": page_count,
        "page_summaries": page_summaries,
        "extraction_quality": extraction_quality(page_texts, page_count),
        "figure_table_index": labels[:80],
        "figure_table_index_truncated": len(labels) > 80,
        "notes": [
            "Figure/table/equation index is text-derived; render pages and visually inspect before making claims about graphical content.",
            "Install PyMuPDF for richer page/image metadata; current fallback uses poppler tools when PyMuPDF is unavailable.",
        ],
    }
    if record_ledger:
        record_inspection(item["key"], inspection)
    return inspection


def parse_pages(pages: str, page_count: int | None = None) -> list[int]:
    out: list[int] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start, end = int(left), int(right)
            if end < start:
                raise SystemExit(f"Invalid page range: {part}")
            out.extend(range(start, end + 1))
        else:
            out.append(int(part))
    unique = sorted(set(out))
    if any(page < 1 for page in unique):
        raise SystemExit("Page numbers are 1-based and must be positive")
    if page_count and any(page > page_count for page in unique):
        raise SystemExit(f"Requested page exceeds PDF page count {page_count}: {unique}")
    return unique


def render_pdf_pages(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    pages: str,
    dpi: int,
    record_ledger: bool,
) -> dict[str, Any]:
    if not shutil.which("pdftoppm"):
        raise SystemExit("pdftoppm is required for page rendering")
    item_id = resolve_item(conn, key, query)
    item = item_brief(conn, item_id)
    pdf = resolve_pdf_attachment(conn, item_id, attachment_key)
    info = pdfinfo_metadata(pdf["resolved_path"])
    page_nums = parse_pages(pages, int(info["pages"]) if isinstance(info.get("pages"), int) else None)
    out_dir = zotero_tmp_dir(item["key"]) / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for page in page_nums:
        prefix = out_dir / f"{pdf['key']}-p{page:04d}-{dpi}dpi"
        cmd = [
            "pdftoppm",
            "-png",
            "-singlefile",
            "-r",
            str(dpi),
            "-f",
            str(page),
            "-l",
            str(page),
            pdf["resolved_path"],
            str(prefix),
        ]
        run_text_command(cmd)
        image_paths.append(str(prefix.with_suffix(".png")))
    if record_ledger:
        record_visual_pages(item["key"], page_nums, image_paths, "render-pages")
    return {
        "item": item,
        "attachment_key": pdf["key"],
        "pdf_path": pdf["resolved_path"],
        "dpi": dpi,
        "pages": page_nums,
        "image_paths": image_paths,
        "next_step": "Use view_image on these paths before making claims about figure/table visual content.",
    }


def read_figures(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    attachment_key: str | None,
    pages: str | None,
    max_pages: int,
    dpi: int,
    record_ledger: bool,
) -> dict[str, Any]:
    inspection = inspect_pdf(conn, key, query, attachment_key, record_ledger)
    if pages:
        selected_pages = parse_pages(pages, inspection.get("page_count"))
        selected_labels = [
            entry for entry in inspection["figure_table_index"] if entry["page"] in set(selected_pages)
        ]
    else:
        all_labels = inspection["figure_table_index"]
        selected_pages = []
        for entry in all_labels:
            if entry["page"] not in selected_pages:
                selected_pages.append(entry["page"])
            if len(selected_pages) >= max_pages:
                break
        selected_labels = [entry for entry in all_labels if entry["page"] in set(selected_pages)]
    if not selected_pages:
        return {
            "inspection": inspection,
            "rendered": None,
            "message": "No figure/table/equation references were found in the text layer. Use render-pages with explicit pages if needed.",
        }
    rendered = render_pdf_pages(
        conn,
        inspection["item"]["key"],
        None,
        inspection["attachment_key"],
        ",".join(str(page) for page in selected_pages),
        dpi,
        record_ledger,
    )
    if record_ledger:
        record_visual_pages(inspection["item"]["key"], selected_pages, rendered["image_paths"], "read-figures")
    return {
        "inspection_summary": {
            "item": inspection["item"],
            "attachment_key": inspection["attachment_key"],
            "page_count": inspection["page_count"],
            "extraction_quality": inspection["extraction_quality"],
        },
        "selected_labels": selected_labels,
        "rendered": rendered,
        "next_step": "Open each image path with view_image and ground claims in what is visible on the rendered page.",
    }


def coverage_report(conn: sqlite3.Connection, key: str | None, query: str | None) -> dict[str, Any]:
    item_id = resolve_item(conn, key, query)
    item = item_brief(conn, item_id)
    state = load_coverage(item["key"])
    reads = state.get("text_reads", [])
    by_kind: dict[str, int] = {}
    for read in reads:
        kind = str(read.get("coverage_kind") or "tool-selected")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    totals = [read.get("total_chars") for read in reads if isinstance(read.get("total_chars"), int)]
    total_chars = max(totals) if totals else None
    intervals = coverage_intervals(reads)
    local_stats = interval_stats(intervals, total_chars)
    delivery_intervals = coverage_intervals(reads, "delivery-envelope-emitted")
    delivery_stats = interval_stats(delivery_intervals, total_chars)
    visual_entries = state.get("visual_pages", [])
    visual_pages = sorted({entry.get("page") for entry in visual_entries if entry.get("page")})
    inspected_pages = sorted(
        {entry.get("page") for entry in visual_entries if entry.get("page") and entry.get("visually_inspected")}
    )
    return {
        "item": item,
        "coverage_file": str(coverage_file(item["key"])),
        "text": {
            "total_chars": total_chars,
            "covered_chars": local_stats["covered_chars"],
            "covered_ratio": local_stats["covered_ratio"],
            "covered_intervals": local_stats["covered_intervals"],
            "gaps": local_stats["gaps"],
            "has_complete_local_fulltext_selection": any(
                read.get("scope") == "fulltext" and read.get("selection_complete") for read in reads
            ),
            "delivery_envelope": {
                "emitted_chars": delivery_stats["covered_chars"],
                "emitted_ratio": delivery_stats["covered_ratio"],
                "emitted_intervals": delivery_stats["covered_intervals"],
                "gaps": delivery_stats["gaps"],
                "complete_emission": total_chars is not None and not delivery_stats["gaps"],
                "receipt_rule": RECEIPT_RULE,
            },
            "coverage_kind_counts": by_kind,
            "coverage_warning": (
                "This records ranges selected/emitted by the local reader. Treat a delivery-window range as model-received "
                "only if BEGIN/END markers were visible and no tool-level truncation/omission notice appeared in command output."
            ),
        },
        "visual": {
            "pages_rendered": visual_pages,
            "rendered_count": len(visual_pages),
            "pages_visually_inspected": inspected_pages,
            "visually_inspected_count": len(inspected_pages),
            "image_paths": [entry.get("image_path") for entry in visual_entries if entry.get("image_path")],
        },
        "inspections": state.get("inspections", []),
        "policy": (
            "For normal paper summaries, complete full-text delivery requires visible BEGIN/END markers "
            "and no tool-level truncation/omission notice. Visual page inspection is optional and should be used "
            "only when requested or when the answer depends on visual-only evidence."
        ),
    }


def compact_notes(notes: list[dict[str, Any]], preview_chars: int = 800) -> list[dict[str, Any]]:
    out = []
    for note in notes:
        text = note.get("note") or ""
        out.append(
            {
                "key": note.get("key"),
                "title": note.get("title"),
                "chars": note.get("chars"),
                "truncated": note.get("truncated"),
                "preview": re.sub(r"\s+", " ", text[:preview_chars]).strip(),
            }
        )
    return out


def compact_attachments(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    attachments = []
    for attachment in item_attachments(conn, item_id, include_fulltext=False):
        cache, text = read_fulltext_cache(attachment["key"])
        attachments.append(
            {
                "key": attachment.get("key"),
                "contentType": attachment.get("contentType"),
                "path": attachment.get("path"),
                "resolved_path": attachment.get("resolved_path"),
                "fulltext_cache": {
                    "available": text is not None,
                    "cache_path": str(cache),
                    "chars": len(text) if text is not None else None,
                },
            }
        )
    return attachments


def chunk_plan(item_key: str, total_chars: int, chunk_size: int) -> list[dict[str, Any]]:
    if chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")
    chunks = []
    for start in range(0, total_chars, chunk_size):
        size = min(chunk_size, total_chars - start)
        chunks.append(
            {
                "start": start,
                "end": start + size,
                "chars": size,
                "recommended_exec_max_output_tokens": RECOMMENDED_EXEC_MAX_OUTPUT_TOKENS,
                "command": (
                    f"python3 scripts/zotero_read.py read-fulltext --key {item_key} "
                    f"--start {start} --chars {size} --delivery-window"
                ),
            }
        )
    return chunks


def evidence_commands(item_key: str, labels: list[dict[str, Any]]) -> list[str]:
    commands = []
    seen: set[tuple[str, str]] = set()
    priority = {"table": 0, "algorithm": 1, "equation": 2, "eq": 2, "figure": 3, "fig": 3}
    ordered = sorted(labels, key=lambda entry: (priority.get(str(entry.get("kind") or "").casefold(), 9), entry.get("page") or 0))
    for label in ordered:
        kind = str(label.get("kind") or "").casefold()
        number = str(label.get("number") or "")
        key = (kind, number)
        if key in seen:
            continue
        seen.add(key)
        if kind == "table":
            commands.append(
                f'python3 scripts/zotero_read.py read-tables --key {item_key} --label "Table {number}" --render-on-ambiguous'
            )
        elif kind in {"equation", "eq"}:
            commands.append(
                f'python3 scripts/zotero_read.py read-equations --key {item_key} --label "{number}" --render-on-ambiguous'
            )
        elif kind == "algorithm":
            commands.append(
                f'python3 scripts/zotero_read.py read-algorithms --key {item_key} --label "Algorithm {number}"'
            )
        if len(commands) >= 14:
            break
    return commands


def compact_coverage_summary(item_key: str, total_chars: int | None) -> dict[str, Any]:
    state = load_coverage(item_key)
    reads = state.get("text_reads", [])
    by_kind: dict[str, int] = {}
    for read in reads:
        kind = str(read.get("coverage_kind") or "tool-selected")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    intervals = coverage_intervals(reads)
    local_stats = interval_stats(intervals, total_chars)
    delivery_intervals = coverage_intervals(reads, "delivery-envelope-emitted")
    delivery_stats = interval_stats(delivery_intervals, total_chars)
    visual_entries = state.get("visual_pages", [])
    return {
        "coverage_file": str(coverage_file(item_key)),
        "text": {
            "total_chars": total_chars,
            "covered_chars": local_stats["covered_chars"],
            "covered_ratio": local_stats["covered_ratio"],
            "gaps": local_stats["gaps"],
            "has_complete_local_fulltext_selection": any(
                read.get("scope") == "fulltext" and read.get("selection_complete") for read in reads
            ),
            "delivery_envelope": {
                "emitted_chars": delivery_stats["covered_chars"],
                "emitted_ratio": delivery_stats["covered_ratio"],
                "gaps": delivery_stats["gaps"],
                "complete_emission": total_chars is not None and not delivery_stats["gaps"],
                "receipt_rule": RECEIPT_RULE,
            },
            "coverage_kind_counts": by_kind,
            "warning": (
                "This is a local selection/emission ledger. Treat delivery windows as received only when BEGIN/END "
                "markers were visible and no tool-level truncation/omission notice appeared in command output."
            ),
        },
        "visual": {
            "rendered_pages": sorted({entry.get("page") for entry in visual_entries if entry.get("page")}),
            "visually_inspected_pages": sorted(
                {entry.get("page") for entry in visual_entries if entry.get("page") and entry.get("visually_inspected")}
            ),
        },
    }


def compact_pdf_inspection(inspection: dict[str, Any]) -> dict[str, Any]:
    if "error" in inspection:
        return inspection
    return {
        "attachment_key": inspection.get("attachment_key"),
        "pdf_path": inspection.get("pdf_path"),
        "tools": inspection.get("tools"),
        "parser": inspection.get("parser"),
        "page_count": inspection.get("page_count"),
        "extraction_quality": inspection.get("extraction_quality"),
        "page_summaries": inspection.get("page_summaries", [])[:8],
        "figure_table_index_count": len(inspection.get("figure_table_index", [])),
        "figure_table_index_truncated": inspection.get("figure_table_index_truncated"),
        "notes": inspection.get("notes"),
    }


def read_paper_packet(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    collection: str | None,
    recursive: bool,
    mode: str,
    chunk_size: int,
    emit_fulltext: bool,
    include_evidence_index: bool,
    include_pdf_inspect: bool,
    max_emit_chars: int,
    include_ledger: bool,
    record_ledger: bool,
) -> dict[str, Any]:
    if mode != "audit":
        raise SystemExit("Only --mode audit is currently supported")
    item_id, resolution = resolve_paper_item(conn, key, query, collection, recursive)
    item = item_brief(conn, item_id)
    attachments = compact_attachments(conn, item_id)
    notes = compact_notes(item_notes(conn, item_id))
    selected_attachment_key = None
    cache_path = None
    text = None
    fulltext_error = None
    try:
        selected_attachment_key = resolve_attachment_key(conn, item_id, None)
        cache_path, text = read_fulltext_cache(selected_attachment_key)
    except SystemExit as exc:
        fulltext_error = str(exc)

    fulltext_status: dict[str, Any] = {
        "available": text is not None,
        "attachment_key": selected_attachment_key,
        "cache_path": str(cache_path) if cache_path else None,
        "total_chars": len(text) if text is not None else None,
        "fulltext_sha256": text_sha256(text) if text is not None else None,
        "emit_fulltext_requested": emit_fulltext,
        "emit_fulltext_complete": False,
        "safe_direct_emit_max_chars": max_emit_chars,
        "recommended_exec_max_output_tokens": RECOMMENDED_EXEC_MAX_OUTPUT_TOKENS,
        "delivery_policy": (
            "Direct stdout full-text is used only within the safe emit limit. "
            "For longer papers, read every delivery-window command and verify BEGIN/END markers are visible "
            "with no tool-level truncation/omission notice."
        ),
        "chunk_size": chunk_size,
        "chunk_count": 0,
        "error": fulltext_error,
        "warning": (
            "Model receipt is session-local: verify delivery-window BEGIN/END markers in the current command output "
            "and reject any output showing a tool-level truncation/omission notice."
        ),
    }
    outline = []
    chunks: list[dict[str, Any]] = []
    fulltext_payload = None
    if text is not None:
        outline = fulltext_outline(text)
        chunks = chunk_plan(item["key"], len(text), chunk_size)
        fulltext_status["chunk_count"] = len(chunks)
        if emit_fulltext and (max_emit_chars < 0 or len(text) <= max_emit_chars):
            fulltext_payload = text
            fulltext_status["emit_fulltext_complete"] = True
            if record_ledger:
                record_text_read(
                    item["key"],
                    {
                        "scope": "fulltext",
                        "start": 0,
                        "end": len(text),
                        "total_chars": len(text),
                        "selection_complete": True,
                        "source": "read-paper --emit-fulltext",
                    },
                )
        elif emit_fulltext:
            fulltext_status["emit_fulltext_refused_reason"] = (
                f"Full text has {len(text)} chars, exceeding --max-emit-chars {max_emit_chars}."
            )
            fulltext_status["emit_fulltext_complete"] = False
            fulltext_status["delivery_required"] = True

    pdf = next(
        (
            attachment
            for attachment in attachments
            if attachment.get("contentType") == "application/pdf"
            or str(attachment.get("resolved_path") or "").casefold().endswith(".pdf")
        ),
        None,
    )
    labels: list[dict[str, Any]] = []
    label_error = None
    label_index_source = None
    if include_evidence_index:
        try:
            pdf = resolve_pdf_attachment(conn, item_id, None)
            page_texts = pdftotext_pages(pdf["resolved_path"])
            if not page_texts:
                fitz_data = fitz_pages(pdf["resolved_path"])
                page_texts = [page["text"] for page in fitz_data] if fitz_data else []
            labels = page_evidence_index(page_texts) if page_texts else []
            label_index_source = "pdftotext -layout"
        except SystemExit as exc:
            label_error = str(exc)

    inspection = None
    if include_pdf_inspect:
        try:
            inspection = inspect_pdf(conn, item["key"], None, pdf.get("key") if pdf else None, record_ledger)
        except SystemExit as exc:
            inspection = {"error": str(exc)}

    evidence_suggestion = (
        {"suggested": False, "reason": None, "message": None}
        if include_evidence_index
        else evidence_index_suggestion(text, outline, pdf is not None)
    )
    out = {
        "mode": mode,
        "resolution": resolution,
        "item": item,
        "attachments": attachments,
        "notes": notes,
        "reading_scope": {
            "default": "audit deep read",
            "visual_reading": "not performed by read-paper",
            "summary_policy": (
                "Do not summarize until full text has either been directly emitted within the safe limit "
                "or every delivery-window command has been read with BEGIN/END markers visible and no tool-level truncation/omission notice."
            ),
        },
        "fulltext_status": fulltext_status,
        "outline": outline,
        "chunk_plan": chunks,
        "pdf": {
            "attachment_key": pdf.get("key") if pdf else None,
            "path": pdf.get("resolved_path") if pdf else None,
            "label_index_enabled": include_evidence_index,
            "label_index_source": label_index_source,
            "label_index_error": label_error,
        },
        "evidence_hints": {
            "generated": include_evidence_index,
            "labels": labels[:60],
            "labels_truncated": len(labels) > 60,
            "index_suggestion": evidence_suggestion,
            "policy": "Use --include-evidence-index or dedicated table/equation/algorithm commands before relying on metrics, objectives, or pseudocode.",
        },
        "recommended_commands": evidence_commands(item["key"], labels),
        "next_steps": [
            "If fulltext_status.emit_fulltext_complete is false, run chunk_plan commands in order and verify every BEGIN/END marker pair with no tool-level truncation/omission notice before summarizing.",
            "Use --include-evidence-index only when figure/table/equation/algorithm label hints are needed.",
            "Use read-tables/read-equations/read-algorithms for claims that depend on metrics, formulas, or pseudocode.",
            "Use render-pages/view_image only when visual evidence is requested or extraction is ambiguous.",
        ],
    }
    if inspection is not None:
        out["pdf_inspection"] = compact_pdf_inspection(inspection)
    if include_ledger:
        out["historical_ledger"] = compact_coverage_summary(item["key"], len(text) if text is not None else None)
    if fulltext_payload is not None:
        out["fulltext"] = fulltext_payload
    return out


def mark_visual_read(
    conn: sqlite3.Connection,
    key: str | None,
    query: str | None,
    pages: str,
    note: str | None,
) -> dict[str, Any]:
    item_id = resolve_item(conn, key, query)
    item = item_brief(conn, item_id)
    state = load_coverage(item["key"])
    page_nums = parse_pages(pages)
    image_by_page: dict[int, str] = {}
    for entry in state.get("visual_pages", []):
        page = entry.get("page")
        image_path = entry.get("image_path")
        if isinstance(page, int) and image_path:
            image_by_page[page] = image_path
    missing = [page for page in page_nums if page not in image_by_page]
    if missing:
        raise SystemExit(f"Pages have not been rendered yet: {missing}. Run render-pages first.")
    image_paths = [image_by_page[page] for page in page_nums]
    record_visual_pages(item["key"], page_nums, image_paths, "mark-visual-read", inspected=True, note=note)
    return {
        "item": item,
        "pages_visually_inspected": page_nums,
        "image_paths": image_paths,
        "note": note,
    }


def synthesize_collection_manifest(conn: sqlite3.Connection, path: str, recursive: bool, limit: int) -> dict[str, Any]:
    coll = find_collection(conn, path)
    items = collection_items(conn, coll["collectionID"], recursive, limit, brief=True)
    manifest = []
    for item in items:
        state = load_coverage(item["key"])
        reads = state.get("text_reads", [])
        local_fulltext_selected = any(read.get("scope") == "fulltext" and read.get("selection_complete") for read in reads)
        delivery_intervals = coverage_intervals(reads, "delivery-envelope-emitted")
        visual_pages = sorted({entry.get("page") for entry in state.get("visual_pages", []) if entry.get("page")})
        inspected_pages = sorted(
            {entry.get("page") for entry in state.get("visual_pages", []) if entry.get("page") and entry.get("visually_inspected")}
        )
        manifest.append(
            {
                "key": item["key"],
                "title": item.get("title"),
                "creators": item.get("creators", []),
                "attachmentCount": item.get("attachmentCount"),
                "noteCount": item.get("noteCount"),
                "coverage": {
                    "local_fulltext_selected": local_fulltext_selected,
                    "delivery_envelope_intervals": [{"start": s, "end": e} for s, e in delivery_intervals],
                    "visual_pages_rendered": visual_pages,
                    "visual_pages_inspected": inspected_pages,
                },
                "recommended_commands": [
                    f"python3 scripts/zotero_read.py read-paper --key {item['key']} --emit-fulltext",
                    f"python3 scripts/zotero_read.py read-fulltext --key {item['key']} --outline --chars 2000",
                    f"python3 scripts/zotero_read.py inspect-pdf --key {item['key']}",
                    f"python3 scripts/zotero_read.py read-figures --key {item['key']} --auto",
                    f"python3 scripts/zotero_read.py reading-coverage --key {item['key']}",
                ],
            }
        )
    return {
        "collection": coll,
        "recursive": recursive,
        "items": manifest,
        "synthesis_policy": "Deep-read each item before comparing claims, methods, experiments, limitations, and open questions. Use visual inspection only when requested or when text/captions are insufficient.",
    }


def emit(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-collections")

    p_search = sub.add_parser("search-items")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=10)

    p_find = sub.add_parser("find-items")
    p_find.add_argument("--query", required=True)
    p_find.add_argument("--collection")
    p_find.add_argument("--recursive", action="store_true")
    p_find.add_argument("--limit", type=int, default=10)

    p_paper = sub.add_parser("read-paper")
    p_paper.add_argument("--key")
    p_paper.add_argument("--query")
    p_paper.add_argument("--collection")
    p_paper.add_argument("--recursive", action="store_true")
    p_paper.add_argument("--mode", default="audit", choices=["audit"])
    p_paper.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    p_paper.add_argument("--emit-fulltext", action="store_true")
    p_paper.add_argument(
        "--include-evidence-index",
        action="store_true",
        help="Generate figure/table/equation/algorithm label hints from the PDF layout layer.",
    )
    p_paper.add_argument("--include-pdf-inspect", action="store_true")
    p_paper.add_argument("--max-emit-chars", type=int, default=MAX_EMIT_FULLTEXT_CHARS)
    p_paper.add_argument(
        "--include-ledger",
        action="store_true",
        help="Include the persistent historical ledger in the output; debug/resume only.",
    )
    p_paper.add_argument(
        "--record-ledger",
        action="store_true",
        help="Record this command in the persistent historical ledger; debug/resume only.",
    )

    p_item = sub.add_parser("read-item")
    p_item.add_argument("--key")
    p_item.add_argument("--query")
    p_item.add_argument("--fulltext", action="store_true")
    p_item.add_argument("--fulltext-start", type=int, default=0)
    p_item.add_argument(
        "--fulltext-limit",
        type=int,
        default=TEXT_LIMIT,
        help="Characters of each full-text cache to include; use -1 for the entire cache.",
    )

    p_fulltext = sub.add_parser("read-fulltext")
    p_fulltext.add_argument("--key")
    p_fulltext.add_argument("--query")
    p_fulltext.add_argument("--attachment-key")
    p_fulltext.add_argument("--start", type=int, default=0)
    p_fulltext.add_argument(
        "--chars",
        type=int,
        default=-1,
        help="Characters to read from the selected body/section; default -1 reads the full selection.",
    )
    p_fulltext.add_argument("--section")
    p_fulltext.add_argument("--search")
    p_fulltext.add_argument("--context", type=int, default=SEARCH_CONTEXT)
    p_fulltext.add_argument("--matches", type=int, default=5)
    p_fulltext.add_argument("--outline", action="store_true")
    p_fulltext.add_argument(
        "--text-only",
        action="store_true",
        help="Emit only the selected full-text window, without JSON metadata.",
    )
    p_fulltext.add_argument(
        "--delivery-window",
        action="store_true",
        help="Emit a single text window with BEGIN/END markers and hashes; use this for truncation-safe full-paper delivery.",
    )
    p_fulltext.add_argument(
        "--record-ledger",
        action="store_true",
        help="Record this command in the persistent historical ledger; debug/resume only.",
    )

    p_inspect = sub.add_parser("inspect-pdf")
    p_inspect.add_argument("--key")
    p_inspect.add_argument("--query")
    p_inspect.add_argument("--attachment-key")
    p_inspect.add_argument("--record-ledger", action="store_true", help="Record this inspection in the persistent historical ledger.")

    p_render = sub.add_parser("render-pages")
    p_render.add_argument("--key")
    p_render.add_argument("--query")
    p_render.add_argument("--attachment-key")
    p_render.add_argument("--pages", required=True, help="1-based pages, e.g. 3,5-7")
    p_render.add_argument("--dpi", type=int, default=180)
    p_render.add_argument("--record-ledger", action="store_true", help="Record rendered pages in the persistent historical ledger.")

    p_figures = sub.add_parser("read-figures")
    p_figures.add_argument("--key")
    p_figures.add_argument("--query")
    p_figures.add_argument("--attachment-key")
    p_figures.add_argument("--auto", action="store_true")
    p_figures.add_argument("--pages", help="Optional explicit 1-based pages, e.g. 3,5-7")
    p_figures.add_argument("--max-pages", type=int, default=8)
    p_figures.add_argument("--dpi", type=int, default=180)
    p_figures.add_argument("--record-ledger", action="store_true", help="Record inspection/rendering in the persistent historical ledger.")

    p_tables = sub.add_parser("read-tables")
    p_tables.add_argument("--key")
    p_tables.add_argument("--query")
    p_tables.add_argument("--attachment-key")
    p_tables.add_argument("--label", help='Optional label, e.g. "Table 2" or "2"')
    p_tables.add_argument("--pages", help="Optional explicit 1-based pages, e.g. 9-11")
    p_tables.add_argument("--context-chars", type=int, default=-1, help="Default -1 returns the full table page text.")
    p_tables.add_argument(
        "--render-on-ambiguous",
        action="store_true",
        help="Render ambiguous table pages for visual inspection.",
    )
    p_tables.add_argument("--dpi", type=int, default=180)

    p_equations = sub.add_parser("read-equations")
    p_equations.add_argument("--key")
    p_equations.add_argument("--query")
    p_equations.add_argument("--attachment-key")
    p_equations.add_argument("--label", help='Optional equation number, e.g. "3"')
    p_equations.add_argument("--pages", help="Optional explicit 1-based pages, e.g. 3-5")
    p_equations.add_argument("--context-lines", type=int, default=5)
    p_equations.add_argument(
        "--render-on-ambiguous",
        action="store_true",
        help="Render ambiguous equation pages for visual inspection.",
    )
    p_equations.add_argument("--dpi", type=int, default=180)

    p_algorithms = sub.add_parser("read-algorithms")
    p_algorithms.add_argument("--key")
    p_algorithms.add_argument("--query")
    p_algorithms.add_argument("--attachment-key")
    p_algorithms.add_argument("--label", help='Optional label, e.g. "Algorithm 1" or "1"')
    p_algorithms.add_argument("--pages", help="Optional explicit 1-based pages, e.g. 7")
    p_algorithms.add_argument("--context-lines", type=int, default=40)

    p_coverage = sub.add_parser("reading-coverage")
    p_coverage.add_argument("--key")
    p_coverage.add_argument("--query")

    p_mark_visual = sub.add_parser("mark-visual-read")
    p_mark_visual.add_argument("--key")
    p_mark_visual.add_argument("--query")
    p_mark_visual.add_argument("--pages", required=True)
    p_mark_visual.add_argument("--note")

    p_synth = sub.add_parser("synthesize-collection")
    p_synth.add_argument("--path", required=True)
    p_synth.add_argument("--recursive", action="store_true")
    p_synth.add_argument("--limit", type=int, default=20)

    p_coll = sub.add_parser("read-collection")
    p_coll.add_argument("--path", required=True)
    p_coll.add_argument("--recursive", action="store_true")
    p_coll.add_argument("--fulltext", action="store_true")
    p_coll.add_argument("--fulltext-start", type=int, default=0)
    p_coll.add_argument(
        "--fulltext-limit",
        type=int,
        default=TEXT_LIMIT,
        help="Characters of each full-text cache to include; use -1 for the entire cache.",
    )
    p_coll.add_argument("--brief", action="store_true")
    p_coll.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()
    conn = connect()
    try:
        if args.cmd == "list-collections":
            emit(collection_paths(conn))
        elif args.cmd == "search-items":
            emit(search_items(conn, args.query, args.limit))
        elif args.cmd == "find-items":
            emit(find_items(conn, args.query, args.limit, args.collection, args.recursive))
        elif args.cmd == "read-paper":
            emit(
                read_paper_packet(
                    conn,
                    args.key,
                    args.query,
                    args.collection,
                    args.recursive,
                    args.mode,
                    args.chunk_size,
                    args.emit_fulltext,
                    args.include_evidence_index,
                    args.include_pdf_inspect,
                    args.max_emit_chars,
                    args.include_ledger,
                    args.record_ledger,
                )
            )
        elif args.cmd == "read-item":
            item_id = resolve_item(conn, args.key, args.query)
            emit(
                item_summary(
                    conn,
                    item_id,
                    include_fulltext=args.fulltext,
                    fulltext_limit=args.fulltext_limit,
                    fulltext_start=args.fulltext_start,
                )
            )
        elif args.cmd == "read-fulltext":
            result = read_fulltext(
                conn,
                args.key,
                args.query,
                args.attachment_key,
                args.start,
                args.chars,
                args.section,
                args.search,
                args.context,
                args.matches,
                args.outline,
                args.text_only,
                args.delivery_window,
                args.record_ledger,
            )
            if args.delivery_window:
                print(format_delivery_window(result))
            elif args.text_only:
                print(result["window"]["text"])
            else:
                emit(result)
        elif args.cmd == "inspect-pdf":
            emit(inspect_pdf(conn, args.key, args.query, args.attachment_key, args.record_ledger))
        elif args.cmd == "render-pages":
            emit(render_pdf_pages(conn, args.key, args.query, args.attachment_key, args.pages, args.dpi, args.record_ledger))
        elif args.cmd == "read-figures":
            if not args.auto and not args.pages:
                raise SystemExit("Provide --auto or --pages")
            emit(read_figures(conn, args.key, args.query, args.attachment_key, args.pages, args.max_pages, args.dpi, args.record_ledger))
        elif args.cmd == "read-tables":
            emit(
                read_tables(
                    conn,
                    args.key,
                    args.query,
                    args.attachment_key,
                    args.label,
                    args.pages,
                    args.context_chars,
                    args.render_on_ambiguous,
                    args.dpi,
                )
            )
        elif args.cmd == "read-equations":
            emit(
                read_equations(
                    conn,
                    args.key,
                    args.query,
                    args.attachment_key,
                    args.label,
                    args.pages,
                    args.context_lines,
                    args.render_on_ambiguous,
                    args.dpi,
                )
            )
        elif args.cmd == "read-algorithms":
            emit(read_algorithms(conn, args.key, args.query, args.attachment_key, args.label, args.pages, args.context_lines))
        elif args.cmd == "reading-coverage":
            emit(coverage_report(conn, args.key, args.query))
        elif args.cmd == "mark-visual-read":
            emit(mark_visual_read(conn, args.key, args.query, args.pages, args.note))
        elif args.cmd == "synthesize-collection":
            emit(synthesize_collection_manifest(conn, args.path, args.recursive, args.limit))
        elif args.cmd == "read-collection":
            coll = find_collection(conn, args.path)
            items = collection_items(conn, coll["collectionID"], args.recursive, args.limit, args.brief)
            if args.fulltext:
                items = [
                    item_summary(
                        conn,
                        item["itemID"],
                        include_fulltext=True,
                        fulltext_limit=args.fulltext_limit,
                        fulltext_start=args.fulltext_start,
                    )
                    for item in items
                ]
            emit({"collection": coll, "recursive": args.recursive, "items": items})
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
