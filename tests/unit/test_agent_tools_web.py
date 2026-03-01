"""Tests for web tools: WebSearchTool and WebFetchTool."""
import json
from unittest.mock import patch, MagicMock

import pytest

from forge_llm.domain.entities import ToolCall

from src.infrastructure.agent.tools.web import WebSearchTool, WebFetchTool, _validate_url


class TestValidateUrl:
    def test_valid_https(self) -> None:
        ok, _ = _validate_url("https://example.com")
        assert ok

    def test_valid_http(self) -> None:
        ok, _ = _validate_url("http://example.com/page")
        assert ok

    def test_rejects_ftp(self) -> None:
        ok, msg = _validate_url("ftp://example.com")
        assert not ok
        assert "http/https" in msg.lower()

    def test_rejects_no_scheme(self) -> None:
        ok, msg = _validate_url("example.com")
        assert not ok

    def test_rejects_no_domain(self) -> None:
        ok, msg = _validate_url("http://")
        assert not ok


class TestWebSearchTool:
    def _call(self, tool: WebSearchTool, query: str, count: int | None = None) -> tuple[str, bool]:
        args = {"query": query}
        if count is not None:
            args["count"] = count
        result = tool.execute(ToolCall(id="t1", name="web_search", arguments=args))
        return result.content, result.is_error

    def test_no_api_key_returns_error(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            tool = WebSearchTool(api_key=None)
            # Force no env var
            tool._init_api_key = None
            content, is_err = self._call(tool, "test query")
            assert is_err
            assert "api key" in content.lower()

    @patch("src.infrastructure.agent.tools.web.httpx.Client")
    def test_successful_search(self, mock_client_cls) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result 1", "url": "https://example.com/1", "description": "Desc 1"},
                    {"title": "Result 2", "url": "https://example.com/2", "description": "Desc 2"},
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        tool = WebSearchTool(api_key="test-key")
        content, is_err = self._call(tool, "test query")
        assert not is_err
        assert "Result 1" in content
        assert "Result 2" in content

    @patch("src.infrastructure.agent.tools.web.httpx.Client")
    def test_no_results(self, mock_client_cls) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"web": {"results": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        tool = WebSearchTool(api_key="test-key")
        content, is_err = self._call(tool, "obscure query")
        assert not is_err
        assert "no results" in content.lower()

    def test_definition(self) -> None:
        tool = WebSearchTool()
        assert tool.definition.name == "web_search"
        assert "query" in tool.definition.parameters["required"]


class TestWebFetchTool:
    def _call(self, tool: WebFetchTool, url: str, **kwargs) -> tuple[str, bool]:
        args = {"url": url, **kwargs}
        result = tool.execute(ToolCall(id="t1", name="web_fetch", arguments=args))
        return result.content, result.is_error

    def test_invalid_url(self) -> None:
        tool = WebFetchTool()
        content, is_err = self._call(tool, "ftp://bad")
        assert is_err
        data = json.loads(content)
        assert "error" in data

    @patch("src.infrastructure.agent.tools.web.httpx.Client")
    def test_fetches_json(self, mock_client_cls) -> None:
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"key": "value"}
        mock_resp.url = "https://api.example.com/data"
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        tool = WebFetchTool()
        content, is_err = self._call(tool, "https://api.example.com/data")
        assert not is_err
        data = json.loads(content)
        assert data["extractor"] == "json"
        assert data["status"] == 200

    @patch("src.infrastructure.agent.tools.web.httpx.Client")
    def test_fetches_html(self, mock_client_cls) -> None:
        html_content = "<html><head><title>Test Page</title></head><body><p>Hello World</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.text = html_content
        mock_resp.url = "https://example.com"
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        tool = WebFetchTool()
        content, is_err = self._call(tool, "https://example.com")
        assert not is_err
        data = json.loads(content)
        assert data["extractor"] == "readability"

    def test_truncation(self) -> None:
        tool = WebFetchTool(max_chars=100)
        assert tool._max_chars == 100

    def test_definition(self) -> None:
        tool = WebFetchTool()
        assert tool.definition.name == "web_fetch"
        assert "url" in tool.definition.parameters["required"]
