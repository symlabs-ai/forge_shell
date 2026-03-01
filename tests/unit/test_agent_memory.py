"""Tests for MemoryStore — two-layer persistent memory."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.agent.memory import MemoryStore


class TestMemoryStoreReadWrite:
    def test_read_empty(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        assert store.read_long_term() == ""

    def test_write_and_read(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.write_long_term("# Facts\n- user prefers vim")
        assert "vim" in store.read_long_term()

    def test_overwrite(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.write_long_term("v1")
        store.write_long_term("v2")
        assert store.read_long_term() == "v2"


class TestMemoryStoreHistory:
    def test_append_history(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append_history("[2024-01-01] User asked about docker")
        store.append_history("[2024-01-02] User configured nginx")
        history = (tmp_path / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert "docker" in history
        assert "nginx" in history

    def test_history_entries_separated(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append_history("entry1")
        store.append_history("entry2")
        history = (tmp_path / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        # Each entry ends with double newline
        assert history.count("\n\n") >= 2


class TestMemoryStoreContext:
    def test_empty_context(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        assert store.get_memory_context() == ""

    def test_context_with_memory(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.write_long_term("# User likes Python")
        ctx = store.get_memory_context()
        assert "Long-term Memory" in ctx
        assert "Python" in ctx


class TestMemoryStoreEnsureDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "memory"
        store = MemoryStore(deep)
        store.ensure_dir()
        assert deep.is_dir()


class TestMemoryConsolidate:
    def test_empty_interactions_returns_true(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        mock_agent = MagicMock()
        assert store.consolidate(mock_agent, []) is True

    def test_consolidate_calls_llm(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.ensure_dir()

        mock_response = MagicMock()
        mock_response.message.tool_calls = [{
            "function": {
                "name": "save_memory",
                "arguments": json.dumps({
                    "history_entry": "[2024-01-01 10:00] User set up Docker",
                    "memory_update": "# Facts\n- User works with Docker",
                }),
            }
        }]

        mock_agent = MagicMock()
        mock_agent.chat.return_value = mock_response

        interactions = [
            {"timestamp": "2024-01-01 10:00", "role": "user", "content": "How do I set up Docker?"},
            {"timestamp": "2024-01-01 10:01", "role": "assistant", "content": "Commands: docker..."},
        ]

        result = store.consolidate(mock_agent, interactions)
        assert result is True
        assert "Docker" in store.read_long_term()
        history = (tmp_path / "memory" / "HISTORY.md").read_text(encoding="utf-8")
        assert "Docker" in history

    def test_consolidate_no_tool_call_returns_false(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.ensure_dir()

        mock_response = MagicMock()
        mock_response.message.tool_calls = None

        mock_agent = MagicMock()
        mock_agent.chat.return_value = mock_response

        result = store.consolidate(mock_agent, [{"role": "user", "content": "test"}])
        assert result is False

    def test_consolidate_handles_exception(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.ensure_dir()

        mock_agent = MagicMock()
        mock_agent.chat.side_effect = RuntimeError("LLM offline")

        result = store.consolidate(mock_agent, [{"role": "user", "content": "test"}])
        assert result is False
