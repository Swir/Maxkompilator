#!/usr/bin/env python3
"""Validate weighted roadmap evidence and synchronize its Markdown views.

Only completed criteria earn their fixed integer weight. The JSON file is the
single source of truth; --check makes uncommitted documentation drift a CI error.
This script uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys
from typing import Any


START = "<!-- MAXKOMPILATOR:PROGRESS:START -->"
END = "<!-- MAXKOMPILATOR:PROGRESS:END -->"
DOCUMENTS = ("README.md", "ROADMAP.md")
STATUSES = {"pending", "in_progress", "complete"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*\Z")


class ProgressError(ValueError):
    """The progress source or one of its generated documents is invalid."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProgressError(f"{label}: expected nonempty text")
    if "\n" in value or "\r" in value or START in value or END in value:
        raise ProgressError(f"{label}: text must be one line without progress markers")
    return value


def _weight(value: Any, label: str) -> int:
    if type(value) is not int or not 0 < value <= 100:
        raise ProgressError(f"{label}: weight must be an integer from 1 to 100")
    return value


def validate_progress(data: Any) -> dict[str, Any]:
    """Reject unsupported schemas, unbalanced weights and unsupported claims."""
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ProgressError("Expected an object with schema_version = 1")
    if data["schema_version"] != 1:
        raise ProgressError("Only schema_version = 1 is supported")
    for key in ("project", "release", "scope"):
        _text(data.get(key), key)
    try:
        date = _text(data.get("updated"), "updated")
        if dt.date.fromisoformat(date).isoformat() != date:
            raise ValueError
    except ValueError as exc:
        raise ProgressError("updated must use YYYY-MM-DD format") from exc

    milestones = data.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        raise ProgressError("milestones must contain at least one milestone")
    seen_milestones: set[str] = set()
    total = 0
    for milestone in milestones:
        if not isinstance(milestone, dict):
            raise ProgressError("A milestone must be an object")
        mid = _text(milestone.get("id"), "milestone.id")
        if not IDENTIFIER.fullmatch(mid) or mid in seen_milestones:
            raise ProgressError(f"Invalid or duplicate milestone identifier: {mid}")
        seen_milestones.add(mid)
        _text(milestone.get("title"), f"{mid}.title")
        weight = _weight(milestone.get("weight"), f"{mid}.weight")
        total += weight
        items = milestone.get("items")
        if not isinstance(items, list) or not items:
            raise ProgressError(f"{mid}: a milestone must contain criteria")
        seen_items: set[str] = set()
        subtotal = 0
        for item in items:
            if not isinstance(item, dict):
                raise ProgressError(f"{mid}: a criterion must be an object")
            iid = _text(item.get("id"), f"{mid}.item.id")
            label = f"{mid}.{iid}"
            if not IDENTIFIER.fullmatch(iid) or iid in seen_items:
                raise ProgressError(f"Invalid or duplicate identifier: {label}")
            seen_items.add(iid)
            _text(item.get("title"), f"{label}.title")
            subtotal += _weight(item.get("weight"), f"{label}.weight")
            status = item.get("status")
            if not isinstance(status, str) or status not in STATUSES:
                raise ProgressError(f"{label}: status must be pending, in_progress or complete")
            evidence = item.get("evidence")
            if not isinstance(evidence, list):
                raise ProgressError(f"{label}: evidence must be a list")
            for entry in evidence:
                _text(entry, f"{label}.evidence")
            if status == "complete" and not evidence:
                raise ProgressError(f"{label}: a completed criterion requires evidence")
        if subtotal != weight:
            raise ProgressError(f"{mid}: criterion weights total {subtotal}, but the milestone weight is {weight}")
    if total != 100:
        raise ProgressError(f"Milestone weights must total 100; received {total}")
    future = data.get("future", [])
    if not isinstance(future, list):
        raise ProgressError("future must be a list")
    for entry in future:
        _text(entry, "future")
    return data


def load_progress(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProgressError(f"Invalid JSON: {path}: {exc.msg}") from exc
    return validate_progress(data)


def earned_weight(milestone: dict[str, Any]) -> int:
    return sum(item["weight"] for item in milestone["items"] if item["status"] == "complete")


def total_progress(data: dict[str, Any]) -> int:
    validate_progress(data)
    return sum(earned_weight(milestone) for milestone in data["milestones"])


def _percentage(earned: int, weight: int) -> str:
    return f"{earned * 100 / weight:.1f}".removesuffix(".0") + "%"


def _table_text(value: str) -> str:
    return value.replace("|", "\\|")


def render_progress(data: dict[str, Any], *, details: bool = False) -> str:
    progress = total_progress(data)
    lines = [
        f"**v{data['release']} progress: {progress}% — {progress} / 100 points.**",
        "",
        "Only completed criteria with recorded evidence earn points. "
        "Work in progress does not increase the percentage.",
        "",
        "| Milestone | v1 weight | Earned | Milestone progress |",
        "|---|---:|---:|---:|",
    ]
    for milestone in data["milestones"]:
        earned = earned_weight(milestone)
        weight = milestone["weight"]
        lines.append(
            f"| {_table_text(milestone['title'])} | {weight} pts | {earned} / {weight} pts "
            f"| {_percentage(earned, weight)} |"
        )
    lines += [
        f"| **Total** | **100 pts** | **{progress} / 100 pts** | **{progress}%** |",
        "",
        f"Source: [docs/progress.json](docs/progress.json) · last updated: **{data['updated']}**.",
    ]
    if details:
        lines += ["", "### Criteria and evidence", ""]
        for milestone in data["milestones"]:
            lines += [f"#### {milestone['title']} — {milestone['weight']} points", ""]
            for item in milestone["items"]:
                mark = "x" if item["status"] == "complete" else " "
                unit = "point" if item["weight"] == 1 else "points"
                line = f"- [{mark}] **{item['title']} — {item['weight']} {unit}.**"
                if item["status"] == "complete":
                    line += " Evidence: " + "; ".join(item["evidence"]) + "."
                elif item["status"] == "in_progress":
                    line += " In progress; points are awarded after the full criterion is met."
                else:
                    line += " Planned."
                line += f" ID: `{milestone['id']}.{item['id']}`."
                lines.append(line)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def replace_block(content: str, generated: str, filename: str) -> str:
    if content.count(START) != 1 or content.count(END) != 1:
        raise ProgressError(f"{filename}: exactly one pair of progress markers is required")
    start = content.index(START) + len(START)
    end = content.index(END)
    if end < start:
        raise ProgressError(f"{filename}: the end marker appears before the start marker")
    return content[:start] + "\n\n" + generated + "\n" + content[end:]


def sync_progress(root: Path, *, check: bool = False) -> list[str]:
    data = load_progress(root / "docs" / "progress.json")
    changes: dict[str, str] = {}
    # Validate every document before writing any of them.
    for filename in DOCUMENTS:
        original = (root / filename).read_text(encoding="utf-8")
        generated = render_progress(data, details=filename == "ROADMAP.md")
        updated = replace_block(original, generated, filename)
        if original != updated:
            changes[filename] = updated
    if not check:
        for filename, content in changes.items():
            (root / filename).write_text(content, encoding="utf-8", newline="\n")
    return list(changes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check consistency without changing files")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Repository root directory")
    args = parser.parse_args(argv)
    try:
        changes = sync_progress(args.root, check=args.check)
    except (OSError, UnicodeError, ProgressError) as exc:
        print(f"Progress error: {exc}", file=sys.stderr)
        return 2
    if changes and args.check:
        print("Outdated progress block: " + ", ".join(changes), file=sys.stderr)
        print("Run: python scripts/update_progress.py", file=sys.stderr)
        return 1
    print("Updated: " + ", ".join(changes) if changes else "Progress is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
