"""
T-24 a T-26 — :explain, :risk e contexto LLM configurável
DADO usecases de explain/risk e builder de contexto LLM
QUANDO invoco com um comando
ENTÃO recebo análise correta sem executar nada
"""
import pytest
from unittest.mock import MagicMock, patch

from src.application.usecases.explain_command import ExplainCommand
from src.application.usecases.risk_command import RiskCommand
from src.application.usecases.llm_context_builder import LLMContextBuilder
from src.infrastructure.intelligence.risk_engine import RiskEngine, RiskLevel
from src.infrastructure.intelligence.nl_response import NLResponse


class TestExplainCommand:
    def _make_adapter(self, explanation: str = "Lista arquivos") -> MagicMock:
        adapter = MagicMock()
        response = NLResponse(
            commands=["ls -la"],
            explanation=explanation,
            risk_level=RiskLevel.LOW,
            assumptions=[],
            required_user_confirmation=False,
        )
        adapter.explain.return_value = response
        return adapter

    def test_explain_returns_nlresponse(self) -> None:
        adapter = self._make_adapter()
        uc = ExplainCommand(adapter)
        result = uc.run("ls -la", context={})
        assert result is not None
        assert result.explanation == "Lista arquivos"

    def test_explain_calls_adapter_explain(self) -> None:
        adapter = self._make_adapter()
        uc = ExplainCommand(adapter)
        uc.run("ls -la", context={})
        adapter.explain.assert_called_once_with(command="ls -la", context={})

    def test_explain_returns_none_on_adapter_failure(self) -> None:
        adapter = MagicMock()
        adapter.explain.return_value = None
        uc = ExplainCommand(adapter)
        result = uc.run("ls -la", context={})
        assert result is None

    def test_explain_does_not_execute_command(self) -> None:
        """explain nunca passa bash_command — apenas analisa."""
        adapter = self._make_adapter()
        uc = ExplainCommand(adapter)
        result = uc.run("rm -rf /", context={})
        # NLResponse retornado — mas nada foi executado
        assert result is not None


class TestRiskCommand:
    def test_risk_low(self) -> None:
        engine = RiskEngine()
        uc = RiskCommand(engine)
        level = uc.run("ls -la")
        assert level == RiskLevel.LOW

    def test_risk_medium(self) -> None:
        engine = RiskEngine()
        uc = RiskCommand(engine)
        level = uc.run("sudo apt update")
        assert level == RiskLevel.MEDIUM

    def test_risk_high(self) -> None:
        engine = RiskEngine()
        uc = RiskCommand(engine)
        level = uc.run("rm -rf /")
        assert level == RiskLevel.HIGH

    def test_risk_returns_string_value(self) -> None:
        engine = RiskEngine()
        uc = RiskCommand(engine)
        level = uc.run("echo hello")
        assert isinstance(level.value, str)

    def test_risk_does_not_execute(self) -> None:
        """Classificar risco nunca executa o comando."""
        engine = RiskEngine()
        uc = RiskCommand(engine)
        # não lança exceção nem efeito colateral
        level = uc.run("mkfs.ext4 /dev/sda")
        assert level == RiskLevel.HIGH


class TestLLMContextBuilder:
    def test_build_includes_cwd(self) -> None:
        builder = LLMContextBuilder()
        ctx = builder.build(cwd="/home/user", last_lines=[], last_cmd="")
        assert ctx["cwd"] == "/home/user"

    def test_build_includes_last_cmd(self) -> None:
        builder = LLMContextBuilder()
        ctx = builder.build(cwd="/tmp", last_lines=[], last_cmd="git status")
        assert ctx["last_cmd"] == "git status"

    def test_build_includes_last_lines(self) -> None:
        builder = LLMContextBuilder()
        lines = ["output line 1", "output line 2"]
        ctx = builder.build(cwd="/tmp", last_lines=lines, last_cmd="")
        assert ctx["last_output"] == lines

    def test_build_truncates_lines_to_max(self) -> None:
        builder = LLMContextBuilder(max_lines=3)
        lines = ["a", "b", "c", "d", "e"]
        ctx = builder.build(cwd="/tmp", last_lines=lines, last_cmd="")
        assert len(ctx["last_output"]) == 3
        assert ctx["last_output"] == ["c", "d", "e"]

    def test_build_env_whitelist(self) -> None:
        import os
        os.environ["EDITOR"] = "vim"
        builder = LLMContextBuilder(env_whitelist=["EDITOR"])
        ctx = builder.build(cwd="/tmp", last_lines=[], last_cmd="", env={"EDITOR": "vim", "SECRET": "x"})
        assert ctx["env"].get("EDITOR") == "vim"
        assert "SECRET" not in ctx["env"]

    def test_build_empty_env_whitelist(self) -> None:
        builder = LLMContextBuilder(env_whitelist=[])
        ctx = builder.build(cwd="/tmp", last_lines=[], last_cmd="", env={"HOME": "/home/user"})
        assert ctx.get("env", {}) == {}

    def test_build_default_max_lines(self) -> None:
        builder = LLMContextBuilder()
        # padrão deve ser >= 10
        assert builder.max_lines >= 10
