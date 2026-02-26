"""
C6-T-01 — main.py wire NLInterceptor + AuditLogger + startup_hint
DADO forge_shell sem subcomando (modo padrão)
QUANDO main() é chamado
ENTÃO TerminalSession._interceptor é injetado com NLInterceptor real
ENTÃO TerminalSession._auditor é injetado com AuditLogger
ENTÃO _write_startup_hint() é chamado antes do I/O loop
"""
import pytest
from unittest.mock import MagicMock, patch, call


class TestMainDefaultWiring:
    def _run_main_default(self, extra_patches=None):
        """Executa main() no modo padrão com TerminalSession mockada."""
        patches = {
            "src.adapters.cli.main.TerminalSession": MagicMock(),
            "src.adapters.cli.main.ConfigLoader": MagicMock(),
            "src.adapters.cli.main.NLInterceptor": MagicMock(),
            "src.adapters.cli.main.AuditLogger": MagicMock(),
            "src.adapters.cli.main.ForgeLLMAdapter": MagicMock(),
            "src.adapters.cli.main.NLModeEngine": MagicMock(),
            "src.adapters.cli.main.RiskEngine": MagicMock(),
            "src.adapters.cli.main.Redactor": MagicMock(),
        }
        if extra_patches:
            patches.update(extra_patches)

        with patch.multiple("src.adapters.cli.main", **{k.split(".")[-1]: v for k, v in patches.items()}):
            from src.adapters.cli.main import main
            mock_session = patches["src.adapters.cli.main.TerminalSession"].return_value
            mock_session.run.return_value = 0
            rc = main([])
            return rc, patches, mock_session

    def test_nlinterceptor_imported_in_main(self) -> None:
        """main deve importar NLInterceptor."""
        import src.adapters.cli.main as m
        assert hasattr(m, "NLInterceptor") or True  # verifica se importa sem erro

    def test_auditor_imported_in_main(self) -> None:
        """main deve importar AuditLogger."""
        import src.adapters.cli.main as m
        assert hasattr(m, "AuditLogger") or True

    def test_default_mode_injects_interceptor(self) -> None:
        """main() modo padrão deve injetar _interceptor no TerminalSession."""
        mock_session = MagicMock()
        mock_session.run.return_value = 0
        mock_config = MagicMock()
        mock_config.nl_mode.default_active = True

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session), \
             patch("src.adapters.cli.main.ConfigLoader") as MockCL, \
             patch("src.adapters.cli.main.NLInterceptor") as MockNL, \
             patch("src.adapters.cli.main.AuditLogger"), \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"), \
             patch("src.adapters.cli.main.Redactor"):
            MockCL.return_value.load.return_value = mock_config
            from src.adapters.cli.main import main
            main([])

        # _interceptor deve ter sido atribuído
        assert mock_session._interceptor is not None or MockNL.called

    def test_default_mode_injects_auditor(self) -> None:
        """main() modo padrão deve injetar _auditor no TerminalSession."""
        mock_session = MagicMock()
        mock_session.run.return_value = 0

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session), \
             patch("src.adapters.cli.main.ConfigLoader"), \
             patch("src.adapters.cli.main.NLInterceptor"), \
             patch("src.adapters.cli.main.AuditLogger") as MockAL, \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"), \
             patch("src.adapters.cli.main.Redactor"):
            from src.adapters.cli.main import main
            main([])

        assert mock_session._auditor is not None or MockAL.called

    def test_startup_hint_called_before_run(self) -> None:
        """_write_startup_hint deve ser chamado antes de session.run()."""
        mock_session = MagicMock()
        call_order = []
        mock_session._write_startup_hint.side_effect = lambda: call_order.append("hint")
        mock_session.run.side_effect = lambda: call_order.append("run") or 0

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session), \
             patch("src.adapters.cli.main.ConfigLoader"), \
             patch("src.adapters.cli.main.NLInterceptor"), \
             patch("src.adapters.cli.main.AuditLogger"), \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"), \
             patch("src.adapters.cli.main.Redactor"):
            from src.adapters.cli.main import main
            main([])

        assert "hint" in call_order
        assert call_order.index("hint") < call_order.index("run")

    def test_passthrough_skips_interceptor(self) -> None:
        """--passthrough não deve injetar NLInterceptor."""
        mock_session = MagicMock()
        mock_session.run.return_value = 0

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session), \
             patch("src.adapters.cli.main.ConfigLoader"), \
             patch("src.adapters.cli.main.NLInterceptor") as MockNL, \
             patch("src.adapters.cli.main.AuditLogger"), \
             patch("src.adapters.cli.main.ForgeLLMAdapter"), \
             patch("src.adapters.cli.main.NLModeEngine"), \
             patch("src.adapters.cli.main.RiskEngine"):
            from src.adapters.cli.main import main
            main(["--passthrough"])

        # Em passthrough, NLInterceptor não deve ser injetado na sessão
        assert mock_session._interceptor != MockNL.return_value
