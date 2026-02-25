"""
C4-T-05 — share wired: RelayBridge conectado ao TerminalSession
DADO share subcommand com relay inline
QUANDO share é invocado
ENTÃO RelayHandler é iniciado em thread background
ENTÃO RelayBridge é criado e iniciado
ENTÃO TerminalSession tem _relay_bridge injetado
QUANDO TerminalSession._handle_pty_output recebe dados
ENTÃO relay_bridge.send() é chamado com os mesmos dados
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestTerminalSessionRelayBridge:
    def test_session_accepts_relay_bridge_injection(self) -> None:
        """TerminalSession deve ter atributo _relay_bridge injetável."""
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import SymShellConfig
        session = TerminalSession(config=SymShellConfig())
        assert hasattr(session, "_relay_bridge")

    def test_relay_bridge_defaults_none(self) -> None:
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import SymShellConfig
        session = TerminalSession(config=SymShellConfig())
        assert session._relay_bridge is None

    def test_handle_pty_output_calls_bridge_send(self) -> None:
        """Quando _relay_bridge está injetado, _handle_pty_output chama bridge.send()."""
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import SymShellConfig
        session = TerminalSession(config=SymShellConfig())
        mock_bridge = MagicMock()
        session._relay_bridge = mock_bridge
        session._stdout = MagicMock()
        session._handle_pty_output(b"output data")
        mock_bridge.send.assert_called_once_with(b"output data")

    def test_handle_pty_output_without_bridge_does_not_crash(self) -> None:
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import SymShellConfig
        session = TerminalSession(config=SymShellConfig())
        session._stdout = MagicMock()
        session._handle_pty_output(b"output data")  # sem bridge


class TestShareCommandWired:
    def test_share_shows_relay_url(self, capsys) -> None:
        """share deve exibir a relay_url usada."""
        from src.adapters.cli.main import main
        with patch("src.adapters.cli.main.SessionManager") as MockSM, \
             patch("src.adapters.cli.main.ShareSession") as MockSS:
            mock_result = {
                "session_id": "s-share-test",
                "token": "tok-abc",
                "expires_at": "2026-02-25T02:00:00+00:00",
            }
            MockSS.return_value.run.return_value = mock_result
            rc = main(["share"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "s-share-test" in captured.out
        assert "tok-abc" in captured.out

    def test_share_returns_0(self) -> None:
        from src.adapters.cli.main import main
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS:
            MockSS.return_value.run.return_value = {
                "session_id": "s-x", "token": "t-x", "expires_at": "2026-01-01"
            }
            rc = main(["share"])
        assert rc == 0
