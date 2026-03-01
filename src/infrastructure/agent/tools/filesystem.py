"""Filesystem tools: read_file, write_file, edit_file, list_dir.

Adaptados do nanobot para forge_llm IToolPort (sync).
"""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from forge_llm.domain.entities import ToolCall, ToolDefinition, ToolResult


def _resolve_path(
    path: str, workspace: Path | None = None, allowed_dir: Path | None = None
) -> Path:
    """Resolve path against workspace (if relative) and enforce directory restriction."""
    p = Path(path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    resolved = p.resolve()
    if allowed_dir:
        try:
            resolved.relative_to(allowed_dir.resolve())
        except ValueError:
            raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
    return resolved


class ReadFileTool:
    """Read file contents (UTF-8)."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None) -> None:
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read the contents of a file at the given path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to read"},
                },
                "required": ["path"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        path = call.arguments.get("path", "")
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return ToolResult(tool_call_id=call.id, content=f"Error: File not found: {path}")
            if not file_path.is_file():
                return ToolResult(tool_call_id=call.id, content=f"Error: Not a file: {path}")
            content = file_path.read_text(encoding="utf-8")
            return ToolResult(tool_call_id=call.id, content=content)
        except PermissionError as e:
            return ToolResult(tool_call_id=call.id, content=f"Error: {e}", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=f"Error reading file: {e}", is_error=True)


class WriteFileTool:
    """Write content to a file, creating parent directories if needed."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None) -> None:
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write content to a file at the given path. Creates parent directories if needed.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to write to"},
                    "content": {"type": "string", "description": "The content to write"},
                },
                "required": ["path", "content"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        path = call.arguments.get("path", "")
        content = call.arguments.get("content", "")
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(tool_call_id=call.id, content=f"Successfully wrote {len(content)} bytes to {file_path}")
        except PermissionError as e:
            return ToolResult(tool_call_id=call.id, content=f"Error: {e}", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=f"Error writing file: {e}", is_error=True)


class EditFileTool:
    """Edit a file by replacing old_text with new_text (fuzzy diff diagnostics on failure)."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None) -> None:
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description="Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to edit"},
                    "old_text": {"type": "string", "description": "The exact text to find and replace"},
                    "new_text": {"type": "string", "description": "The text to replace with"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        path = call.arguments.get("path", "")
        old_text = call.arguments.get("old_text", "")
        new_text = call.arguments.get("new_text", "")
        try:
            file_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not file_path.exists():
                return ToolResult(tool_call_id=call.id, content=f"Error: File not found: {path}")

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                msg = self._not_found_message(old_text, content, path)
                return ToolResult(tool_call_id=call.id, content=msg)

            count = content.count(old_text)
            if count > 1:
                return ToolResult(
                    tool_call_id=call.id,
                    content=f"Warning: old_text appears {count} times. Please provide more context to make it unique.",
                )

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            return ToolResult(tool_call_id=call.id, content=f"Successfully edited {file_path}")
        except PermissionError as e:
            return ToolResult(tool_call_id=call.id, content=f"Error: {e}", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=f"Error editing file: {e}", is_error=True)

    @staticmethod
    def _not_found_message(old_text: str, content: str, path: str) -> str:
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = len(old_lines)

        best_ratio, best_start = 0.0, 0
        for i in range(max(1, len(lines) - window + 1)):
            ratio = difflib.SequenceMatcher(None, old_lines, lines[i : i + window]).ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, i

        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_lines,
                    lines[best_start : best_start + window],
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return f"Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
        return f"Error: old_text not found in {path}. No similar text found. Verify the file content."


class ListDirTool:
    """List directory contents."""

    def __init__(self, workspace: Path | None = None, allowed_dir: Path | None = None) -> None:
        self._workspace = workspace
        self._allowed_dir = allowed_dir

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_dir",
            description="List the contents of a directory.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The directory path to list"},
                },
                "required": ["path"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        path = call.arguments.get("path", "")
        try:
            dir_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not dir_path.exists():
                return ToolResult(tool_call_id=call.id, content=f"Error: Directory not found: {path}")
            if not dir_path.is_dir():
                return ToolResult(tool_call_id=call.id, content=f"Error: Not a directory: {path}")

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "[DIR] " if item.is_dir() else "[FILE] "
                items.append(f"{prefix}{item.name}")

            if not items:
                return ToolResult(tool_call_id=call.id, content=f"Directory {path} is empty")

            return ToolResult(tool_call_id=call.id, content="\n".join(items))
        except PermissionError as e:
            return ToolResult(tool_call_id=call.id, content=f"Error: {e}", is_error=True)
        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=f"Error listing directory: {e}", is_error=True)
