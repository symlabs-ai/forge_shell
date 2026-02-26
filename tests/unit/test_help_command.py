"""
:help command — testes unitários

DADO usuário digita :help no terminal
QUANDO NLModeEngine processa o input
ENTÃO retorna NLResult(is_help=True)
E NLInterceptor mapeia para InterceptAction.HELP
E TerminalSession exibe o texto de ajuda sem ir ao LLM
"""
import pytest
from unittest.mock import MagicMock, patch

from src.application.usecases.nl_mode_engine import NLModeEngine, NLResult
from src.application.usecases.nl_interceptor import NLInterceptor, InterceptAction
from src.infrastructure.intelligence.risk_engine import RiskEngine


class TestNLModeEngineHelp:
    def _make_engine(self) -> NLModeEngine:
        adapter = MagicMock()
        return NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())

    def test_help_returns_is_help_true(self) -> None:
        engine = self._make_engine()
        result = engine.process_input(":help", context={})
        assert result is not None
        assert result.is_help is True

    def test_help_case_insensitive(self) -> None:
        engine = self._make_engine()
        for variant in (":HELP", ":Help", ":hElP"):
            result = engine.process_input(variant, context={})
            assert result is not None and result.is_help is True, f"failed for {variant!r}"

    def test_help_does_not_call_llm(self) -> None:
        adapter = MagicMock()
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        engine.process_input(":help", context={})
        adapter.request.assert_not_called()
        adapter.explain.assert_not_called()

    def test_help_works_in_bash_mode(self) -> None:
        engine = self._make_engine()
        engine.toggle()  # → BASH_ACTIVE
        result = engine.process_input(":help", context={})
        assert result is not None
        assert result.is_help is True

    def test_help_requires_exact_command(self) -> None:
        """':help algo' não deve ativar :help (cai no NL Mode normal)."""
        engine = self._make_engine()
        # adapter.request retorna None → NLResult vazio, is_help=False
        engine._adapter.request.return_value = None
        result = engine.process_input(":help algo", context={})
        assert result is None or not result.is_help


class TestNLInterceptorHelp:
    def _make_interceptor(self) -> NLInterceptor:
        adapter = MagicMock()
        adapter.request.return_value = None
        engine = NLModeEngine(llm_adapter=adapter, risk_engine=RiskEngine())
        return NLInterceptor(nl_engine=engine)

    def test_intercept_help_returns_help_action(self) -> None:
        interceptor = self._make_interceptor()
        result = interceptor.intercept(b":help")
        assert result.action == InterceptAction.HELP

    def test_help_action_exists_in_enum(self) -> None:
        assert InterceptAction.HELP == "help"


class TestTerminalSessionHelpHandler:
    def _make_session(self):
        from src.infrastructure.config.loader import ForgeShellConfig
        from src.application.usecases.terminal_session import TerminalSession
        config = ForgeShellConfig()
        session = TerminalSession(config=config)
        return session

    def test_help_writes_to_stdout(self) -> None:
        import io
        from src.application.usecases.nl_interceptor import InterceptResult
        session = self._make_session()
        buf = io.BytesIO()
        session._stdout = buf
        result = InterceptResult(action=InterceptAction.HELP)
        session._handle_intercept_result(result)
        output = buf.getvalue()
        assert b"forge_shell" in output
        assert b":explain" in output
        assert b":help" in output
        assert b"!" in output

    def test_help_output_contains_nl_mode_hint(self) -> None:
        import io
        from src.application.usecases.nl_interceptor import InterceptResult
        session = self._make_session()
        buf = io.BytesIO()
        session._stdout = buf
        result = InterceptResult(action=InterceptAction.HELP)
        session._handle_intercept_result(result)
        output = buf.getvalue().decode("utf-8", errors="replace")
        assert "NL Mode" in output or "portugues" in output.lower() or "português" in output
