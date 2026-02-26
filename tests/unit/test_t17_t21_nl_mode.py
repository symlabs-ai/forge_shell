"""
T-17 a T-21 — NL Mode Engine
DADO o motor de NL Mode
QUANDO processo input do usuário
ENTÃO o modo correto é ativado e o fluxo de confirmação é respeitado
"""
import pytest
from unittest.mock import MagicMock
from src.application.usecases.nl_mode_engine import NLModeEngine, NLModeState
from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel


def _make_response(risk: RiskLevel = RiskLevel.LOW) -> NLResponse:
    return NLResponse(
        commands=["ls -la"],
        explanation="Lista arquivos",
        risk_level=risk,
        assumptions=[],
        required_user_confirmation=True,
    )


class TestNLModeState:
    def test_starts_in_nl_mode(self) -> None:
        engine = NLModeEngine(llm_adapter=MagicMock(), risk_engine=MagicMock())
        assert engine.state == NLModeState.NL_ACTIVE

    def test_toggle_switches_to_bash(self) -> None:
        engine = NLModeEngine(llm_adapter=MagicMock(), risk_engine=MagicMock())
        engine.toggle()
        assert engine.state == NLModeState.BASH_ACTIVE

    def test_toggle_switches_back_to_nl(self) -> None:
        engine = NLModeEngine(llm_adapter=MagicMock(), risk_engine=MagicMock())
        engine.toggle()
        engine.toggle()
        assert engine.state == NLModeState.NL_ACTIVE


class TestNLModeInputProcessing:
    def _engine_with_response(self, resp: NLResponse | None) -> NLModeEngine:
        adapter = MagicMock()
        adapter.request.return_value = resp
        risk = MagicMock()
        risk.classify.return_value = resp.risk_level if resp else RiskLevel.LOW
        risk.requires_double_confirm.return_value = resp.risk_level == RiskLevel.HIGH if resp else False
        return NLModeEngine(llm_adapter=adapter, risk_engine=risk)

    def test_nl_text_calls_adapter(self) -> None:
        resp = _make_response()
        engine = self._engine_with_response(resp)
        result = engine.process_input("listar arquivos", context={})
        assert result is not None
        assert result.suggestion == resp

    def test_bang_toggle_switches_mode(self) -> None:
        engine = self._engine_with_response(None)
        result = engine.process_input("!", context={})
        assert result is None  # toggle não retorna sugestão
        assert engine.state == NLModeState.BASH_ACTIVE

    def test_bang_command_is_bash_escape(self) -> None:
        engine = self._engine_with_response(None)
        result = engine.process_input("!ls -la", context={})
        assert result is not None
        assert result.bash_command == "ls -la"
        assert engine.state == NLModeState.NL_ACTIVE  # retorna ao NL Mode

    def test_llm_failure_returns_none(self) -> None:
        engine = self._engine_with_response(None)
        result = engine.process_input("fazer algo", context={})
        assert result is None or result.suggestion is None

    def test_high_risk_requires_double_confirm(self) -> None:
        resp = _make_response(risk=RiskLevel.HIGH)
        engine = self._engine_with_response(resp)
        result = engine.process_input("apagar tudo", context={})
        assert result is not None
        assert result.requires_double_confirm is True

    def test_low_risk_no_double_confirm(self) -> None:
        resp = _make_response(risk=RiskLevel.LOW)
        engine = self._engine_with_response(resp)
        result = engine.process_input("listar arquivos", context={})
        assert result is not None
        assert result.requires_double_confirm is False

    def test_bash_mode_passthrough(self) -> None:
        engine = self._engine_with_response(None)
        engine.toggle()  # switch to bash
        result = engine.process_input("ls -la", context={})
        assert result is not None
        assert result.bash_command == "ls -la"

    def test_exit_in_nl_mode_bypasses_llm(self) -> None:
        """exit nunca deve ir ao LLM — sai direto como bash command."""
        adapter = MagicMock()
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=MagicMock())
        result = engine.process_input("exit", context={})
        assert result is not None
        assert result.bash_command == "exit"
        adapter.request.assert_not_called()

    def test_logout_in_nl_mode_bypasses_llm(self) -> None:
        """logout nunca deve ir ao LLM — sai direto como bash command."""
        adapter = MagicMock()
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=MagicMock())
        result = engine.process_input("logout", context={})
        assert result is not None
        assert result.bash_command == "logout"
        adapter.request.assert_not_called()
