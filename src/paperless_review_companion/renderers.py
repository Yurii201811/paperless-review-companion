from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from typing import Any

from .manifest import document_of, review_of


def cell(value: Any, max_len: int = 180) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    text = " ".join(str(value).replace("|", "/").split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    return lines


def confidence(row: dict[str, Any]) -> float:
    try:
        return float(review_of(row).get("confidence"))
    except (TypeError, ValueError):
        return 0.0


def needs_attention(row: dict[str, Any]) -> bool:
    review = review_of(row)
    return (
        row.get("status") != "reviewed"
        or bool(review.get("needs_manual_review"))
        or confidence(row) < 0.75
        or bool(review.get("action_needed"))
        or review.get("keep_in_paperless") is False
    )


def render_full_report(source: str, rows: list[dict[str, Any]]) -> str:
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    categories = Counter(review_of(row).get("primary_category") or "missing" for row in rows)
    sensitivities = Counter(review_of(row).get("sensitivity") or "missing" for row in rows)
    doc_types = Counter(review_of(row).get("document_type") or "missing" for row in rows)
    statuses = Counter(row.get("status") or "missing" for row in rows)
    attention = [row for row in rows if needs_attention(row)]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[review_of(row).get("primary_category") or "missing"].append(row)

    lines = [
        "# Paperless Review Report",
        "",
        f"Generated: {now}",
        f"Source manifest: `{source}`",
        "",
        "This report is manifest-only. It does not change Paperless.",
        "",
        "## Overview",
        "",
        f"- Documents reviewed: {len(rows)}",
        f"- Rows needing attention: {len(attention)}",
        f"- Rows suggesting action: {sum(1 for row in rows if review_of(row).get('action_needed'))}",
        f"- Rows suggesting not to keep: {sum(1 for row in rows if review_of(row).get('keep_in_paperless') is False)}",
        "",
        "## Counts",
        "",
        *table(["Status", "Count"], statuses.most_common()),
        "",
        *table(["Category", "Count"], categories.most_common()),
        "",
        *table(["Sensitivity", "Count"], sensitivities.most_common()),
        "",
        *table(["Document type", "Count"], doc_types.most_common(30)),
        "",
        "## Needs Attention",
        "",
    ]
    if attention:
        lines.extend(
            table(
                ["ID", "Category", "Type", "Sensitivity", "Confidence", "Reason", "Summary", "Title"],
                [
                    [
                        document_of(row).get("id"),
                        review_of(row).get("primary_category"),
                        review_of(row).get("document_type"),
                        review_of(row).get("sensitivity"),
                        confidence(row),
                        review_of(row).get("action_reason") or review_of(row).get("rationale"),
                        review_of(row).get("summary"),
                        document_of(row).get("title"),
                    ]
                    for row in attention
                ],
            )
        )
    else:
        lines.append("No rows need attention.")

    lines.extend(["", "## Documents By Category", ""])
    for category in sorted(groups):
        lines.extend([f"### {category}", ""])
        lines.extend(
            table(
                ["ID", "Type", "Sensitivity", "Confidence", "Title", "Summary", "Suggested tags"],
                [
                    [
                        document_of(row).get("id"),
                        review_of(row).get("document_type"),
                        review_of(row).get("sensitivity"),
                        confidence(row),
                        document_of(row).get("title"),
                        review_of(row).get("summary"),
                        review_of(row).get("suggested_tags"),
                    ]
                    for row in groups[category]
                ],
            )
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


IMPORTANT_CATEGORIES = {"legal", "finance_tax", "identity", "health_personal", "housing_travel"}
NOISE_CATEGORIES = {"media", "learning_books"}


def priority(row: dict[str, Any]) -> tuple[int, str]:
    review = review_of(row)
    category = review.get("primary_category") or "missing"
    sensitivity = review.get("sensitivity") or "missing"
    text = " ".join(
        str(value or "")
        for value in (
            document_of(row).get("title"),
            document_of(row).get("original_filename"),
            review.get("summary"),
            review.get("action_reason"),
            " ".join(review.get("suggested_tags") or []),
        )
    ).lower()
    urgent = any(term in text for term in ("deadline", "due", "overdue", "expires", "court", "claim", "payment"))
    if row.get("status") != "reviewed":
        return 1, "model error"
    if sensitivity == "highly_sensitive" or category == "identity":
        return 1, "identity or highly sensitive"
    if category in {"legal", "finance_tax"} and urgent:
        return 1, "urgent legal/finance signal"
    if review.get("action_needed") and category in IMPORTANT_CATEGORIES:
        return 1, "important action suggestion"
    if category in IMPORTANT_CATEGORIES:
        return 2, "important category"
    if needs_attention(row) and category not in NOISE_CATEGORIES:
        return 2, "manual review outside archive-only categories"
    if needs_attention(row):
        return 3, "low-confidence archive item"
    return 4, "archive-only"


def render_triage(source: str, rows: list[dict[str, Any]], max_rows: int = 75) -> str:
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rank, _ = priority(row)
        buckets[rank].append(row)
    for rank in buckets:
        buckets[rank].sort(key=lambda row: (-confidence(row), document_of(row).get("id") or 0))

    lines = [
        "# Paperless Executive Triage",
        "",
        f"Generated: {now}",
        f"Source manifest: `{source}`",
        "",
        "## What To Do",
        "",
        "1. Review Tier 1 first.",
        "2. Use Tier 2 for a second pass.",
        "3. Treat Tier 3 and archive-only rows as lower-priority unless searching for something specific.",
        "",
        "## Overview",
        "",
        f"- Documents: {len(rows)}",
        f"- Tier 1: {len(buckets[1])}",
        f"- Tier 2: {len(buckets[2])}",
        f"- Tier 3: {len(buckets[3])}",
        f"- Archive-only: {len(buckets[4])}",
        "",
        "## Tier 1: Review First",
        "",
    ]
    for title, rank in (("Tier 1: Review First", 1), ("Tier 2: Important Second Pass", 2)):
        if rank != 1:
            lines.extend(["", f"## {title}", ""])
        selected = buckets[rank][:max_rows]
        if not selected:
            lines.append(f"No {title.lower()} rows.")
            continue
        lines.extend(
            table(
                ["ID", "Category", "Type", "Sensitivity", "Confidence", "Why", "Summary", "Title"],
                [
                    [
                        document_of(row).get("id"),
                        review_of(row).get("primary_category"),
                        review_of(row).get("document_type"),
                        review_of(row).get("sensitivity"),
                        confidence(row),
                        priority(row)[1],
                        review_of(row).get("summary"),
                        document_of(row).get("title"),
                    ]
                    for row in selected
                ],
            )
        )
    lines.extend(["", "## Lower Priority Summary", ""])
    lines.extend(table(["Bucket", "Count"], [["Tier 3", len(buckets[3])], ["Archive-only", len(buckets[4])]]))
    return "\n".join(lines).rstrip() + "\n"


def render_focus(source: str, rows: list[dict[str, Any]], limit: int = 100) -> str:
    selected = sorted(rows, key=lambda row: (priority(row)[0], -confidence(row), document_of(row).get("id") or 0))
    selected = [row for row in selected if priority(row)[0] <= 2][:limit]
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# Paperless Focus Queue",
        "",
        f"Generated: {now}",
        f"Source manifest: `{source}`",
        "",
        "This is the smallest practical review surface from the manifest.",
        "",
        "## Summary",
        "",
        f"- Documents considered: {len(rows)}",
        f"- Focus queue size: {len(selected)}",
        "",
        "## Focus Queue",
        "",
        *table(
            ["ID", "Why", "Category", "Type", "Sensitivity", "Confidence", "Summary", "Title"],
            [
                [
                    document_of(row).get("id"),
                    priority(row)[1],
                    review_of(row).get("primary_category"),
                    review_of(row).get("document_type"),
                    review_of(row).get("sensitivity"),
                    confidence(row),
                    review_of(row).get("summary"),
                    document_of(row).get("title"),
                ]
                for row in selected
            ],
        ),
    ]
    return "\n".join(lines).rstrip() + "\n"

