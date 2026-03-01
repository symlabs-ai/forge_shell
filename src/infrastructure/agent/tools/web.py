"""Web tools: web_search (Brave API) and web_fetch (httpx + readability).

Adapted from nanobot for sync execution via httpx sync client.
"""
from __future__ import annotations

import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from forge_llm.domain.entities import ToolCall, ToolDefinition, ToolResult

_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
_MAX_REDIRECTS = 5


def _strip_tags(text: str) -> str:
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


class WebSearchTool:
    """Search the web using Brave Search API."""

    def __init__(self, api_key: str | None = None, max_results: int = 5) -> None:
        self._init_api_key = api_key
        self._max_results = max_results

    @property
    def _api_key(self) -> str:
        return self._init_api_key or os.environ.get("BRAVE_API_KEY", "")

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web. Returns titles, URLs, and snippets.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {"type": "integer", "description": "Number of results (1-10)", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        query = call.arguments.get("query", "")
        count = call.arguments.get("count", self._max_results)

        if not self._api_key:
            return ToolResult(
                tool_call_id=call.id,
                content="Error: Brave Search API key not configured. Set agent.brave_api_key in config or export BRAVE_API_KEY.",
                is_error=True,
            )

        try:
            n = min(max(count, 1), 10)
            with httpx.Client(timeout=10.0) as client:
                r = client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": n},
                    headers={"Accept": "application/json", "X-Subscription-Token": self._api_key},
                )
                r.raise_for_status()

            results = r.json().get("web", {}).get("results", [])[:n]
            if not results:
                return ToolResult(tool_call_id=call.id, content=f"No results for: {query}")

            lines = [f"Results for: {query}\n"]
            for i, item in enumerate(results, 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                if desc := item.get("description"):
                    lines.append(f"   {desc}")
            return ToolResult(tool_call_id=call.id, content="\n".join(lines))

        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=f"Error: {e}", is_error=True)


class WebFetchTool:
    """Fetch URL and extract readable content (HTML to text/markdown)."""

    def __init__(self, max_chars: int = 50_000) -> None:
        self._max_chars = max_chars

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_fetch",
            description="Fetch URL and extract readable content (HTML to markdown/text).",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "extractMode": {
                        "type": "string",
                        "enum": ["markdown", "text"],
                        "description": "Extraction mode (default: markdown)",
                    },
                    "maxChars": {"type": "integer", "minimum": 100, "description": "Max characters to return"},
                },
                "required": ["url"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        from readability import Document

        url = call.arguments.get("url", "")
        extract_mode = call.arguments.get("extractMode", "markdown")
        max_chars = call.arguments.get("maxChars", self._max_chars)

        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"URL validation failed: {error_msg}", "url": url}, ensure_ascii=False),
                is_error=True,
            )

        try:
            with httpx.Client(
                follow_redirects=True,
                max_redirects=_MAX_REDIRECTS,
                timeout=30.0,
            ) as client:
                r = client.get(url, headers={"User-Agent": _USER_AGENT})
                r.raise_for_status()

            ctype = r.headers.get("content-type", "")

            if "application/json" in ctype:
                text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                doc = Document(r.text)
                if extract_mode == "markdown":
                    content = self._to_markdown(doc.summary())
                else:
                    content = _strip_tags(doc.summary())
                text = f"# {doc.title()}\n\n{content}" if doc.title() else content
                extractor = "readability"
            else:
                text, extractor = r.text, "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps(
                    {
                        "url": url, "finalUrl": str(r.url), "status": r.status_code,
                        "extractor": extractor, "truncated": truncated, "length": len(text),
                        "text": text,
                    },
                    ensure_ascii=False,
                ),
            )

        except Exception as e:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": str(e), "url": url}, ensure_ascii=False),
                is_error=True,
            )

    @staticmethod
    def _to_markdown(raw_html: str) -> str:
        text = re.sub(
            r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            lambda m: f'[{_strip_tags(m[2])}]({m[1]})', raw_html, flags=re.I,
        )
        text = re.sub(
            r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
            lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I,
        )
        text = re.sub(r'<li[^>]*>([\s\S]*?)</li>', lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I)
        text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
        text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
        return _normalize(_strip_tags(text))
