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
        agent_config: AgentConfig | None = None,
    ) -> None:
        self._cfg = agent_config or AgentConfig()

        # Build tool registry
        self._registry = ToolRegistry()
        self._register_tools()

        # Build LLM agent with tools
        self._agent = ChatAgent(
            provider=provider,
            api_key=api_key,
            model=model,
            tools=self._registry,
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
            ChatMessage(role="user", content=user_prompt),
        ]

        try:
            raw_content = ""
            for chunk in self._agent.stream_chat(
                messages=messages,
                config=self._config,
                auto_execute_tools=True,
            ):
                if chunk.content and chunk.role == "assistant":
                    raw_content += chunk.content
                    if on_chunk is not None:
                        on_chunk(chunk.content)

            result = self._parse(raw_content)

            # Track interaction for memory
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

    @staticmethod
    def _parse(content: str) -> NLResponse | None:
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
            return NLResponse(
                commands=data["commands"],
                explanation=data["explanation"],
                risk_level=RiskLevel(data["risk_level"]),
                assumptions=data.get("assumptions", []),
                required_user_confirmation=data["required_user_confirmation"],
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("AgentService: invalid schema — %s", exc)
            return None
