"""Tests for AgentService — orchestrator."""
import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.domain.value_objects import NLResponse, RiskLevel
from src.infrastructure.agent.agent_service import AgentService
from src.infrastructure.config.loader import AgentConfig


class TestAgentServiceParse:
    """Test JSON parsing logic."""

    def test_parses_valid_json(self) -> None:
        raw = json.dumps({
            "commands": ["ls -la"],
            "explanation": "List files with details",
            "risk_level": "low",
            "assumptions": ["current dir exists"],
            "required_user_confirmation": False,
        })
        result = AgentService._parse(raw)
        assert result is not None
        assert result.commands == ["ls -la"]
        assert result.risk_level == RiskLevel.LOW

    def test_parses_json_in_code_fence(self) -> None:
        raw = '```json\n{"commands":["pwd"],"explanation":"Show cwd","risk_level":"low","assumptions":[],"required_user_confirmation":false}\n```'
        result = AgentService._parse(raw)
        assert result is not None
        assert result.commands == ["pwd"]

    def test_returns_none_for_invalid_json(self) -> None:
        assert AgentService._parse("not json at all") is None

    def test_returns_none_for_missing_keys(self) -> None:
        raw = json.dumps({"commands": ["ls"]})
        assert AgentService._parse(raw) is None

    def test_returns_none_for_invalid_risk(self) -> None:
        raw = json.dumps({
            "commands": ["ls"],
            "explanation": "list",
            "risk_level": "ultra",
            "assumptions": [],
            "required_user_confirmation": False,
        })
        assert AgentService._parse(raw) is None

    def test_returns_none_for_empty_commands(self) -> None:
        raw = json.dumps({
            "commands": [],
            "explanation": "nothing",
            "risk_level": "low",
            "assumptions": [],
            "required_user_confirmation": False,
        })
        assert AgentService._parse(raw) is None


class TestAgentServiceBuildPrompt:
    def test_basic_prompt(self) -> None:
        prompt = AgentService._build_user_prompt("list files", {"cwd": "/home/user"})
        assert "list files" in prompt
        assert "/home/user" in prompt

    def test_with_last_output(self) -> None:
        prompt = AgentService._build_user_prompt("what happened", {
            "cwd": "/tmp",
            "last_output": ["error: file not found", "exit code 1"],
        })
        assert "error: file not found" in prompt

    def test_without_context(self) -> None:
        prompt = AgentService._build_user_prompt("hello", {})
        assert "hello" in prompt


class TestAgentServiceProcess:
    @patch("src.infrastructure.agent.agent_service.ChatAgent")
    @patch("src.infrastructure.agent.agent_service.MemoryStore")
    def test_process_returns_nl_response(self, mock_mem_cls, mock_agent_cls) -> None:
        mock_mem = MagicMock()
        mock_mem.get_memory_context.return_value = ""
        mock_mem_cls.return_value = mock_mem

        # Build valid JSON that will be returned as stream chunks
        valid_json = json.dumps({
            "commands": ["ls -la"],
            "explanation": "List files",
            "risk_level": "low",
            "assumptions": [],
            "required_user_confirmation": False,
        })

        mock_chunk = MagicMock()
        mock_chunk.content = valid_json
        mock_chunk.role = "assistant"

        mock_agent = MagicMock()
        mock_agent.stream_chat.return_value = iter([mock_chunk])
        mock_agent.provider_name = "ollama"
        mock_agent._config = MagicMock()
        mock_agent._config.api_key = None
        mock_agent._model = "llama3.2"
        mock_agent_cls.return_value = mock_agent

        config = AgentConfig(enabled=True, memory_enabled=False)
        service = AgentService(
            provider="ollama",
            model="llama3.2",
            agent_config=config,
        )
        # Override the agent that was already created
        service._agent = mock_agent

        result = service.process("list files", {"cwd": "/tmp"})
        assert result is not None
        assert result.commands == ["ls -la"]

    @patch("src.infrastructure.agent.agent_service.ChatAgent")
    def test_process_returns_none_on_error(self, mock_agent_cls) -> None:
        mock_agent = MagicMock()
        mock_agent.stream_chat.side_effect = RuntimeError("LLM down")
        mock_agent_cls.return_value = mock_agent

        config = AgentConfig(enabled=True, memory_enabled=False)
        service = AgentService(provider="ollama", model="llama3.2", agent_config=config)
        service._agent = mock_agent

        result = service.process("test", {})
        assert result is None

    @patch("src.infrastructure.agent.agent_service.ChatAgent")
    def test_process_calls_on_chunk(self, mock_agent_cls) -> None:
        valid_json = json.dumps({
            "commands": ["echo hi"],
            "explanation": "Say hi",
            "risk_level": "low",
            "assumptions": [],
            "required_user_confirmation": False,
        })

        chunk1 = MagicMock(content='{"commands"', role="assistant")
        chunk2 = MagicMock(content=valid_json[len('{"commands"'):], role="assistant")

        mock_agent = MagicMock()
        mock_agent.stream_chat.return_value = iter([chunk1, chunk2])
        mock_agent_cls.return_value = mock_agent

        config = AgentConfig(enabled=True, memory_enabled=False)
        service = AgentService(provider="ollama", model="llama3.2", agent_config=config)
        service._agent = mock_agent

        chunks_received = []
        service.process("say hi", {}, on_chunk=chunks_received.append)
        assert len(chunks_received) == 2


class TestAgentServiceShutdown:
    @patch("src.infrastructure.agent.agent_service.ChatAgent")
    def test_shutdown_no_crash(self, mock_agent_cls) -> None:
        mock_agent_cls.return_value = MagicMock()
        config = AgentConfig(enabled=True, memory_enabled=False)
        service = AgentService(provider="ollama", model="llama3.2", agent_config=config)
        service.shutdown()  # Should not raise
