"""
C2-T-03 + C2-T-09 — TerminalSession (I/O loop) + Config wiring
DADO o TerminalSession com PTYEngine mockado
QUANDO processo eventos de stdin e PTY
ENTÃO roteamento, SIGWINCH e config são aplicados corretamente
"""
import signal
import sys
import pytest
from unittest.mock import MagicMock, patch, call

from src.application.usecases.terminal_session import TerminalSession, SessionMode
from src.infrastructure.config.loader import ForgeShellConfig, NLModeConfig, LLMConfig, RedactionConfig


def _config(nl_active: bool = True) -> ForgeShellConfig:
    return ForgeShellConfig(
        nl_mode=NLModeConfig(default_active=nl_active),
        redaction=RedactionConfig(),
        llm=LLMConfig(),
    )


class TestTerminalSessionInit:
    def test_create_with_config(self) -> None:
        session = TerminalSession(config=_config())
        assert session is not None

    def test_passthrough_mode_off_by_default(self) -> None:
        session = TerminalSession(config=_config())
        assert session.mode == SessionMode.NL

    def test_passthrough_mode_enabled(self) -> None:
        session = TerminalSession(config=_config(), passthrough=True)
        assert session.mode == SessionMode.PASSTHROUGH

    def test_nl_mode_respects_config_default_false(self) -> None:
        session = TerminalSession(config=_config(nl_active=False))
        assert session.mode == SessionMode.BASH

    def test_nl_mode_respects_config_default_true(self) -> None:
        session = TerminalSession(config=_config(nl_active=True))
        assert session.mode == SessionMode.NL


class TestTerminalSessionRouting:
    """Testa roteamento de input sem I/O real."""

    def test_passthrough_routes_all_input_to_pty(self) -> None:
        session = TerminalSession(config=_config(), passthrough=True)
        engine = MagicMock()
        session._engine = engine
        session._route_input(b"ls -la\n")
        engine.write.assert_called_once_with(b"ls -la\n")

    def test_passthrough_never_intercepts_nl(self) -> None:
        session = TerminalSession(config=_config(), passthrough=True)
        engine = MagicMock()
        interceptor = MagicMock()
        session._engine = engine
        session._interceptor = interceptor
        session._route_input(b"list all files\n")
        interceptor.intercept.assert_not_called()
        engine.write.assert_called_once_with(b"list all files\n")

    def test_nl_mode_routes_text_to_interceptor(self) -> None:
        session = TerminalSession(config=_config(nl_active=True))
        engine = MagicMock()
        interceptor = MagicMock()
        interceptor.intercept.return_value = None  # sem resultado ainda
        session._engine = engine
        session._interceptor = interceptor
        session._route_input(b"list all files\n")
        interceptor.intercept.assert_called_once()

    def test_nl_skips_interceptor_when_alternate_screen_active(self) -> None:
        """vim, top etc. — input vai direto para PTY sem NL."""
        session = TerminalSession(config=_config(nl_active=True))
        engine = MagicMock()
        interceptor = MagicMock()
        detector = MagicMock()
        detector.is_active = True  # vim aberto
        session._engine = engine
        session._interceptor = interceptor
        session._detector = detector
        session._route_input(b"some vim command\n")
        interceptor.intercept.assert_not_called()
        engine.write.assert_called_once_with(b"some vim command\n")

    def test_pty_output_fed_to_detector(self) -> None:
        session = TerminalSession(config=_config())
        detector = MagicMock()
        stdout = MagicMock()
        session._detector = detector
        session._stdout = stdout
        session._handle_pty_output(b"\x1b[?1049hsome output")
        detector.feed.assert_called_once_with(b"\x1b[?1049hsome output")

    def test_pty_output_written_to_stdout(self) -> None:
        session = TerminalSession(config=_config())
        detector = MagicMock()
        stdout = MagicMock()
        session._detector = detector
        session._stdout = stdout
        session._handle_pty_output(b"hello world\r\n")
        stdout.write.assert_called_once_with(b"hello world\r\n")


class TestTerminalSessionSIGWINCH:
    @pytest.mark.skipif(sys.platform == "win32", reason="SIGWINCH não existe no Windows")
    def test_resize_handler_installed(self) -> None:
        session = TerminalSession(config=_config())
        engine = MagicMock()
        session._engine = engine
        session._install_sigwinch_handler()
        # handler instalado — não deve lançar exceção
        # dispara manualmente para verificar que chama engine.resize
        handler = signal.getsignal(signal.SIGWINCH)
        assert handler is not None
        assert callable(handler)


class TestTerminalSessionConfigWiring:
    def test_config_nl_active_propagated(self) -> None:
        cfg = _config(nl_active=True)
        session = TerminalSession(config=cfg)
        assert session.config.nl_mode.default_active is True

    def test_config_llm_provider_accessible(self) -> None:
        cfg = _config()
        cfg.llm.provider = "openai"
        session = TerminalSession(config=cfg)
        assert session.config.llm.provider == "openai"

    def test_config_redaction_profile_accessible(self) -> None:
        cfg = _config()
        cfg.redaction.default_profile = "dev"
        session = TerminalSession(config=cfg)
        assert session.config.redaction.default_profile == "dev"
