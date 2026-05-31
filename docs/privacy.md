# Privacy And Safety

This project assumes your Paperless archive is private.

## What May Contain Private Data

- exported document JSONL
- review manifests
- Markdown reports
- write-back plans
- terminal logs containing document titles or summaries

Those paths are ignored by `.gitignore`, but you should still inspect commits
before publishing.

## Local Model Default

The default model path uses Ollama. Prompts are sent to `http://127.0.0.1:11434`
unless you override `--ollama-url`.

If you configure a remote Ollama-compatible endpoint, document excerpts leave
your machine.

## Write-Back Rules

- Write-back is tag-only.
- Generated tags use the `ai_review:` prefix by default.
- The tool refuses low-confidence, unknown-type, or unsafe rows.
- The tool does not delete documents.
- The tool requires `--apply --yes` and `PAPERLESS_REVIEW_APPLY=YES` for live
  tag changes.

## Recommended Workflow

1. Start with `--limit 10`.
2. Review the generated manifest locally.
3. Render triage and focus reports.
4. Generate a write-back plan.
5. Read the plan before applying.
6. Back up Paperless before the first live write-back.

