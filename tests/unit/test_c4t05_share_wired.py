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
        from src.infrastructure.config.loader import ForgeShellConfig
        session = TerminalSession(config=ForgeShellConfig())
        assert hasattr(session, "_relay_bridge")

    def test_relay_bridge_defaults_none(self) -> None:
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import ForgeShellConfig
        session = TerminalSession(config=ForgeShellConfig())
        assert session._relay_bridge is None

    def test_handle_pty_output_calls_bridge_send(self) -> None:
        """Quando _relay_bridge está injetado, _handle_pty_output chama bridge.send()."""
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import ForgeShellConfig
        session = TerminalSession(config=ForgeShellConfig())
        mock_bridge = MagicMock()
        session._relay_bridge = mock_bridge
        session._stdout = MagicMock()
        session._handle_pty_output(b"output data")
        mock_bridge.send.assert_called_once_with(b"output data")

    def test_handle_pty_output_without_bridge_does_not_crash(self) -> None:
        from src.application.usecases.terminal_session import TerminalSession
        from src.infrastructure.config.loader import ForgeShellConfig
        session = TerminalSession(config=ForgeShellConfig())
        session._stdout = MagicMock()
        session._handle_pty_output(b"output data")  # sem bridge


def _share_infra_patches():
    return dict(
        RelayBridge=MagicMock(),
        TerminalSession=MagicMock(**{"return_value.run.return_value": 0}),
        NLInterceptor=MagicMock(),
        AuditLogger=MagicMock(),
        ForgeLLMAdapter=MagicMock(),
        NLModeEngine=MagicMock(),
        RiskEngine=MagicMock(),
    )


class TestShareCommandWired:
    def test_share_shows_machine_code_and_password(self, capsys) -> None:
        """share deve exibir o machine_code e a password."""
        from src.adapters.cli.main import main
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS, \
             patch.multiple("src.adapters.cli.main", **_share_infra_patches()):
            MockSS.return_value.run.return_value = {
                "machine_code": "497-051-961",
                "password": "321321",
            }
            rc = main(["share"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "497-051-961" in captured.out
        assert "321321" in captured.out

    def test_share_returns_0(self) -> None:
        from src.adapters.cli.main import main
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS, \
             patch.multiple("src.adapters.cli.main", **_share_infra_patches()):
            MockSS.return_value.run.return_value = {
                "machine_code": "111-222-333", "password": "000000"
            }
            rc = main(["share"])
        assert rc == 0
