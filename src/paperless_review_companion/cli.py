from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .client import PaperlessClient
from .manifest import append_jsonl, latest_by_document, load_jsonl, write_jsonl
from .renderers import render_focus, render_full_report, render_triage
from .review import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, review_document
from .writeback import apply_tag_plan, plan_rows, render_plan_report


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


def load_input_documents(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    documents: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row.get("document"), dict):
            documents.append(row["document"])
        else:
            documents.append(row)
    return documents


def command_review(args: argparse.Namespace) -> int:
    if args.input:
        documents = load_input_documents(args.input)
        if args.limit:
            documents = documents[: args.limit]
    else:
        url = args.paperless_url or os.environ.get("PAPERLESS_URL")
        token = args.paperless_token or os.environ.get("PAPERLESS_TOKEN")
        if not url or not token:
            raise SystemExit("Provide --paperless-url/--paperless-token or PAPERLESS_URL/PAPERLESS_TOKEN, or use --input.")
        client = PaperlessClient(url, token, timeout=args.timeout)
        documents = list(client.iter_documents(limit=args.limit, page_size=args.page_size, content_chars=args.content_chars))

    rows = [
        review_document(
            document,
            rules_only=args.rules_only,
            model=args.model,
            ollama_url=args.ollama_url,
            timeout=args.timeout,
        )
        for document in documents
    ]
    append_jsonl(args.output, rows)
    print(args.output)
    print(f"reviewed {len(rows)} document(s)")
    return 0


def load_latest_manifest(path: Path) -> list[dict[str, Any]]:
    return latest_by_document(load_jsonl(path))


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    print(path)


def command_report(args: argparse.Namespace) -> int:
    rows = load_latest_manifest(args.manifest)
    write_text(args.output, render_full_report(str(args.manifest), rows))
    return 0


def command_triage(args: argparse.Namespace) -> int:
    rows = load_latest_manifest(args.manifest)
    write_text(args.output, render_triage(str(args.manifest), rows, max_rows=args.max_rows))
    return 0


def command_focus(args: argparse.Namespace) -> int:
    rows = load_latest_manifest(args.manifest)
    write_text(args.output, render_focus(str(args.manifest), rows, limit=args.limit))
    return 0


def command_plan_writeback(args: argparse.Namespace) -> int:
    rows = load_latest_manifest(args.manifest)
    planned = plan_rows(rows, prefix=args.tag_prefix)
    write_jsonl(args.output, planned)
    write_text(args.report, render_plan_report(str(args.manifest), planned))
    print(args.output)
    return 0


def command_apply_writeback(args: argparse.Namespace) -> int:
    url = args.paperless_url or os.environ.get("PAPERLESS_URL")
    token = args.paperless_token or os.environ.get("PAPERLESS_TOKEN")
    if not url or not token:
        raise SystemExit("Provide --paperless-url/--paperless-token or PAPERLESS_URL/PAPERLESS_TOKEN.")
    planned = load_jsonl(args.plan)
    client = PaperlessClient(url, token, timeout=args.timeout)
    result = apply_tag_plan(client, planned, apply=args.apply and not args.dry_run, yes=args.yes, prefix=args.tag_prefix)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("blocked") else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paperless-review", description="Manifest-first review for Paperless-ngx archives.")
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="Classify Paperless documents into a JSONL manifest.")
    review.add_argument("--input", type=Path, help="Offline JSONL document export.")
    review.add_argument("--paperless-url", help="Paperless base URL.")
    review.add_argument("--paperless-token", help="Paperless API token.")
    review.add_argument("--output", type=Path, required=True, help="Append-only review manifest JSONL.")
    review.add_argument("--limit", type=positive_int, default=10, help="Maximum documents to review.")
    review.add_argument("--page-size", type=positive_int, default=50, help="Paperless API page size.")
    review.add_argument("--content-chars", type=positive_int, default=3500, help="OCR excerpt chars per document.")
    review.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model.")
    review.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama generate API URL.")
    review.add_argument("--timeout", type=positive_int, default=120, help="HTTP timeout seconds.")
    review.add_argument("--rules-only", action="store_true", help="Use deterministic local rules instead of Ollama.")
    review.set_defaults(func=command_review)

    report = sub.add_parser("report", help="Render a full Markdown report.")
    report.add_argument("manifest", type=Path)
    report.add_argument("--output", type=Path, required=True)
    report.set_defaults(func=command_report)

    triage = sub.add_parser("triage", help="Render an executive triage report.")
    triage.add_argument("manifest", type=Path)
    triage.add_argument("--output", type=Path, required=True)
    triage.add_argument("--max-rows", type=positive_int, default=75)
    triage.set_defaults(func=command_triage)

    focus = sub.add_parser("focus", help="Render a small focus queue.")
    focus.add_argument("manifest", type=Path)
    focus.add_argument("--output", type=Path, required=True)
    focus.add_argument("--limit", type=positive_int, default=100)
    focus.set_defaults(func=command_focus)

    plan = sub.add_parser("plan-writeback", help="Create a tag-only dry-run write-back plan.")
    plan.add_argument("manifest", type=Path)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--report", type=Path, required=True)
    plan.add_argument("--tag-prefix", default="ai_review")
    plan.set_defaults(func=command_plan_writeback)

    apply = sub.add_parser("apply-writeback", help="Dry-run or apply a guarded tag write-back plan.")
    apply.add_argument("plan", type=Path)
    apply.add_argument("--paperless-url")
    apply.add_argument("--paperless-token")
    apply.add_argument("--timeout", type=positive_int, default=120)
    apply.add_argument("--tag-prefix", default="ai_review")
    apply.add_argument("--dry-run", action="store_true", help="Check the plan without writing tags.")
    apply.add_argument("--apply", action="store_true", help="Apply tag changes.")
    apply.add_argument("--yes", action="store_true", help="Confirm live apply.")
    apply.set_defaults(func=command_apply_writeback)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - produce clean CLI errors.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

