"""
C6-T-02 — Double-confirm para HIGH risk
DADO _handle_intercept_result com sugestão de risco alto
QUANDO requires_double_confirm=True
ENTÃO PTY não recebe o comando imediatamente
ENTÃO stdout exibe prompt de confirmação
QUANDO requires_double_confirm=False (risco baixo)
ENTÃO PTY recebe o comando imediatamente sem perguntar
"""
import pytest
from unittest.mock import MagicMock
from src.application.usecases.terminal_session import TerminalSession
from src.application.usecases.nl_interceptor import InterceptResult, InterceptAction
from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel
from src.infrastructure.config.loader import SymShellConfig


def _make_session():
    session = TerminalSession(config=SymShellConfig())
    session._engine = MagicMock()
    session._stdout = MagicMock()
    session._detector = MagicMock()
    session._detector.is_active = False
    return session


def _make_suggestion(risk: RiskLevel, requires_double_confirm: bool, cmd="rm -rf /tmp/x"):
    resp = NLResponse(
        commands=[cmd],
        explanation="Remove arquivos",
        risk_level=risk,
        assumptions=[],
        required_user_confirmation=requires_double_confirm,
    )
    return InterceptResult(
        action=InterceptAction.SHOW_SUGGESTION,
        suggestion=resp,
        requires_double_confirm=requires_double_confirm,
    )


class TestDoubleConfirm:
    def test_low_risk_injects_command_immediately(self) -> None:
        session = _make_session()
        result = _make_suggestion(RiskLevel.LOW, False, "ls -la")
        session._handle_intercept_result(result)
        session._engine.write.assert_called()
        written = session._engine.write.call_args[0][0]
        assert b"ls -la" in written

    def test_high_risk_does_not_inject_command_immediately(self) -> None:
        session = _make_session()
        result = _make_suggestion(RiskLevel.HIGH, True, "rm -rf /tmp/x")
        session._handle_intercept_result(result)
        # PTY não deve receber o comando sem confirmação
        session._engine.write.assert_not_called()

    def test_high_risk_shows_confirmation_prompt(self) -> None:
        session = _make_session()
        result = _make_suggestion(RiskLevel.HIGH, True, "rm -rf /tmp/x")
        session._handle_intercept_result(result)
        written = b"".join(
            c.args[0] for c in session._stdout.write.call_args_list if c.args
        )
        # deve exibir aviso de risco alto e pedir confirmação
        assert b"rm -rf" in written or b"alto" in written.lower() or b"high" in written.lower() or b"confirm" in written.lower()

    def test_high_risk_prompt_shows_command(self) -> None:
        session = _make_session()
        result = _make_suggestion(RiskLevel.HIGH, True, "dd if=/dev/zero of=/dev/sda")
        session._handle_intercept_result(result)
        written = b"".join(
            c.args[0] for c in session._stdout.write.call_args_list if c.args
        )
        assert b"dd" in written

    def test_medium_risk_injects_without_double_confirm(self) -> None:
        """Risco médio sem requires_double_confirm deve injetar normalmente."""
        session = _make_session()
        result = _make_suggestion(RiskLevel.MEDIUM, False, "chmod 755 file.sh")
        session._handle_intercept_result(result)
        session._engine.write.assert_called()
