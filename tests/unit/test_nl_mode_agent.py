"""Tests for NL Mode agent routing — agent vs LLM, toggle/escape/help inalterados."""
from unittest.mock import MagicMock

import pytest

from src.application.usecases.nl_mode_engine import NLModeEngine, NLModeState
from src.domain.value_objects import NLResponse, RiskLevel
from src.infrastructure.intelligence.forge_llm_adapter import ForgeLLMAdapter
from src.infrastructure.intelligence.risk_engine import RiskEngine


def _make_response(**overrides) -> NLResponse:
    defaults = {
        "commands": ["ls -la"],
        "explanation": "List files",
        "risk_level": RiskLevel.LOW,
        "assumptions": [],
        "required_user_confirmation": False,
    }
    defaults.update(overrides)
    return NLResponse(**defaults)


def _engine(agent=None, adapter_response=None):
    adapter = MagicMock(spec=ForgeLLMAdapter)
    adapter.request.return_value = adapter_response
    adapter.explain.return_value = adapter_response
    risk = RiskEngine()
    return NLModeEngine(llm_adapter=adapter, risk_engine=risk, agent_service=agent), adapter


class TestAgentRouting:
    def test_nl_routes_to_agent_when_present(self) -> None:
        agent = MagicMock()
        resp = _make_response()
        agent.process.return_value = resp
        engine, adapter = _engine(agent=agent)

        result = engine.process_input("list files", {})
        assert result is not None
        assert result.suggestion == resp
        agent.process.assert_called_once()
        adapter.request.assert_not_called()

    def test_nl_routes_to_adapter_when_no_agent(self) -> None:
        resp = _make_response()
        engine, adapter = _engine(adapter_response=resp)

        result = engine.process_input("list files", {})
        assert result is not None
        assert result.suggestion == resp
        adapter.request.assert_called_once()

    def test_agent_none_response(self) -> None:
        agent = MagicMock()
        agent.process.return_value = None
        engine, _ = _engine(agent=agent)

        result = engine.process_input("do something impossible", {})
        assert result is not None
        assert result.suggestion is None


class TestAgentDoesNotAffectExistingBehavior:
    """Toggle, escape, help, risk, explain, builtins — all unchanged with agent."""

    def test_toggle_unchanged(self) -> None:
        agent = MagicMock()
        engine, _ = _engine(agent=agent)
        result = engine.process_input("!", {})
        assert result is None
        assert engine.state == NLModeState.BASH_ACTIVE
        agent.process.assert_not_called()

    def test_escape_unchanged(self) -> None:
        agent = MagicMock()
        engine, _ = _engine(agent=agent)
        result = engine.process_input("!git status", {})
        assert result is not None
        assert result.bash_command == "git status"
        agent.process.assert_not_called()

    def test_help_unchanged(self) -> None:
        agent = MagicMock()
        engine, _ = _engine(agent=agent)
        result = engine.process_input(":help", {})
        assert result is not None
        assert result.is_help is True
        agent.process.assert_not_called()

    def test_risk_unchanged(self) -> None:
        agent = MagicMock()
        engine, _ = _engine(agent=agent)
        result = engine.process_input(":risk rm -rf /", {})
        assert result is not None
        assert result.is_risk is True
        agent.process.assert_not_called()

    def test_explain_uses_adapter_not_agent(self) -> None:
        agent = MagicMock()
        resp = _make_response()
        engine, adapter = _engine(agent=agent, adapter_response=resp)

        result = engine.process_input(":explain ls -la", {})
        assert result is not None
        assert result.is_explanation is True
        adapter.explain.assert_called_once()
        agent.process.assert_not_called()

    def test_exit_builtin_unchanged(self) -> None:
        agent = MagicMock()
        engine, _ = _engine(agent=agent)
        result = engine.process_input("exit", {})
        assert result is not None
        assert result.bash_command == "exit"
        agent.process.assert_not_called()

    def test_bash_mode_passthrough_unchanged(self) -> None:
        agent = MagicMock()
        engine, _ = _engine(agent=agent)
        engine.toggle()  # switch to bash mode
        result = engine.process_input("ls", {})
        assert result is not None
        assert result.bash_command == "ls"
        agent.process.assert_not_called()

    def test_on_chunk_forwarded_to_agent(self) -> None:
        agent = MagicMock()
        agent.process.return_value = _make_response()
        engine, _ = _engine(agent=agent)

        chunks = []
        engine.process_input("test", {}, on_chunk=chunks.append)
        # Verify agent.process was called with on_chunk
        call_kwargs = agent.process.call_args
        assert call_kwargs[1].get("on_chunk") is not None or call_kwargs[0][2] is not None
