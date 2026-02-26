"""
C3-T-04 — TerminalSession I/O loop integration
DADO um TerminalSession com PTY real e stdin/stdout mockados
QUANDO processo input e output
ENTÃO o roteamento funciona end-to-end sem I/O real de console
"""
import io
import os
import sys
import time
import threading
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="PTY não disponível no Windows"
)

from src.application.usecases.terminal_session import TerminalSession, SessionMode
from src.infrastructure.config.loader import ForgeShellConfig, NLModeConfig, LLMConfig, RedactionConfig
from src.infrastructure.terminal_engine.pty_engine import PTYEngine


def _config(nl_active=True):
    return ForgeShellConfig(
        nl_mode=NLModeConfig(default_active=nl_active),
        redaction=RedactionConfig(),
        llm=LLMConfig(),
    )


class TestTerminalSessionIOIntegration:
    def test_pty_output_captured_via_handle(self) -> None:
        """_handle_pty_output escreve em stdout mockado."""
        session = TerminalSession(config=_config())
        buf = io.BytesIO()
        session._stdout = buf

        from src.infrastructure.terminal_engine.alternate_screen import AlternateScreenDetector
        session._detector = AlternateScreenDetector()

        session._handle_pty_output(b"hello from PTY\r\n")

        buf.seek(0)
        assert b"hello from PTY" in buf.read()

    def test_passthrough_routes_to_pty(self) -> None:
        """Em passthrough, input vai direto ao PTY sem interceptor."""
        session = TerminalSession(config=_config(), passthrough=True)
        from unittest.mock import MagicMock
        engine = MagicMock()
        session._engine = engine

        session._route_input(b"ls -la\n")
        engine.write.assert_called_once_with(b"ls -la\n")

    def test_nl_mode_with_real_engine_spawn(self) -> None:
        """TerminalSession em modo NL pode fazer spawn do PTY."""
        session = TerminalSession(config=_config(nl_active=True))
        # spawn direto do engine interno
        session._engine.spawn()
        assert session._engine.is_alive
        session._engine.close()
        time.sleep(0.1)
        assert session._engine.is_alive is False

    def test_pty_real_echo_via_engine(self) -> None:
        """Engine interno do TerminalSession pode executar comandos."""
        session = TerminalSession(config=_config())
        engine = session._engine
        engine.spawn()
        time.sleep(0.3)
        engine.read_available(timeout=0.2)  # drena prompt
        engine.write(b"echo INTEGRATION_TEST\n")
        output = b""
        for _ in range(8):
            output += engine.read_available(timeout=0.15)
            if b"INTEGRATION_TEST" in output:
                break
        engine.close()
        assert b"INTEGRATION_TEST" in output, f"output: {output!r}"

    def test_alternate_screen_blocks_nl_interception(self) -> None:
        """Quando alternate screen ativo, input vai direto ao PTY."""
        session = TerminalSession(config=_config(nl_active=True))
        from unittest.mock import MagicMock
        engine = MagicMock()
        interceptor = MagicMock()
        detector = MagicMock()
        detector.is_active = True

        session._engine = engine
        session._interceptor = interceptor
        session._detector = detector

        session._route_input(b"vim command\n")

        interceptor.intercept.assert_not_called()
        engine.write.assert_called_once_with(b"vim command\n")

    def test_session_mode_nl_by_default(self) -> None:
        session = TerminalSession(config=_config(nl_active=True))
        assert session.mode == SessionMode.NL

    def test_session_mode_passthrough(self) -> None:
        session = TerminalSession(config=_config(), passthrough=True)
        assert session.mode == SessionMode.PASSTHROUGH
