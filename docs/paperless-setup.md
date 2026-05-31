# Paperless Setup

## API Token

Create or copy a Paperless API token from your Paperless user settings. Then:

```bash
export PAPERLESS_URL="http://127.0.0.1:8000"
export PAPERLESS_TOKEN="your-token"
```

The token is used as:

```text
Authorization: Token your-token
```

## First Review

```bash
paperless-review review \
  --paperless-url "$PAPERLESS_URL" \
  --paperless-token "$PAPERLESS_TOKEN" \
  --limit 10 \
  --rules-only \
  --output review/first-pass.jsonl
```

Use `--rules-only` first to verify connectivity and output paths. Then switch to
Ollama:

```bash
paperless-review review \
  --paperless-url "$PAPERLESS_URL" \
  --paperless-token "$PAPERLESS_TOKEN" \
  --limit 10 \
  --model gemma3:4b \
  --output review/first-pass.jsonl
```

## Content Excerpt Size

The default excerpt is intentionally bounded. Increase only when you need more
context:

```bash
paperless-review review --content-chars 5000 ...
```

