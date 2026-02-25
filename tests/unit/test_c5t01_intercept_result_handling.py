"""
C5-T-01 — TerminalSession usa InterceptResult corretamente
DADO _route_input com interceptor configurado
QUANDO interceptor retorna EXEC_BASH
ENTÃO engine.write() recebe o bash_command + newline
QUANDO interceptor retorna TOGGLE
ENTÃO stdout recebe indicador de modo
QUANDO interceptor retorna SHOW_SUGGESTION
ENTÃO stdout recebe texto da sugestão e PTY recebe o comando
QUANDO interceptor retorna NOOP
ENTÃO engine.write() não é chamado
"""
import pytest
from unittest.mock import MagicMock, patch
from src.application.usecases.terminal_session import TerminalSession
from src.application.usecases.nl_interceptor import InterceptResult, InterceptAction
from src.infrastructure.config.loader import SymShellConfig, NLModeConfig


def _make_session():
    config = SymShellConfig(nl_mode=NLModeConfig(default_active=True))
    session = TerminalSession(config=config)
    session._engine = MagicMock()
    session._engine.write = MagicMock()
    session._stdout = MagicMock()
    session._detector = MagicMock()
    session._detector.is_active = False
    return session


class TestInterceptResultHandling:
    def test_exec_bash_writes_to_pty(self) -> None:
        session = _make_session()
        mock_interceptor = MagicMock()
        mock_interceptor.intercept.return_value = InterceptResult(
            action=InterceptAction.EXEC_BASH,
            bash_command="ls -la",
        )
        session._interceptor = mock_interceptor
        session._route_input(b"!ls -la\n")
        session._engine.write.assert_called_once_with(b"ls -la\n")

    def test_noop_does_not_write_to_pty(self) -> None:
        session = _make_session()
        mock_interceptor = MagicMock()
        mock_interceptor.intercept.return_value = InterceptResult(
            action=InterceptAction.NOOP,
        )
        session._interceptor = mock_interceptor
        session._route_input(b"some text\n")
        session._engine.write.assert_not_called()

    def test_toggle_writes_mode_indicator_to_stdout(self) -> None:
        session = _make_session()
        mock_interceptor = MagicMock()
        mock_interceptor.intercept.return_value = InterceptResult(
            action=InterceptAction.TOGGLE,
        )
        session._interceptor = mock_interceptor
        session._route_input(b"!\n")
        # stdout deve receber algo (indicador de modo)
        assert session._stdout.write.called

    def test_toggle_indicator_contains_mode_text(self) -> None:
        session = _make_session()
        mock_interceptor = MagicMock()
        mock_interceptor.intercept.return_value = InterceptResult(
            action=InterceptAction.TOGGLE,
        )
        session._interceptor = mock_interceptor
        session._route_input(b"!\n")
        written = b"".join(
            call.args[0] for call in session._stdout.write.call_args_list
            if call.args
        )
        assert b"Mode" in written or b"mode" in written or b"NL" in written or b"Bash" in written

    def test_show_suggestion_writes_suggestion_to_stdout(self) -> None:
        session = _make_session()
        from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel
        mock_interceptor = MagicMock()
        mock_resp = NLResponse(
            commands=["find . -name '*.py'"],
            explanation="Lista arquivos Python",
            risk_level=RiskLevel.LOW,
            assumptions=[],
            required_user_confirmation=False,
        )
        mock_interceptor.intercept.return_value = InterceptResult(
            action=InterceptAction.SHOW_SUGGESTION,
            suggestion=mock_resp,
        )
        session._interceptor = mock_interceptor
        session._route_input(b"list python files\n")
        written = b"".join(
            call.args[0] for call in session._stdout.write.call_args_list
            if call.args
        )
        # deve exibir o comando sugerido
        assert b"find" in written or b"*.py" in written

    def test_show_suggestion_injects_command_into_pty(self) -> None:
        session = _make_session()
        from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel
        mock_interceptor = MagicMock()
        mock_resp = NLResponse(
            commands=["ls *.py"],
            explanation="Lista arquivos Python",
            risk_level=RiskLevel.LOW,
            assumptions=[],
            required_user_confirmation=False,
        )
        mock_interceptor.intercept.return_value = InterceptResult(
            action=InterceptAction.SHOW_SUGGESTION,
            suggestion=mock_resp,
        )
        session._interceptor = mock_interceptor
        session._route_input(b"list python files\n")
        # para risco baixo: injeta o comando no PTY para o usuário revisar e pressionar Enter
        session._engine.write.assert_called()
        written_to_pty = session._engine.write.call_args[0][0]
        assert b"ls *.py" in written_to_pty
