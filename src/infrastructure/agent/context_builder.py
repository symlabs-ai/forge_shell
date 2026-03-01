"""AgentContextBuilder — builds system prompt for the agent.

Composes: identity + runtime info + memory + response format.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path

from src.infrastructure.agent.memory import MemoryStore

_RESPONSE_FORMAT = """\
Respond ONLY with valid JSON matching this schema (no markdown, no extra text):
{
  "commands": ["<bash command 1>", "..."],
  "explanation": "<short explanation of what will happen>",
  "risk_level": "low" | "medium" | "high",
  "assumptions": ["<assumption 1>", "..."],
  "required_user_confirmation": true | false
}

risk_level criteria:
- low: read, list, info — no side effects
- medium: reversible modification, process kill, service restart
- high: irreversible deletion, format, critical system file changes"""


class AgentContextBuilder:
    """Builds the system prompt for the agent."""

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self._memory = memory

    def build_system_prompt(self) -> str:
        sections: list[str] = []

        sections.append(self._identity())

        if self._memory:
            mem_ctx = self._memory.get_memory_context()
            if mem_ctx:
                sections.append(mem_ctx)

        sections.append(self._tools_guidance())
        sections.append(_RESPONSE_FORMAT)

        return "\n\n".join(sections)

    @staticmethod
    def _identity() -> str:
        cwd = os.getcwd()
        user = os.environ.get("USER", "unknown")
        shell = os.environ.get("SHELL", "/bin/bash")
        uname = platform.uname()
        return f"""You are an intelligent terminal assistant inside forge_shell.
You have access to tools to investigate the environment before suggesting commands.

## Runtime
- User: {user}
- Shell: {shell}
- OS: {uname.system} {uname.release}
- CWD: {cwd}

## Guidelines
- Use tools (read_file, list_dir, sonda) to investigate before answering
- Do NOT guess — verify paths, file contents, running processes
- Use web_search/web_fetch only when local investigation is insufficient
- After investigation, produce a final JSON response with the suggested command(s)
- If you cannot determine a safe command, explain why in the explanation field"""

    @staticmethod
    def _tools_guidance() -> str:
        return """## Available Tools
- read_file: Read file contents (UTF-8)
- write_file: Write/create a file
- edit_file: Surgical edit with old_text/new_text replacement
- list_dir: List directory contents
- sonda: Execute shell command silently, capture output (for investigation only)
- web_search: Search the web via Brave Search API
- web_fetch: Fetch URL and extract readable content"""
