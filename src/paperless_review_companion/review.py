from __future__ import annotations

import datetime as dt
import json
import re
import urllib.request
from typing import Any

from .constants import CATEGORIES, PROTECTED_CATEGORIES, REQUIRED_REVIEW_FIELDS, SENSITIVITIES

DEFAULT_MODEL = "gemma3:4b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def compact_text(value: Any, limit: int = 3500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def searchable(document: dict[str, Any]) -> str:
    keys = ("title", "original_filename", "archive_filename", "mime_type", "content_excerpt")
    return " ".join(str(document.get(key) or "") for key in keys).lower()


def build_prompt(document: dict[str, Any]) -> str:
    payload = {
        "id": document.get("id"),
        "title": document.get("title"),
        "original_filename": document.get("original_filename"),
        "created": document.get("created"),
        "mime_type": document.get("mime_type"),
        "page_count": document.get("page_count"),
        "existing_tags": document.get("tags") or [],
        "content_excerpt": compact_text(document.get("content_excerpt"), 3500),
    }
    return f"""You classify a private Paperless-ngx document from metadata and a bounded OCR excerpt.
Do not invent facts. If OCR is empty or weak, lower confidence and request manual review.

Return one compact JSON object with exactly these keys:
- document_id: number
- source: one of paperless, import, email, scanner, unknown
- primary_category: one of legal, finance_tax, housing_travel, health_personal, identity, learning_books, work_product, media, personal_strategy, other
- sensitivity: one of public, internal, sensitive, highly_sensitive
- document_type: short lowercase label such as invoice, bank_statement, tax_document, court_document, passport, lease, book, course_material, photo, certificate, note, unknown
- correspondent_or_source: organization/person if clear, otherwise null
- summary: one or two plain sentences
- key_dates: array of visible dates or empty array
- suggested_tags: array of 3 to 8 short tags
- action_needed: boolean
- action_reason: short reason or null
- keep_in_paperless: boolean
- confidence: number from 0 to 1
- rationale: short explanation

Safety rules:
- Never set keep_in_paperless=false for legal, finance_tax, health_personal, identity, or personal_strategy.
- action_needed means likely human attention is needed, not simply that the document exists.
- Prefer manual review over confident guessing.

Document JSON:
{json.dumps(payload, ensure_ascii=False)}
"""


def ollama_review(document: dict[str, Any], *, model: str, ollama_url: str, timeout: int) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "prompt": build_prompt(document),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    request = urllib.request.Request(ollama_url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = payload.get("response", "")
    if not isinstance(raw, str):
        return {"parse_error": True, "raw_model_response": raw}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw_model_response": raw}
    return value if isinstance(value, dict) else {"parse_error": True, "raw_model_response": raw}


def rules_review(document: dict[str, Any]) -> dict[str, Any]:
    text = searchable(document)
    category = "other"
    document_type = "unknown"
    sensitivity = "internal"
    action_needed = False
    action_reason = None

    rules: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("identity", "passport", ("passport", "national id", "identity card", "visa", "residence permit")),
        ("finance_tax", "invoice", ("invoice", "amount due", "payment due", "receipt")),
        ("finance_tax", "bank_statement", ("bank statement", "account statement", "transaction history")),
        ("finance_tax", "tax_document", ("tax", "vat", "income declaration")),
        ("housing_travel", "lease", ("lease", "rent", "landlord", "tenant", "mortgage", "booking")),
        ("legal", "legal_document", ("court", "lawsuit", "claim", "contract", "agreement", "lawyer")),
        ("health_personal", "medical_document", ("medical", "patient", "diagnosis", "health")),
        ("learning_books", "course_material", ("course", "lesson", "exercise", "study notes", "book")),
        ("media", "image", ("image/png", "image/jpeg", "screenshot", ".png", ".jpg", ".jpeg")),
        ("work_product", "work_document", ("project", "proposal", "meeting notes", "research report")),
        ("personal_strategy", "note", ("goals", "strategy", "journal", "personal plan")),
    )
    for found_category, found_type, terms in rules:
        if any(term in text for term in terms):
            category = found_category
            document_type = found_type
            break

    if category in {"identity", "legal", "health_personal"}:
        sensitivity = "highly_sensitive" if category == "identity" else "sensitive"
    elif category in {"finance_tax", "housing_travel", "personal_strategy"}:
        sensitivity = "sensitive"
    elif category in {"learning_books", "media"}:
        sensitivity = "internal"

    urgent_terms = ("due", "deadline", "expires", "expired", "overdue", "court", "claim", "appointment")
    if category in {"legal", "finance_tax", "identity", "housing_travel"} and any(term in text for term in urgent_terms):
        action_needed = True
        action_reason = "Contains a deadline, official process, payment, or legal/identity signal."

    title = document.get("title") or document.get("original_filename") or f"Document {document.get('id')}"
    confidence = 0.86 if document_type != "unknown" else 0.45
    if not compact_text(document.get("content_excerpt")):
        confidence = min(confidence, 0.65)

    return {
        "document_id": document.get("id"),
        "source": "paperless",
        "primary_category": category,
        "sensitivity": sensitivity,
        "document_type": document_type,
        "correspondent_or_source": None,
        "summary": f"Likely {document_type.replace('_', ' ')} in {category.replace('_', ' ')}. Title: {title}.",
        "key_dates": [],
        "suggested_tags": suggested_tags(category, document_type, sensitivity, action_needed),
        "action_needed": action_needed,
        "action_reason": action_reason,
        "keep_in_paperless": True,
        "confidence": confidence,
        "rationale": "Rules-only classification from title, filename, MIME type, and OCR excerpt.",
    }


def suggested_tags(category: str, document_type: str, sensitivity: str, action_needed: bool) -> list[str]:
    tags = [f"category:{category}", f"type:{document_type}", f"sensitivity:{sensitivity}"]
    if action_needed:
        tags.append("action_needed")
    return tags


def clean_label(value: Any, fallback: str) -> str:
    text = str(value or fallback).strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text).strip("_")
    return text[:64] or fallback


def normalize_review(review: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(review)
    normalized.setdefault("document_id", document.get("id"))
    normalized["source"] = clean_label(normalized.get("source"), "unknown")
    normalized["primary_category"] = clean_label(normalized.get("primary_category"), "other")
    if normalized["primary_category"] not in CATEGORIES:
        normalized["primary_category"] = "other"
    normalized["sensitivity"] = clean_label(normalized.get("sensitivity"), "internal")
    if normalized["sensitivity"] not in SENSITIVITIES:
        normalized["sensitivity"] = "internal"
    normalized["document_type"] = clean_label(normalized.get("document_type"), "unknown")
    normalized["summary"] = compact_text(normalized.get("summary") or "Needs manual review.", 300)
    normalized["rationale"] = compact_text(normalized.get("rationale") or "No rationale provided.", 300)
    normalized["key_dates"] = normalized.get("key_dates") if isinstance(normalized.get("key_dates"), list) else []
    tags = normalized.get("suggested_tags")
    if not isinstance(tags, list) or not tags:
        tags = suggested_tags(
            normalized["primary_category"],
            normalized["document_type"],
            normalized["sensitivity"],
            bool(normalized.get("action_needed")),
        )
    normalized["suggested_tags"] = [clean_label(tag, "reviewed") for tag in tags[:10]]
    normalized["action_needed"] = bool(normalized.get("action_needed"))
    if not normalized["action_needed"]:
        normalized["action_reason"] = None
    else:
        normalized["action_reason"] = compact_text(normalized.get("action_reason") or "Review suggested.", 180)
    normalized["keep_in_paperless"] = bool(normalized.get("keep_in_paperless", True))
    try:
        normalized["confidence"] = max(0.0, min(1.0, float(normalized.get("confidence", 0.0))))
    except (TypeError, ValueError):
        normalized["confidence"] = 0.0
    if normalized["primary_category"] in PROTECTED_CATEGORIES:
        normalized["keep_in_paperless"] = True
    if any(normalized.get(key) is None for key in REQUIRED_REVIEW_FIELDS):
        normalized["needs_manual_review"] = True
    if normalized["confidence"] < 0.75:
        normalized["needs_manual_review"] = True
    return normalized


def review_document(
    document: dict[str, Any],
    *,
    rules_only: bool,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout: int = 120,
) -> dict[str, Any]:
    reviewed_at = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        raw = rules_review(document) if rules_only else ollama_review(document, model=model, ollama_url=ollama_url, timeout=timeout)
        review = normalize_review(raw, document)
        return {"status": "reviewed", "reviewed_at": reviewed_at, "document": document, "review": review}
    except Exception as exc:  # noqa: BLE001 - CLI should preserve failed rows in the manifest.
        fallback = normalize_review(
            {
                "document_id": document.get("id"),
                "source": "unknown",
                "primary_category": "other",
                "sensitivity": "internal",
                "document_type": "unknown",
                "summary": "Model review failed; manual review required.",
                "suggested_tags": ["review_failed", "manual_review"],
                "action_needed": False,
                "keep_in_paperless": True,
                "confidence": 0,
                "rationale": str(exc),
            },
            document,
        )
        fallback["needs_manual_review"] = True
        return {"status": "model_error", "reviewed_at": reviewed_at, "document": document, "review": fallback}
