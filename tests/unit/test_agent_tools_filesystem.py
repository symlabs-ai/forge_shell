"""Tests for agent filesystem tools: read_file, write_file, edit_file, list_dir."""
import pytest
from pathlib import Path

from forge_llm.domain.entities import ToolCall

from src.infrastructure.agent.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
    _resolve_path,
)


class TestResolvePath:
    def test_absolute_path_unchanged(self, tmp_path: Path) -> None:
        p = _resolve_path(str(tmp_path / "file.txt"))
        assert p == (tmp_path / "file.txt").resolve()

    def test_relative_resolved_against_workspace(self, tmp_path: Path) -> None:
        p = _resolve_path("sub/file.txt", workspace=tmp_path)
        assert p == (tmp_path / "sub" / "file.txt").resolve()

    def test_allowed_dir_permits_inside(self, tmp_path: Path) -> None:
        child = tmp_path / "sub" / "file.txt"
        p = _resolve_path(str(child), allowed_dir=tmp_path)
        assert p == child.resolve()

    def test_allowed_dir_blocks_outside(self, tmp_path: Path) -> None:
        with pytest.raises(PermissionError, match="outside allowed directory"):
            _resolve_path("/etc/passwd", allowed_dir=tmp_path)


class TestReadFileTool:
    def _call(self, tool: ReadFileTool, path: str) -> str:
        result = tool.execute(ToolCall(id="t1", name="read_file", arguments={"path": path}))
        return result.content

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        tool = ReadFileTool(workspace=tmp_path)
        assert self._call(tool, str(f)) == "hello world"

    def test_file_not_found(self, tmp_path: Path) -> None:
        tool = ReadFileTool(workspace=tmp_path)
        result = self._call(tool, str(tmp_path / "missing.txt"))
        assert "not found" in result.lower()

    def test_not_a_file(self, tmp_path: Path) -> None:
        tool = ReadFileTool(workspace=tmp_path)
        result = self._call(tool, str(tmp_path))
        assert "not a file" in result.lower()

    def test_workspace_boundary(self, tmp_path: Path) -> None:
        tool = ReadFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = tool.execute(ToolCall(id="t1", name="read_file", arguments={"path": "/etc/passwd"}))
        assert result.is_error
        assert "outside" in result.content.lower()


class TestWriteFileTool:
    def _call(self, tool: WriteFileTool, path: str, content: str) -> str:
        result = tool.execute(ToolCall(id="t1", name="write_file", arguments={"path": path, "content": content}))
        return result.content

    def test_writes_new_file(self, tmp_path: Path) -> None:
        tool = WriteFileTool(workspace=tmp_path)
        f = tmp_path / "out.txt"
        result = self._call(tool, str(f), "hello")
        assert "successfully" in result.lower()
        assert f.read_text(encoding="utf-8") == "hello"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        tool = WriteFileTool(workspace=tmp_path)
        f = tmp_path / "a" / "b" / "c.txt"
        self._call(tool, str(f), "deep")
        assert f.read_text(encoding="utf-8") == "deep"

    def test_workspace_boundary(self, tmp_path: Path) -> None:
        tool = WriteFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = tool.execute(ToolCall(id="t1", name="write_file", arguments={"path": "/tmp/hacked.txt", "content": "bad"}))
        assert result.is_error


class TestEditFileTool:
    def _call(self, tool: EditFileTool, path: str, old: str, new: str) -> str:
        result = tool.execute(ToolCall(
            id="t1", name="edit_file",
            arguments={"path": path, "old_text": old, "new_text": new},
        ))
        return result.content

    def test_replaces_text(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("x = 1\ny = 2\n", encoding="utf-8")
        tool = EditFileTool(workspace=tmp_path)
        result = self._call(tool, str(f), "x = 1", "x = 42")
        assert "successfully" in result.lower()
        assert f.read_text(encoding="utf-8") == "x = 42\ny = 2\n"

    def test_old_text_not_found_shows_diff(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("x = 1\ny = 2\n", encoding="utf-8")
        tool = EditFileTool(workspace=tmp_path)
        result = self._call(tool, str(f), "x = 11", "x = 42")
        assert "not found" in result.lower()

    def test_ambiguous_match_warns(self, tmp_path: Path) -> None:
        f = tmp_path / "dup.py"
        f.write_text("a = 1\na = 1\n", encoding="utf-8")
        tool = EditFileTool(workspace=tmp_path)
        result = self._call(tool, str(f), "a = 1", "a = 2")
        assert "appears 2 times" in result.lower()

    def test_file_not_found(self, tmp_path: Path) -> None:
        tool = EditFileTool(workspace=tmp_path)
        result = self._call(tool, str(tmp_path / "nope.py"), "x", "y")
        assert "not found" in result.lower()


class TestListDirTool:
    def _call(self, tool: ListDirTool, path: str) -> str:
        result = tool.execute(ToolCall(id="t1", name="list_dir", arguments={"path": path}))
        return result.content

    def test_lists_files_and_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("x", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        tool = ListDirTool(workspace=tmp_path)
        content = self._call(tool, str(tmp_path))
        assert "[FILE] file.txt" in content
        assert "[DIR] subdir" in content

    def test_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        tool = ListDirTool(workspace=tmp_path)
        result = self._call(tool, str(empty))
        assert "empty" in result.lower()

    def test_dir_not_found(self, tmp_path: Path) -> None:
        tool = ListDirTool(workspace=tmp_path)
        result = self._call(tool, str(tmp_path / "nope"))
        assert "not found" in result.lower()

    def test_not_a_directory(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("x", encoding="utf-8")
        tool = ListDirTool(workspace=tmp_path)
        result = self._call(tool, str(f))
        assert "not a directory" in result.lower()
