# Contributing

Paperless Review Companion is a local-first safety tool. Contributions should
make private-archive review more understandable without weakening the
manifest-first workflow.

## Development

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
```

Run the demo flow:

```bash
paperless-review review --input sample_data/demo_documents.jsonl --output review/demo.jsonl --rules-only
paperless-review triage review/demo.jsonl --output review/demo-triage.md
```

## Guidelines

- Keep rules-only mode working without Paperless, Ollama, or network access.
- Do not commit real manifests, document excerpts, API tokens, `.env` files, or
  archive reports.
- Keep write-back opt-in, dry-run-first, and tag-only unless a future design
  clearly proves a safer broader operation.
- Add tests for safety gates, report rendering, and write-back planning.
- Update docs when CLI behavior, taxonomy, privacy posture, or write-back
  behavior changes.

## Pull Request Checklist

- Tests pass.
- No private document data is committed.
- The demo fixture still works.
- Write-back remains explicit and guarded.
- Documentation is updated when user-facing behavior changes.

