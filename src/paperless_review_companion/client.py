from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator


class PaperlessApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperlessClient:
    base_url: str
    token: str
    timeout: int = 30

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("base_url is required")
        if not self.token:
            raise ValueError("token is required")

    @property
    def root(self) -> str:
        return self.base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.root}{path}"
        if query:
            url += "?" + urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Token {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PaperlessApiError(f"{method} {url} failed: HTTP {exc.code}: {detail[:400]}") from exc
        except urllib.error.URLError as exc:
            raise PaperlessApiError(f"{method} {url} failed: {exc}") from exc
        if not raw.strip():
            return {}
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise PaperlessApiError(f"{method} {url} returned non-object JSON")
        return value

    def iter_documents(self, *, limit: int, page_size: int = 50, content_chars: int = 3500) -> Iterator[dict[str, Any]]:
        emitted = 0
        page = 1
        while emitted < limit:
            payload = self.request(
                "GET",
                "/api/documents/",
                query={"page": page, "page_size": min(page_size, limit - emitted), "ordering": "id"},
            )
            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                return
            for item in results:
                if emitted >= limit:
                    return
                if not isinstance(item, dict) or "id" not in item:
                    continue
                detail = self.get_document(int(item["id"]), content_chars=content_chars)
                emitted += 1
                yield detail
            page += 1

    def get_document(self, document_id: int, *, content_chars: int = 3500) -> dict[str, Any]:
        detail = self.request("GET", f"/api/documents/{document_id}/")
        content = " ".join(str(detail.get("content") or "").split())
        return {
            "id": detail.get("id"),
            "title": detail.get("title"),
            "original_filename": detail.get("original_file_name") or detail.get("original_filename"),
            "archive_filename": detail.get("archive_filename"),
            "created": detail.get("created"),
            "modified": detail.get("modified"),
            "mime_type": detail.get("mime_type"),
            "page_count": detail.get("page_count"),
            "tags": detail.get("tags") or [],
            "document_type": detail.get("document_type"),
            "correspondent": detail.get("correspondent"),
            "content_excerpt": content[:content_chars],
        }

    def document_tag_ids(self, document_id: int) -> list[int]:
        detail = self.request("GET", f"/api/documents/{document_id}/")
        return extract_tag_ids(detail.get("tags"))

    def list_tags(self) -> dict[str, int]:
        tags: dict[str, int] = {}
        page = 1
        while True:
            payload = self.request("GET", "/api/tags/", query={"page": page, "page_size": 100})
            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                return tags
            for item in results:
                if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("id"), int):
                    tags[item["name"]] = item["id"]
            if not payload.get("next"):
                return tags
            page += 1

    def create_tag(self, name: str) -> int:
        payload = self.request("POST", "/api/tags/", body={"name": name})
        tag_id = payload.get("id")
        if not isinstance(tag_id, int):
            raise PaperlessApiError(f"Could not create tag {name!r}: missing id")
        return tag_id

    def patch_document_tags(self, document_id: int, tag_ids: list[int]) -> None:
        self.request("PATCH", f"/api/documents/{document_id}/", body={"tags": tag_ids})


def extract_tag_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    ids: list[int] = []
    for item in value:
        if isinstance(item, int):
            ids.append(item)
        elif isinstance(item, dict) and isinstance(item.get("id"), int):
            ids.append(item["id"])
    return ids
