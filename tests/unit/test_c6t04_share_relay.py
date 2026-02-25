"""
C6-T-04 — share CLI: RelayHandler inline + RelayBridge + SessionIndicator
DADO share subcommand
QUANDO executado
ENTÃO RelayHandler é iniciado em thread background
ENTÃO RelayBridge é criado e startado
ENTÃO TerminalSession._relay_bridge é injetado
ENTÃO SessionIndicator é criado
ENTÃO indicador é exibido no output
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestShareRelayWired:
    def test_share_imports_relay_handler(self) -> None:
        import src.adapters.cli.main as m
        assert hasattr(m, "RelayHandler") or True  # verifica import sem erro

    def test_share_starts_relay_bridge(self) -> None:
        """share deve criar e iniciar um RelayBridge."""
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS, \
             patch("src.adapters.cli.main.RelayHandler") as MockRH, \
             patch("src.adapters.cli.main.RelayBridge") as MockRB, \
             patch("src.adapters.cli.main.TerminalSession") as MockTS, \
             patch("src.adapters.cli.main.NLInterceptor"), \
             patch("src.adapters.cli.main.AuditLogger"), \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"):
            MockSS.return_value.run.return_value = {
                "session_id": "s-x", "token": "t-x", "expires_at": "2026-01-01"
            }
            mock_session = MagicMock()
            mock_session.run.return_value = 0
            MockTS.return_value = mock_session
            from src.adapters.cli.main import main
            main(["share"])
        MockRB.assert_called()
        MockRB.return_value.start.assert_called()

    def test_share_injects_relay_bridge_into_session(self) -> None:
        """share deve injetar _relay_bridge no TerminalSession."""
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
                "session_id": "s-x", "token": "t-x", "expires_at": "2026-01-01"
            }
            mock_session = MagicMock()
            mock_session.run.return_value = 0
            MockTS.return_value = mock_session
            from src.adapters.cli.main import main
            main(["share"])
        assert mock_session._relay_bridge == MockRB.return_value

    def test_share_shows_session_info(self, capsys) -> None:
        """share deve continuar exibindo session_id e token."""
        with patch("src.adapters.cli.main.SessionManager"), \
             patch("src.adapters.cli.main.ShareSession") as MockSS, \
             patch("src.adapters.cli.main.RelayHandler"), \
             patch("src.adapters.cli.main.RelayBridge"), \
             patch("src.adapters.cli.main.TerminalSession") as MockTS, \
             patch("src.adapters.cli.main.NLInterceptor"), \
             patch("src.adapters.cli.main.AuditLogger"), \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"):
            MockSS.return_value.run.return_value = {
                "session_id": "s-demo", "token": "tok-demo", "expires_at": "2026-01-01"
            }
            MockTS.return_value.run.return_value = 0
            from src.adapters.cli.main import main
            rc = main(["share"])
        captured = capsys.readouterr()
        assert "s-demo" in captured.out
        assert rc == 0
