"""AgentService — orchestrates LLM + tools + memory for NL Mode.

Implements AgentPort. Uses forge_llm ChatAgent with ToolRegistry
and stream_chat(auto_execute_tools=True) for multi-round tool calling.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from forge_llm import ChatAgent, ChatConfig, ChatMessage
from forge_llm.application.tools import ToolRegistry
from forge_llm.domain.entities import ToolDefinition

from src.application.ports.agent_port import AgentPort
from src.domain.value_objects import NLResponse, RiskLevel
from src.infrastructure.agent.context_builder import AgentContextBuilder
from src.infrastructure.agent.memory import MemoryStore
from src.infrastructure.agent.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from src.infrastructure.agent.tools.shell import SondaTool
from src.infrastructure.agent.tools.web import WebFetchTool, WebSearchTool
from src.infrastructure.config.loader import AgentConfig

log = logging.getLogger(__name__)


class AgentService(AgentPort):
    """Orchestrates the agent system: tools + LLM + memory."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        agent_config: AgentConfig | None = None,
    ) -> None:
        self._cfg = agent_config or AgentConfig()

        # Build tool registry
        self._registry = ToolRegistry()
        self._register_tools()

        # Build LLM agent with tools
        kwargs: dict = {}
        if base_url:
            kwargs["base_url"] = base_url
        self._agent = ChatAgent(
            provider=provider,
            api_key=api_key,
            model=model,
            tools=self._registry,
            **kwargs,
        )
        self._config = ChatConfig(temperature=0.2)

        # Memory
        self._memory: MemoryStore | None = None
        if self._cfg.memory_enabled:
            mem_dir = Path.home() / ".forge_shell" / "agent" / "memory"
            self._memory = MemoryStore(mem_dir)
            self._memory.ensure_dir()

        # Context builder
        self._context_builder = AgentContextBuilder(memory=self._memory)

        # Conversation history (user/assistant pairs for context)
        self._conversation_history: list[ChatMessage] = []
        self._max_history_pairs = 5  # keep last N exchanges

        # Interaction tracking for memory consolidation
        self._interactions: list[dict[str, str]] = []
        self._interaction_count = 0

    def _register_tools(self) -> None:
        workspace = Path.home()
        self._registry.register(ReadFileTool(workspace=workspace))
        self._registry.register(WriteFileTool(workspace=workspace))
        self._registry.register(EditFileTool(workspace=workspace))
        self._registry.register(ListDirTool(workspace=workspace))
        self._registry.register(SondaTool(
            timeout=self._cfg.exec_timeout,
            extra_deny_patterns=self._cfg.exec_deny_patterns or None,
        ))
        self._registry.register(WebSearchTool(api_key=self._cfg.brave_api_key))
        self._registry.register(WebFetchTool(max_chars=self._cfg.web_fetch_max_chars))

    def process(
        self,
        text: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResponse | None:
        """Process NL query using tools and return structured response."""
        system_prompt = self._context_builder.build_system_prompt()
        user_prompt = self._build_user_prompt(text, context)

        messages = [
            ChatMessage(role="system", content=system_prompt),
            *self._conversation_history,
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            raw_content = ""
            for chunk in self._agent.stream_chat(
                messages=messages,
                config=self._config,
                auto_execute_tools=True,
            ):
                # Tool call — emit sonda activity
                if (
                    chunk.role == "assistant"
                    and chunk.finish_reason == "tool_calls"
                    and chunk.tool_calls
                    and on_chunk is not None
                ):
                    for tc in chunk.tool_calls:
                        func = tc.get("function", {})
                        name = func.get("name", "?")
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        if name == "sonda" and isinstance(args, dict):
                            cmd = args.get("command", "")
                            on_chunk(f"\n\033[35m[sonda]\033[0m {cmd}")
                        elif name in ("list_dir", "read_file"):
                            path = args.get("path", "") if isinstance(args, dict) else str(args)
                            on_chunk(f"\n\033[35m[{name}]\033[0m {path}")

                # Tool result — emit output summary
                elif chunk.role == "tool" and chunk.content and on_chunk is not None:
                    content = chunk.content
                    if content.startswith("[Tool "):
                        content = content.split("]: ", 1)[-1]
                    lines = content.strip().splitlines()
                    if lines:
                        first = lines[0][:100]
                        if len(lines) > 1:
                            on_chunk(f"\n\033[32m   → {first}  \033[2m(+{len(lines)-1} linhas)\033[0m")
                        else:
                            on_chunk(f"\n\033[32m   → {first}\033[0m")

                # Regular assistant content
                elif chunk.content and chunk.role == "assistant":
                    raw_content += chunk.content
                    if on_chunk is not None:
                        on_chunk(chunk.content)

            result = self._parse(raw_content)

            # Track conversation history for context
            self._conversation_history.append(
                ChatMessage(role="user", content=user_prompt)
            )
            if result:
                # Store a concise summary as assistant response
                summary = f"Commands: {result.commands} | {result.explanation}"
            else:
                summary = raw_content[:200] if raw_content else "(no response)"
            self._conversation_history.append(
                ChatMessage(role="assistant", content=summary)
            )
            # Trim history to max pairs
            max_msgs = self._max_history_pairs * 2
            if len(self._conversation_history) > max_msgs:
                self._conversation_history = self._conversation_history[-max_msgs:]

            # Track interaction for memory consolidation
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            self._interactions.append({"timestamp": ts, "role": "user", "content": text})
            if result:
                self._interactions.append({
                    "timestamp": ts,
                    "role": "assistant",
                    "content": f"Commands: {result.commands} | {result.explanation}",
                })
            self._interaction_count += 1

            # Consolidate memory periodically
            if (
                self._memory
                and self._cfg.memory_consolidate_every > 0
                and self._interaction_count % self._cfg.memory_consolidate_every == 0
                and self._interactions
            ):
                self._consolidate_memory()

            return result

        except Exception as exc:
            log.warning("AgentService error: %s", exc)
            return None

    def shutdown(self) -> None:
        """Consolidate remaining memory on shutdown."""
        if self._memory and self._interactions:
            self._consolidate_memory()

    def _consolidate_memory(self) -> None:
        if self._memory is None:
            return
        # Use a separate agent without tools for consolidation
        consolidation_agent = ChatAgent(
            provider=self._agent.provider_name,
            api_key=self._agent._config.api_key,
            model=self._agent._model,
        )
        self._memory.consolidate(consolidation_agent, self._interactions)
        self._interactions.clear()

    @staticmethod
    def _build_user_prompt(text: str, context: dict) -> str:
        parts = [f"User request: {text}"]
        if context.get("cwd"):
            parts.append(f"Current directory: {context['cwd']}")
        if context.get("last_output"):
            last_lines = context["last_output"]
            if isinstance(last_lines, list):
                last_lines = "\n".join(last_lines)
            parts.append(f"Recent terminal output:\n{last_lines}")
        return "\n".join(parts)

    # Tool names that must never appear as bash commands, with bash equivalents
    _TOOL_BASH_MAP: dict[str, str | None] = {
        "sonda": None,       # sonda wraps a real command — just strip the prefix
        "read_file": "cat",  # read_file <path> → cat <path>
        "list_dir": "ls",    # list_dir <path> → ls <path>
        "write_file": None,  # no safe equivalent
        "edit_file": None,   # no safe equivalent
        "web_search": None,  # no bash equivalent
        "web_fetch": "curl", # web_fetch <url> → curl <url>
    }

    @classmethod
    def _sanitize_commands(cls, commands: list[str]) -> list[str]:
        """Replace tool name prefixes that the LLM mistakenly placed in commands."""
        sanitized: list[str] = []
        for cmd in commands:
            first_token = cmd.split()[0] if cmd.strip() else ""
            if first_token in cls._TOOL_BASH_MAP:
                rest = cmd[len(first_token):].strip()
                replacement = cls._TOOL_BASH_MAP[first_token]
                if rest:
                    if replacement:
                        fixed = f"{replacement} {rest}"
                    else:
                        fixed = rest
                    log.info("Fixed tool-as-command '%s' → '%s'", cmd, fixed)
                    sanitized.append(fixed)
                else:
                    log.warning("Rejected tool-only command: %s", cmd)
            else:
                sanitized.append(cmd)
        return sanitized

    @classmethod
    def _parse(cls, content: str) -> NLResponse | None:
        """Parse LLM JSON response into NLResponse."""
        # Strip markdown code fences if present
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            log.warning("AgentService: response is not valid JSON")
            return None

        try:
            commands = cls._sanitize_commands(data["commands"])
            if not commands:
                log.warning("AgentService: all commands were tool names, rejected")
                return None
            return NLResponse(
                commands=commands,
                explanation=data["explanation"],
                risk_level=RiskLevel(data["risk_level"]),
                assumptions=data.get("assumptions", []),
                required_user_confirmation=data["required_user_confirmation"],
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("AgentService: invalid schema — %s", exc)
            return None
