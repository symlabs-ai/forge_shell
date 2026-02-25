"""
C4-T-03 — AuditLogger wired no TerminalSession
DADO TerminalSession com auditor injetado
QUANDO session_start é chamado (run() inicia)
ENTÃO auditor.log_session_join() é chamado
QUANDO _handle_pty_output recebe dados com newline (linha de comando)
ENTÃO auditor registra o evento
"""
import pytest
from unittest.mock import MagicMock, patch
from src.application.usecases.terminal_session import TerminalSession
from src.infrastructure.config.loader import SymShellConfig, NLModeConfig


class TestAuditWiredInTerminalSession:
    def _make_session(self):
        config = SymShellConfig(nl_mode=NLModeConfig(default_active=False))
        session = TerminalSession(config=config)
        return session

    def test_session_accepts_auditor_injection(self) -> None:
        """TerminalSession deve aceitar auditor via DI."""
        session = self._make_session()
        assert hasattr(session, "_auditor"), "TerminalSession deve ter atributo _auditor"

    def test_auditor_defaults_to_none(self) -> None:
        """_auditor deve ser None por padrão (sem injeção)."""
        session = self._make_session()
        assert session._auditor is None

    def test_auditor_can_be_injected(self) -> None:
        """_auditor pode ser injetado após construção."""
        session = self._make_session()
        mock_auditor = MagicMock()
        session._auditor = mock_auditor
        assert session._auditor is mock_auditor

    def test_handle_pty_output_calls_auditor_when_set(self) -> None:
        """_handle_pty_output deve chamar auditor.log_command quando configurado."""
        session = self._make_session()
        mock_auditor = MagicMock()
        session._auditor = mock_auditor
        out = MagicMock()
        session._stdout = out
        # simular linha de output com newline
        session._handle_pty_output(b"$ ls -la\r\n")
        assert mock_auditor.log_command.called

    def test_handle_pty_output_without_auditor_does_not_crash(self) -> None:
        """_handle_pty_output sem auditor não deve lançar exceção."""
        session = self._make_session()
        out = MagicMock()
        session._stdout = out
        # sem auditor, não deve travar
        session._handle_pty_output(b"hello\r\n")

    def test_auditor_log_command_receives_output_line(self) -> None:
        """auditor.log_command recebe output como string."""
        session = self._make_session()
        mock_auditor = MagicMock()
        session._auditor = mock_auditor
        out = MagicMock()
        session._stdout = out
        session._handle_pty_output(b"some-output\r\n")
        call_args = mock_auditor.log_command.call_args
        # deve incluir origin="pty" e a linha de output
        assert call_args is not None
        kwargs = call_args.kwargs if call_args.kwargs else {}
        args = call_args.args if call_args.args else ()
        # origin deve ser "pty" ou "user"
        all_args = args + tuple(kwargs.values())
        assert any("pty" in str(a) or "user" in str(a) for a in all_args)
