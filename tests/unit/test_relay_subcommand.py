"""
relay standalone subcommand — sym_shell relay
DADO o CLI com subcomando relay
QUANDO invoco 'sym_shell relay'
ENTÃO RelayHandler é iniciado como serviço standalone (sem PTY)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRelaySubcommandParser:
    def test_relay_subcommand_exists(self) -> None:
        from src.adapters.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["relay"])
        assert args.command == "relay"

    def test_relay_default_host(self) -> None:
        from src.adapters.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["relay"])
        assert args.host == "0.0.0.0"

    def test_relay_default_port_is_none(self) -> None:
        """Sem --port, usa relay.port do config."""
        from src.adapters.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["relay"])
        assert args.port is None

    def test_relay_custom_port(self) -> None:
        from src.adapters.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["relay", "--port", "9999"])
        assert args.port == 9999

    def test_relay_custom_host(self) -> None:
        from src.adapters.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["relay", "--host", "127.0.0.1"])
        assert args.host == "127.0.0.1"


class TestRelaySubcommandWired:
    def test_relay_returns_0(self) -> None:
        """relay deve retornar exit code 0."""
        with patch("src.adapters.cli.main.RelayHandler") as MockRH, \
             patch("src.adapters.cli.main.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = None
            from src.adapters.cli.main import main
            rc = main(["relay"])
        assert rc == 0

    def test_relay_calls_asyncio_run(self) -> None:
        """relay deve chamar asyncio.run() com relay.start()."""
        with patch("src.adapters.cli.main.RelayHandler") as MockRH, \
             patch("src.adapters.cli.main.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = None
            from src.adapters.cli.main import main
            main(["relay"])
        mock_asyncio.run.assert_called_once()

    def test_relay_uses_config_port_by_default(self) -> None:
        """relay sem --port usa relay.port do config (8060)."""
        with patch("src.adapters.cli.main.RelayHandler") as MockRH, \
             patch("src.adapters.cli.main.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = None
            from src.adapters.cli.main import main
            main(["relay"])
        call_kwargs = str(MockRH.call_args)
        assert "8060" in call_kwargs

    def test_relay_uses_custom_port(self) -> None:
        """relay com --port usa a porta fornecida."""
        with patch("src.adapters.cli.main.RelayHandler") as MockRH, \
             patch("src.adapters.cli.main.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = None
            from src.adapters.cli.main import main
            main(["relay", "--port", "9999"])
        call_kwargs = str(MockRH.call_args)
        assert "9999" in call_kwargs

    def test_relay_prints_bind_info(self, capsys) -> None:
        """relay deve exibir endereço de escuta."""
        with patch("src.adapters.cli.main.RelayHandler"), \
             patch("src.adapters.cli.main.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = None
            from src.adapters.cli.main import main
            main(["relay"])
        captured = capsys.readouterr()
        assert "8060" in captured.out

    def test_relay_graceful_on_keyboard_interrupt(self) -> None:
        """relay deve retornar 0 mesmo quando Ctrl+C."""
        with patch("src.adapters.cli.main.RelayHandler"), \
             patch("src.adapters.cli.main.asyncio") as mock_asyncio:
            mock_asyncio.run.side_effect = KeyboardInterrupt
            from src.adapters.cli.main import main
            rc = main(["relay"])
        assert rc == 0


class TestShareNoLongerStartsRelayInline:
    """share não deve mais iniciar RelayHandler inline."""

    def _share_patches(self):
        return dict(
            RelayBridge=MagicMock(),
            TerminalSession=MagicMock(**{"return_value.run.return_value": 0}),
            NLInterceptor=MagicMock(),
            AuditLogger=MagicMock(),
            ForgeLLMAdapter=MagicMock(),
            NLModeEngine=MagicMock(),
            RiskEngine=MagicMock(),
        )

    def test_share_does_not_instantiate_relay_handler(self) -> None:
        """share não deve criar RelayHandler."""
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS, \
             patch("src.adapters.cli.main.RelayHandler") as MockRH, \
             patch.multiple("src.adapters.cli.main", **self._share_patches()):
            MockSS.return_value.run.return_value = {
                "machine_code": "497-051-961", "password": "321321"
            }
            from src.adapters.cli.main import main
            main(["share"])
        MockRH.assert_not_called()

    def test_share_still_uses_relay_bridge(self) -> None:
        """share deve continuar usando RelayBridge para conectar ao relay externo."""
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS, \
             patch("src.adapters.cli.main.RelayHandler"), \
             patch("src.adapters.cli.main.RelayBridge") as MockRB, \
             patch("src.adapters.cli.main.TerminalSession") as MockTS, \
             patch("src.adapters.cli.main.NLInterceptor"), \
             patch("src.adapters.cli.main.AuditLogger"), \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"):
            MockSS.return_value.run.return_value = {
                "machine_code": "497-051-961", "password": "321321"
            }
            MockTS.return_value.run.return_value = 0
            from src.adapters.cli.main import main
            main(["share"])
        MockRB.assert_called_once()
        MockRB.return_value.start.assert_called_once()
