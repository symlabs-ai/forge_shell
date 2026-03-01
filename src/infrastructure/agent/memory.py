"""MemoryStore — two-layer persistent memory for the agent.

- MEMORY.md: long-term facts (overwritten by LLM consolidation)
- HISTORY.md: append-only grep-searchable log with timestamps

Adapted from nanobot MemoryStore for sync execution.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from forge_llm import ChatAgent, ChatConfig, ChatMessage

log = logging.getLogger(__name__)

_SAVE_MEMORY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_memory",
        "description": "Save the memory consolidation result to persistent storage.",
        "parameters": {
            "type": "object",
            "properties": {
                "history_entry": {
                    "type": "string",
                    "description": (
                        "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search."
                    ),
                },
                "memory_update": {
                    "type": "string",
                    "description": (
                        "Full updated long-term memory as markdown. Include all existing "
                        "facts plus new ones. Return unchanged if nothing new."
                    ),
                },
            },
            "required": ["history_entry", "memory_update"],
        },
    },
}


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""

    def __init__(self, memory_dir: Path) -> None:
        self._memory_dir = memory_dir
        self._memory_file = memory_dir / "MEMORY.md"
        self._history_file = memory_dir / "HISTORY.md"

    def ensure_dir(self) -> None:
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def read_long_term(self) -> str:
        if self._memory_file.exists():
            return self._memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        self.ensure_dir()
        self._memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        self.ensure_dir()
        with open(self._history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    def consolidate(
        self,
        agent: ChatAgent,
        interactions: list[dict[str, str]],
    ) -> bool:
        """Consolidate recent interactions into MEMORY.md + HISTORY.md via LLM tool call.

        Returns True on success, False on failure.
        """
        if not interactions:
            return True

        lines: list[str] = []
        for entry in interactions:
            ts = entry.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
            role = entry.get("role", "user").upper()
            content = entry.get("content", "")
            lines.append(f"[{ts}] {role}: {content}")

        current_memory = self.read_long_term()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{chr(10).join(lines)}"""

        from forge_llm.domain.entities import ToolDefinition, ToolCall as ForgeLLMToolCall

        try:
            response = agent.chat(
                messages=[
                    ChatMessage(role="system", content="You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."),
                    ChatMessage(role="user", content=prompt),
                ],
                config=ChatConfig(temperature=0.3),
                auto_execute_tools=False,
            )

            if not response.message.tool_calls:
                log.warning("Memory consolidation: LLM did not call save_memory")
                return False

            raw_tc = response.message.tool_calls[0]
            args = raw_tc.get("function", {}).get("arguments", "{}")
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                log.warning("Memory consolidation: unexpected arguments type %s", type(args).__name__)
                return False

            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)

            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)

            log.info("Memory consolidation done: %d interactions processed", len(interactions))
            return True
        except Exception:
            log.exception("Memory consolidation failed")
            return False
