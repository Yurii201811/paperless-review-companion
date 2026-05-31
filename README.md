# Paperless Review Companion

Manifest-first, local-model document triage for Paperless-ngx.

Paperless Review Companion helps you review a large Paperless-ngx archive without
letting an AI write directly into your document system. It exports document
metadata/OCR excerpts, classifies each document with a local Ollama model or a
transparent rules-only fallback, writes a JSONL manifest, and renders small
human review reports before any optional tag write-back.

The project is designed for private archives, self-hosted setups, and cautious
operators. It does not require paid LLM APIs.

## Why This Exists

Large Paperless archives often become searchable but not understandable. You may
have thousands of scans, invoices, IDs, travel files, letters, and old notes, but
you still need a safe way to answer:

- What needs my attention first?
- Which documents are identity, finance, health, legal, or routine archive?
- Which model classifications are too weak to trust?
- What tags would be added if I approved write-back?

This tool keeps the answer in manifests and reports first. Paperless remains
unchanged until you review an explicit dry-run plan.

## Features

- Reads Paperless documents through the official REST API.
- Can also classify an exported JSONL document file for offline tests.
- Uses Ollama locally by default, with no cloud LLM dependency.
- Includes a rules-only mode for deterministic dry runs and CI.
- Writes append-only JSONL manifests.
- Deduplicates repeated manifest rows by document ID when rendering reports.
- Produces three review surfaces:
  - full report
  - executive triage
  - small focus queue
- Creates a write-back dry-run plan that only proposes controlled tags.
- Optional guarded tag write-back through the Paperless API.
- Never proposes document deletion.

## Safety Model

The default workflow is:

1. Read document metadata/OCR excerpts.
2. Classify into a local JSONL manifest.
3. Render reports.
4. Generate a dry-run write-back plan.
5. Review the plan manually.
6. Apply controlled tags only if you pass explicit apply flags.

No raw private archive output belongs in this repository. The `.gitignore`
excludes manifests, reports, local exports, `.env`, and caches.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

Optional local model runtime:

```bash
ollama pull gemma3:4b
```

## Quick Demo

Run a private-data-free fixture through rules-only mode:

```bash
paperless-review review \
  --input sample_data/demo_documents.jsonl \
  --output review/demo-review.jsonl \
  --rules-only

paperless-review report review/demo-review.jsonl --output review/demo-report.md
paperless-review triage review/demo-review.jsonl --output review/demo-triage.md
paperless-review focus review/demo-review.jsonl --output review/demo-focus.md
paperless-review plan-writeback review/demo-review.jsonl --output review/demo-plan.jsonl --report review/demo-plan.md
```

## Paperless API Review

Create a local `.env` file or export values in your shell:

```bash
export PAPERLESS_URL="http://127.0.0.1:8000"
export PAPERLESS_TOKEN="your-paperless-api-token"
```

Review the first 25 documents with Ollama:

```bash
paperless-review review \
  --paperless-url "$PAPERLESS_URL" \
  --paperless-token "$PAPERLESS_TOKEN" \
  --limit 25 \
  --model gemma3:4b \
  --output review/paperless-review.jsonl
```

Resume into the same manifest by running with the same `--output`; later rows
replace earlier rows for reporting, but the manifest remains append-only.

## Write-Back

Write-back is tag-only and guarded. First create a plan:

```bash
paperless-review plan-writeback review/paperless-review.jsonl \
  --output review/writeback-plan.jsonl \
  --report review/writeback-plan.md
```

Dry-run the plan against Paperless:

```bash
paperless-review apply-writeback review/writeback-plan.jsonl \
  --paperless-url "$PAPERLESS_URL" \
  --paperless-token "$PAPERLESS_TOKEN" \
  --dry-run
```

Apply only after reviewing the plan:

```bash
PAPERLESS_REVIEW_APPLY=YES paperless-review apply-writeback review/writeback-plan.jsonl \
  --paperless-url "$PAPERLESS_URL" \
  --paperless-token "$PAPERLESS_TOKEN" \
  --apply --yes
```

The tool refuses live apply unless all safety gates pass.

## Categories

The built-in taxonomy is intentionally practical:

- `legal`
- `finance_tax`
- `housing_travel`
- `health_personal`
- `identity`
- `learning_books`
- `work_product`
- `media`
- `personal_strategy`
- `other`

You can change the prompt and rules in `src/paperless_review_companion/review.py`.

## Checks

```bash
python3 -m pytest
python3 -m compileall src tests
```

## Documentation

- [Architecture](docs/architecture.md)
- [Privacy and safety](docs/privacy.md)
- [Paperless setup](docs/paperless-setup.md)
- [Roadmap](docs/roadmap.md)

## Project Status

This is an MVP companion CLI. It is useful for local-first Paperless archive
triage, but it should be run on small batches first and reviewed carefully
before enabling write-back.

