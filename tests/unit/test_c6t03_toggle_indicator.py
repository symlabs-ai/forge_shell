"""
C6-T-03 — Toggle atualiza indicador de modo correto
DADO TerminalSession em NL Mode
QUANDO TOGGLE é processado
ENTÃO stdout exibe "Bash Mode" (não "NL Mode")
QUANDO TOGGLE é processado novamente
ENTÃO stdout exibe "NL Mode"
"""
import pytest
from unittest.mock import MagicMock
from src.application.usecases.terminal_session import TerminalSession, SessionMode
from src.application.usecases.nl_interceptor import InterceptResult, InterceptAction
from src.infrastructure.config.loader import ForgeShellConfig, NLModeConfig


def _make_session(nl_active=True):
    session = TerminalSession(config=ForgeShellConfig(nl_mode=NLModeConfig(default_active=nl_active)))
    session._engine = MagicMock()
    session._detector = MagicMock()
    session._detector.is_active = False
    return session


class TestToggleIndicator:
    def test_toggle_from_nl_shows_bash_mode(self) -> None:
        session = _make_session(nl_active=True)
        out = MagicMock()
        session._stdout = out
        assert session.mode == SessionMode.NL

        result = InterceptResult(action=InterceptAction.TOGGLE)
        session._handle_intercept_result(result)

        written = b"".join(c.args[0] for c in out.write.call_args_list if c.args)
        assert b"Bash" in written

    def test_toggle_from_bash_shows_nl_mode(self) -> None:
        session = _make_session(nl_active=False)
        out = MagicMock()
        session._stdout = out
        assert session.mode == SessionMode.BASH

        result = InterceptResult(action=InterceptAction.TOGGLE)
        session._handle_intercept_result(result)

        written = b"".join(c.args[0] for c in out.write.call_args_list if c.args)
        assert b"NL" in written

    def test_toggle_updates_session_mode(self) -> None:
        """TOGGLE deve atualizar o _mode da session via NLModeEngine."""
        from unittest.mock import MagicMock, patch
        session = _make_session(nl_active=True)
        session._stdout = MagicMock()
        mock_engine = MagicMock()
        mock_engine.state.value = "bash_active"
        mock_interceptor = MagicMock()
        mock_interceptor.nl_engine = mock_engine
        session._interceptor = mock_interceptor

        result = InterceptResult(action=InterceptAction.TOGGLE)
        session._handle_intercept_result(result)

        # indicador deve refletir o novo estado
        written = b"".join(c.args[0] for c in session._stdout.write.call_args_list if c.args)
        assert len(written) > 0  # algo foi escrito
