from __future__ import annotations

import os
from collections import Counter
from typing import Any

from .client import PaperlessClient
from .constants import CONTROLLED_TAG_PREFIX
from .manifest import document_of, review_of


def clean_label(value: Any, fallback: str = "missing") -> str:
    text = str(value or fallback).strip().lower().replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char in "_-")[:64] or fallback


def tags_for_review(review: dict[str, Any], prefix: str = CONTROLLED_TAG_PREFIX) -> list[str]:
    tags = [
        f"{prefix}:reviewed",
        f"{prefix}:no_delete",
        f"{prefix}:category:{clean_label(review.get('primary_category'))}",
        f"{prefix}:type:{clean_label(review.get('document_type'))}",
        f"{prefix}:sensitivity:{clean_label(review.get('sensitivity'))}",
    ]
    if review.get("action_needed"):
        tags.append(f"{prefix}:action_needed")
    if review.get("needs_manual_review"):
        tags.append(f"{prefix}:manual_review")
    return sorted(dict.fromkeys(tags))


def plan_rows(rows: list[dict[str, Any]], *, prefix: str = CONTROLLED_TAG_PREFIX) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for row in rows:
        document = document_of(row)
        review = review_of(row)
        confidence = float(review.get("confidence") or 0)
        issues: list[str] = []
        if row.get("status") != "reviewed":
            issues.append("not_reviewed")
        if confidence < 0.75:
            issues.append("low_confidence")
        if review.get("document_type") in {None, "unknown", "missing"}:
            issues.append("unknown_document_type")
        if review.get("keep_in_paperless") is False:
            issues.append("unsafe_keep_false")
        planned.append(
            {
                "document_id": document.get("id"),
                "title": document.get("title"),
                "review_status": row.get("status"),
                "dry_run": True,
                "safe_to_apply": not issues,
                "issues": issues,
                "confidence": confidence,
                "category": review.get("primary_category"),
                "document_type": review.get("document_type"),
                "sensitivity": review.get("sensitivity"),
                "action_needed": bool(review.get("action_needed")),
                "needs_manual_review": bool(review.get("needs_manual_review")),
                "tags_to_add": tags_for_review(review, prefix),
                "summary": review.get("summary"),
                "keep_in_paperless": review.get("keep_in_paperless"),
                "no_delete": True,
            }
        )
    return planned


def render_plan_report(source: str, planned: list[dict[str, Any]]) -> str:
    categories = Counter(row.get("category") for row in planned)
    sensitivities = Counter(row.get("sensitivity") for row in planned)
    issue_rows = [row for row in planned if row.get("issues")]

    def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
        lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        for row in rows:
            cells = [" ".join(str("" if value is None else value).replace("|", "/").split())[:180] for value in row]
            lines.append("| " + " | ".join(cells) + " |")
        return lines

    lines = [
        "# Paperless Write-Back Dry-Run Plan",
        "",
        f"Source manifest: `{source}`",
        "",
        "This plan proposes controlled tags only. It does not delete documents.",
        "",
        "## Safety Gates",
        "",
        *table(
            ["Gate", "Value"],
            [
                ["Rows", len(planned)],
                ["Safe to apply", f"{sum(1 for row in planned if row.get('safe_to_apply'))}/{len(planned)}"],
                ["Issue rows", len(issue_rows)],
                ["Deletes proposed", 0],
                ["Rows with no_delete=false", sum(1 for row in planned if not row.get("no_delete"))],
            ],
        ),
        "",
        "## Category Counts",
        "",
        *table(["Category", "Count"], categories.most_common()),
        "",
        "## Sensitivity Counts",
        "",
        *table(["Sensitivity", "Count"], sensitivities.most_common()),
        "",
        "## Issue Rows",
        "",
        *table(
            ["ID", "Issues", "Category", "Type", "Confidence", "Title"],
            [
                [
                    row.get("document_id"),
                    ", ".join(row.get("issues") or []),
                    row.get("category"),
                    row.get("document_type"),
                    row.get("confidence"),
                    row.get("title"),
                ]
                for row in issue_rows[:100]
            ],
        ),
    ]
    return "\n".join(lines).rstrip() + "\n"


def validate_plan_for_apply(planned: list[Any], prefix: str = CONTROLLED_TAG_PREFIX) -> list[str]:
    failures: list[str] = []
    if not planned:
        failures.append("plan is empty")
    for row_number, row in enumerate(planned, start=1):
        if not isinstance(row, dict):
            failures.append(f"row {row_number}: plan entry must be an object")
            continue
        document_id = row.get("document_id")
        label = f"row {row_number} (document {document_id!r})"
        if type(document_id) is not int or document_id < 1:
            failures.append(f"{label}: document_id must be a positive integer")
        if row.get("review_status") != "reviewed":
            failures.append(f"{label}: review_status is not reviewed")
        if row.get("dry_run") is not True:
            failures.append(f"{label}: dry_run must be literal true")
        if row.get("safe_to_apply") is not True:
            failures.append(f"{label}: safe_to_apply must be literal true")
        if row.get("keep_in_paperless") is not True:
            failures.append(f"{label}: keep_in_paperless must be literal true")
        if row.get("no_delete") is not True:
            failures.append(f"{label}: no_delete must be literal true")

        issues = row.get("issues")
        if not isinstance(issues, list):
            failures.append(f"{label}: issues must be a list")
        elif issues:
            failures.append(f"{label}: unresolved safety issues: {', '.join(map(str, issues))}")

        confidence = row.get("confidence")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.75 <= confidence <= 1
        ):
            failures.append(f"{label}: confidence must be a number from 0.75 to 1")
        document_type = row.get("document_type")
        normalized_document_type = clean_label(document_type, "unknown")
        if (
            not isinstance(document_type, str)
            or document_type != normalized_document_type
            or normalized_document_type in {"unknown", "missing"}
        ):
            failures.append(f"{label}: document_type is not safe to apply")

        category = row.get("category")
        sensitivity = row.get("sensitivity")
        action_needed = row.get("action_needed")
        needs_manual_review = row.get("needs_manual_review")
        if not isinstance(category, str) or not category.strip():
            failures.append(f"{label}: category must be a non-empty string")
        if not isinstance(sensitivity, str) or not sensitivity.strip():
            failures.append(f"{label}: sensitivity must be a non-empty string")
        if type(action_needed) is not bool:
            failures.append(f"{label}: action_needed must be a boolean")
        if type(needs_manual_review) is not bool:
            failures.append(f"{label}: needs_manual_review must be a boolean")

        tags = row.get("tags_to_add")
        if not isinstance(tags, list) or not tags:
            failures.append(f"{label}: tags_to_add must be a non-empty list")
            continue
        tags_are_strings = all(isinstance(tag, str) for tag in tags)
        for tag in tags:
            if not isinstance(tag, str) or not tag.startswith(f"{prefix}:"):
                failures.append(f"{label}: invalid tag {tag!r}")
        if (
            isinstance(category, str)
            and category.strip()
            and isinstance(sensitivity, str)
            and sensitivity.strip()
            and isinstance(document_type, str)
            and document_type == normalized_document_type
            and normalized_document_type not in {"unknown", "missing"}
            and type(action_needed) is bool
            and type(needs_manual_review) is bool
            and tags_are_strings
        ):
            expected_tags = tags_for_review(
                {
                    "primary_category": category,
                    "document_type": document_type,
                    "sensitivity": sensitivity,
                    "action_needed": action_needed,
                    "needs_manual_review": needs_manual_review,
                },
                prefix,
            )
            if sorted(set(tags)) != expected_tags or len(tags) != len(expected_tags):
                failures.append(f"{label}: tags_to_add does not match the reviewed safety fields")
    return failures


def apply_tag_plan(
    client: PaperlessClient,
    planned: list[Any],
    *,
    apply: bool,
    yes: bool,
    prefix: str = CONTROLLED_TAG_PREFIX,
) -> dict[str, Any]:
    failures = validate_plan_for_apply(planned, prefix)
    if apply and (not yes or os.environ.get("PAPERLESS_REVIEW_APPLY") != "YES"):
        failures.append("live apply requires --apply --yes and PAPERLESS_REVIEW_APPLY=YES")
    if failures:
        return {"blocked": True, "failures": failures, "apply": apply}

    existing_tags = client.list_tags()
    all_tag_names = sorted({tag for row in planned for tag in (row.get("tags_to_add") or [])})
    tags_to_create = [tag for tag in all_tag_names if tag not in existing_tags]
    result = {
        "blocked": False,
        "apply": apply,
        "plan_rows": len(planned),
        "tags_to_create": len(tags_to_create),
        "tag_links_to_add": sum(len(row.get("tags_to_add") or []) for row in planned),
        "created_tags": 0,
        "patched_documents": 0,
    }
    if not apply:
        return result

    for tag in tags_to_create:
        existing_tags[tag] = client.create_tag(tag)
        result["created_tags"] += 1
    for row in planned:
        document_id = int(row["document_id"])
        tag_ids = [existing_tags[tag] for tag in row.get("tags_to_add") or []]
        current_tag_ids = client.document_tag_ids(document_id)
        client.patch_document_tags(document_id, sorted(set(current_tag_ids) | set(tag_ids)))
        result["patched_documents"] += 1
    return result
