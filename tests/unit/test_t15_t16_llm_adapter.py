"""
T-15/T-16 — ForgeLLM adapter + schema de resposta
DADO o adapter ForgeLLM
QUANDO faço uma requisição NL
ENTÃO recebo NLResponse validada ou um fallback limpo
"""
import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.intelligence.forge_llm_adapter import ForgeLLMAdapter
from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel


class TestNLResponse:
    def test_valid_response(self) -> None:
        resp = NLResponse(
            commands=["ps aux --sort=-%mem | head -6"],
            explanation="Lista processos ordenados por memória.",
            risk_level=RiskLevel.LOW,
            assumptions=[],
            required_user_confirmation=True,
        )
        assert resp.commands == ["ps aux --sort=-%mem | head -6"]
        assert resp.risk_level == RiskLevel.LOW
        assert resp.required_user_confirmation is True

    def test_empty_commands_raises(self) -> None:
        with pytest.raises(ValueError, match="commands"):
            NLResponse(
                commands=[],
                explanation="x",
                risk_level=RiskLevel.LOW,
                assumptions=[],
                required_user_confirmation=False,
            )

    def test_empty_explanation_raises(self) -> None:
        with pytest.raises(ValueError, match="explanation"):
            NLResponse(
                commands=["ls"],
                explanation="",
                risk_level=RiskLevel.LOW,
                assumptions=[],
                required_user_confirmation=False,
            )

    def test_risk_levels(self) -> None:
        for level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH):
            resp = NLResponse(
                commands=["ls"],
                explanation="ok",
                risk_level=level,
                assumptions=[],
                required_user_confirmation=True,
            )
            assert resp.risk_level == level


class TestForgeLLMAdapter:
    def _make_adapter(self, mock_agent: MagicMock) -> ForgeLLMAdapter:
        adapter = ForgeLLMAdapter(api_key="sk-test", provider="ollama", model="llama3")
        adapter._agent = mock_agent  # injetar mock diretamente (lazy init)
        return adapter

    def test_returns_nl_response_on_valid_json(self) -> None:
        mock_agent = MagicMock()
        mock_agent.chat.return_value = MagicMock(
            content='{"commands": ["ls -la"], "explanation": "Lista arquivos.", "risk_level": "low", "assumptions": [], "required_user_confirmation": true}'
        )
        adapter = self._make_adapter(mock_agent)
        resp = adapter.request(text="listar arquivos", context={})
        assert isinstance(resp, NLResponse)
        assert resp.commands == ["ls -la"]
        assert resp.risk_level == RiskLevel.LOW

    def test_returns_none_on_invalid_json(self) -> None:
        mock_agent = MagicMock()
        mock_agent.chat.return_value = MagicMock(content="não sei o que fazer aqui")
        adapter = self._make_adapter(mock_agent)
        resp = adapter.request(text="x", context={})
        assert resp is None

    def test_returns_none_on_timeout(self) -> None:
        mock_agent = MagicMock()
        mock_agent.chat.side_effect = TimeoutError("timeout")
        adapter = self._make_adapter(mock_agent)
        resp = adapter.request(text="x", context={})
        assert resp is None

    def test_returns_none_on_missing_schema_fields(self) -> None:
        mock_agent = MagicMock()
        mock_agent.chat.return_value = MagicMock(content='{"commands": ["ls"]}')
        adapter = self._make_adapter(mock_agent)
        resp = adapter.request(text="x", context={})
        assert resp is None

    def test_context_sent_to_agent(self) -> None:
        mock_agent = MagicMock()
        mock_agent.chat.return_value = MagicMock(
            content='{"commands": ["pwd"], "explanation": "dir atual", "risk_level": "low", "assumptions": [], "required_user_confirmation": false}'
        )
        adapter = self._make_adapter(mock_agent)
        adapter.request(text="onde estou?", context={"cwd": "/home/user", "last_lines": "$ ls\nfoo bar"})
        call_args = mock_agent.chat.call_args
        # deve ter passado alguma mensagem para o agent
        assert call_args is not None
