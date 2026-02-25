"""
C2-T-05 + C2-T-06 — NLInterceptor + integração com TerminalSession
DADO o NLInterceptor com NLModeEngine mockado
QUANDO recebo bytes de input
ENTÃO toggle/escape/NL/bash são roteados corretamente e o output é produzido
"""
import pytest
from unittest.mock import MagicMock, patch

from src.application.usecases.nl_interceptor import NLInterceptor, InterceptResult, InterceptAction
from src.application.usecases.nl_mode_engine import NLModeState
from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel


def _mock_engine(state=NLModeState.NL_ACTIVE):
    engine = MagicMock()
    engine.state = state
    return engine


class TestNLInterceptor:
    def test_bang_alone_toggles_mode(self) -> None:
        nl_engine = _mock_engine()
        nl_engine.process_input.return_value = None  # toggle retorna None
        interceptor = NLInterceptor(nl_engine=nl_engine)
        result = interceptor.intercept(b"!\n")
        assert result.action == InterceptAction.TOGGLE

    def test_bang_cmd_returns_bash_command(self) -> None:
        nl_engine = _mock_engine()
        from src.application.usecases.nl_mode_engine import NLResult
        nl_engine.process_input.return_value = NLResult(bash_command="ls -la")
        interceptor = NLInterceptor(nl_engine=nl_engine)
        result = interceptor.intercept(b"!ls -la\n")
        assert result.action == InterceptAction.EXEC_BASH
        assert result.bash_command == "ls -la"

    def test_nl_text_returns_suggestion(self) -> None:
        nl_engine = _mock_engine()
        from src.application.usecases.nl_mode_engine import NLResult
        suggestion = NLResponse(
            commands=["ls -la"],
            explanation="Lista arquivos",
            risk_level=RiskLevel.LOW,
            assumptions=[],
            required_user_confirmation=False,
        )
        nl_engine.process_input.return_value = NLResult(suggestion=suggestion)
        interceptor = NLInterceptor(nl_engine=nl_engine)
        result = interceptor.intercept(b"list all files\n")
        assert result.action == InterceptAction.SHOW_SUGGESTION
        assert result.suggestion is not None

    def test_bash_mode_passthrough(self) -> None:
        nl_engine = _mock_engine(state=NLModeState.BASH_ACTIVE)
        from src.application.usecases.nl_mode_engine import NLResult
        nl_engine.process_input.return_value = NLResult(bash_command="ls")
        interceptor = NLInterceptor(nl_engine=nl_engine)
        result = interceptor.intercept(b"ls\n")
        assert result.action == InterceptAction.EXEC_BASH
        assert result.bash_command == "ls"

    def test_nl_engine_called_with_stripped_text(self) -> None:
        nl_engine = _mock_engine()
        nl_engine.process_input.return_value = None
        interceptor = NLInterceptor(nl_engine=nl_engine)
        interceptor.intercept(b"  hello world  \n")
        call_args = nl_engine.process_input.call_args
        text_arg = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
        assert text_arg.strip() == "hello world"

    def test_empty_input_returns_noop(self) -> None:
        nl_engine = _mock_engine()
        nl_engine.process_input.return_value = None
        interceptor = NLInterceptor(nl_engine=nl_engine)
        result = interceptor.intercept(b"\n")
        assert result.action in (InterceptAction.NOOP, InterceptAction.TOGGLE)

    def test_intercept_result_has_high_risk_flag(self) -> None:
        nl_engine = _mock_engine()
        from src.application.usecases.nl_mode_engine import NLResult
        suggestion = NLResponse(
            commands=["rm -rf /"],
            explanation="Apaga tudo",
            risk_level=RiskLevel.HIGH,
            assumptions=[],
            required_user_confirmation=True,
        )
        nl_engine.process_input.return_value = NLResult(
            suggestion=suggestion, requires_double_confirm=True
        )
        interceptor = NLInterceptor(nl_engine=nl_engine)
        result = interceptor.intercept(b"delete everything\n")
        assert result.requires_double_confirm is True


class TestInterceptResult:
    def test_result_fields(self) -> None:
        r = InterceptResult(action=InterceptAction.EXEC_BASH, bash_command="ls")
        assert r.bash_command == "ls"
        assert r.suggestion is None
        assert r.requires_double_confirm is False
