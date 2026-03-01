"""SondaTool — silent subprocess execution for agent investigation.

Runs commands silently (no PTY output), captures stdout/stderr, returns to LLM.
Adapted from nanobot ExecTool for sync execution.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from forge_llm.domain.entities import ToolCall, ToolDefinition, ToolResult

_DEFAULT_DENY_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fq]\b",
    r"\brmdir\s+/s\b",
    r"(?:^|[;&|]\s*)format\b",
    r"\b(mkfs|diskpart)\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{.*\};\s*:",
]

_MAX_OUTPUT = 10_000


class SondaTool:
    """Silent shell probe — runs command, captures output, returns to LLM."""

    def __init__(
        self,
        timeout: int = 60,
        deny_patterns: list[str] | None = None,
        extra_deny_patterns: list[str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._deny_patterns = deny_patterns if deny_patterns is not None else list(_DEFAULT_DENY_PATTERNS)
        if extra_deny_patterns:
            self._deny_patterns.extend(extra_deny_patterns)

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sonda",
            description=(
                "Execute a shell command silently and return its output. "
                "Use for investigation: reading configs, checking status, listing files, etc. "
                "Destructive commands (rm -rf, dd, format, shutdown) are blocked."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Optional working directory for the command",
                    },
                },
                "required": ["command"],
            },
        )

    def execute(self, call: ToolCall) -> ToolResult:
        command = call.arguments.get("command", "")
        working_dir = call.arguments.get("working_dir") or os.getcwd()

        guard_error = self._guard_command(command)
        if guard_error:
            return ToolResult(tool_call_id=call.id, content=guard_error, is_error=True)

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=self._timeout,
                cwd=working_dir,
            )

            parts: list[str] = []
            if proc.stdout:
                parts.append(proc.stdout.decode("utf-8", errors="replace"))
            if proc.stderr:
                stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()
                if stderr_text:
                    parts.append(f"STDERR:\n{stderr_text}")
            if proc.returncode != 0:
                parts.append(f"\nExit code: {proc.returncode}")

            result = "\n".join(parts) if parts else "(no output)"

            if len(result) > _MAX_OUTPUT:
                result = result[:_MAX_OUTPUT] + f"\n... (truncated, {len(result) - _MAX_OUTPUT} more chars)"

            return ToolResult(tool_call_id=call.id, content=result)

        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_call_id=call.id,
                content=f"Error: Command timed out after {self._timeout} seconds",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=f"Error executing command: {e}", is_error=True)

    def _guard_command(self, command: str) -> str | None:
        lower = command.strip().lower()
        for pattern in self._deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"
        return None
