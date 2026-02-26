"""
C4-T-02 — attach CLI wired: asyncio.run() viewer loop real
DADO attach subcommand
QUANDO executado com session_id
ENTÃO ViewerClient.connect() é chamado com on_output e relay_url do config
QUANDO Ctrl+C (KeyboardInterrupt)
ENTÃO ViewerClient.close() é chamado e retorna 0 graciosamente
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call


class TestAttachLive:
    def _make_mock_vc(self):
        """ViewerClient mock com connect/wait/close async."""
        mock_vc = MagicMock()
        mock_vc.connect = AsyncMock(return_value=None)
        mock_vc.wait = AsyncMock(return_value=None)   # retorna imediatamente (relay fechou)
        mock_vc.close = AsyncMock(return_value=None)
        return mock_vc

    def test_attach_calls_viewer_connect(self) -> None:
        """attach deve chamar viewer.connect() — não apenas instanciar ViewerClient."""
        mock_vc = self._make_mock_vc()
        with patch("src.adapters.cli.main.ViewerClient", return_value=mock_vc) as MockVC:
            from src.adapters.cli.main import main
            rc = main(["attach", "497-051-961", "123456"])
        assert mock_vc.connect.called, "viewer.connect() deve ser chamado"

    def test_attach_calls_viewer_close_on_exit(self) -> None:
        """attach deve chamar viewer.close() ao encerrar."""
        mock_vc = self._make_mock_vc()
        with patch("src.adapters.cli.main.ViewerClient", return_value=mock_vc):
            from src.adapters.cli.main import main
            main(["attach", "497-051-961", "123456"])
        assert mock_vc.close.called, "viewer.close() deve ser chamado"

    def test_attach_uses_relay_url_from_config(self, tmp_path) -> None:
        """relay_url deve vir do config, não hardcoded."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("relay:\n  url: ws://custom-relay:9999\n")
        mock_vc = self._make_mock_vc()
        with patch("src.adapters.cli.main.ViewerClient", return_value=mock_vc) as MockVC, \
             patch("src.adapters.cli.main.ConfigLoader") as MockCL:
            from src.infrastructure.config.loader import SymShellConfig, RelayConfig, NLModeConfig, LLMConfig, RedactionConfig
            mock_config = SymShellConfig(
                relay=RelayConfig(url="ws://custom-relay:9999", port=9999),
            )
            MockCL.return_value.load.return_value = mock_config
            from src.adapters.cli.main import main
            main(["attach", "497-051-961", "123456"])
        # ViewerClient deve ter sido instanciado com a URL do config
        call_kwargs = MockVC.call_args
        assert "ws://custom-relay:9999" in str(call_kwargs)

    def test_attach_returns_0(self) -> None:
        """attach deve retornar exit code 0."""
        mock_vc = self._make_mock_vc()
        with patch("src.adapters.cli.main.ViewerClient", return_value=mock_vc):
            from src.adapters.cli.main import main
            rc = main(["attach", "497-051-961", "123456"])
        assert rc == 0

    def test_attach_graceful_on_keyboard_interrupt(self) -> None:
        """attach deve fechar viewer e retornar 0 mesmo quando Ctrl+C no wait."""
        mock_vc = self._make_mock_vc()
        mock_vc.wait = AsyncMock(side_effect=KeyboardInterrupt)
        with patch("src.adapters.cli.main.ViewerClient", return_value=mock_vc):
            from src.adapters.cli.main import main
            rc = main(["attach", "497-051-961", "123456"])
        assert rc == 0
        assert mock_vc.close.called
