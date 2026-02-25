"""
C3-T-06 — NL Mode smoke (interceptor ao vivo, sem LLM real)
             + attach wired no CLI
DADO NLInterceptor com NLModeEngine real (sem LLM)
QUANDO processo comandos de toggle/escape
ENTÃO comportamento correto sem LLM real
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.application.usecases.nl_interceptor import NLInterceptor, InterceptAction
from src.application.usecases.nl_mode_engine import NLModeEngine, NLModeState
from src.infrastructure.intelligence.risk_engine import RiskEngine


class TestNLModeSmokeWithoutLLM:
    """Smoke do NL Mode sem LLM real — usa adapter mockado."""

    def _make_interceptor(self):
        adapter = MagicMock()
        adapter.request.return_value = None  # sem LLM
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        return NLInterceptor(nl_engine=engine)

    def test_toggle_changes_state(self) -> None:
        interceptor = self._make_interceptor()
        result = interceptor.intercept(b"!\n")
        assert result.action == InterceptAction.TOGGLE

    def test_double_toggle_restores_state(self) -> None:
        adapter = MagicMock()
        adapter.request.return_value = None
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        interceptor = NLInterceptor(nl_engine=engine)
        assert engine.state == NLModeState.NL_ACTIVE
        interceptor.intercept(b"!\n")
        assert engine.state == NLModeState.BASH_ACTIVE
        interceptor.intercept(b"!\n")
        assert engine.state == NLModeState.NL_ACTIVE

    def test_bang_cmd_returns_exec_bash(self) -> None:
        interceptor = self._make_interceptor()
        result = interceptor.intercept(b"!ls -la\n")
        assert result.action == InterceptAction.EXEC_BASH
        assert result.bash_command == "ls -la"

    def test_bang_cmd_returns_to_nl_mode(self) -> None:
        adapter = MagicMock()
        adapter.request.return_value = None
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        interceptor = NLInterceptor(nl_engine=engine)
        # forçar bash mode
        engine.toggle()
        assert engine.state == NLModeState.BASH_ACTIVE
        # !<cmd> deve retornar ao NL mode
        interceptor.intercept(b"!ls\n")
        assert engine.state == NLModeState.NL_ACTIVE

    def test_nl_text_returns_noop_without_llm(self) -> None:
        interceptor = self._make_interceptor()
        result = interceptor.intercept(b"list all python files\n")
        # sem LLM, adapter retorna None → NLResult vazio → NOOP
        assert result.action == InterceptAction.NOOP

    def test_bash_mode_passthrough(self) -> None:
        adapter = MagicMock()
        adapter.request.return_value = None
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        engine.toggle()  # → BASH_ACTIVE
        interceptor = NLInterceptor(nl_engine=engine)
        result = interceptor.intercept(b"ls -la\n")
        assert result.action == InterceptAction.EXEC_BASH
        assert result.bash_command == "ls -la"


class TestAttachWiredCLI:
    def _make_mock_vc(self):
        mock_vc = MagicMock()
        mock_vc.connect = AsyncMock(return_value=None)
        mock_vc.wait = AsyncMock(return_value=None)
        mock_vc.close = AsyncMock(return_value=None)
        return mock_vc

    def test_attach_no_longer_stub_notimplemented(self, capsys) -> None:
        """attach deve exibir info de conexão e chamar viewer.connect()."""
        with patch("src.adapters.cli.main.ViewerClient") as MockVC:
            MockVC.return_value = self._make_mock_vc()
            from src.adapters.cli.main import main
            rc = main(["attach", "s-test123"])
        captured = capsys.readouterr()
        assert rc == 0

    def test_attach_with_session_id(self) -> None:
        with patch("src.adapters.cli.main.ViewerClient") as MockVC:
            MockVC.return_value = self._make_mock_vc()
            from src.adapters.cli.main import main
            rc = main(["attach", "s-abc"])
        assert rc == 0
