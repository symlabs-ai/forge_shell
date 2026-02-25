"""
ForgeLLMAdapter — adapter para o ForgeLLM (forge-llm library).

Converte requisições NL em NLResponse validada.
Em caso de falha (timeout, schema inválido, exceção), retorna None
sem propagar exceção — o terminal nunca trava por causa do LLM.
"""
from __future__ import annotations

import json
import logging

from forge_llm import ChatAgent, ChatMessage

from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um assistente de terminal Unix. O usuário descreve uma ação em linguagem natural.
Responda SOMENTE com JSON válido no seguinte schema (sem markdown, sem texto extra):
{
  "commands": ["<comando bash 1>", "..."],
  "explanation": "<explicação curta do que vai acontecer>",
  "risk_level": "low" | "medium" | "high",
  "assumptions": ["<premissa 1>", "..."],
  "required_user_confirmation": true | false
}

Critérios de risk_level:
- low: leitura, listagem, informação — sem efeito colateral
- medium: modificação reversível, kill de processo, restart de serviço
- high: deleção irreversível, formatação, alteração de arquivos críticos do sistema
"""

_EXPLAIN_SYSTEM_PROMPT = """Você é um assistente de terminal Unix especializado em análise de comandos.
O usuário fornece um comando bash. Analise-o e responda SOMENTE com JSON válido (sem markdown, sem texto extra):
{
  "commands": ["<o próprio comando recebido>"],
  "explanation": "<explicação detalhada do que o comando faz, passo a passo>",
  "risk_level": "low" | "medium" | "high",
  "assumptions": ["<premissa ou aviso importante>"],
  "required_user_confirmation": true | false
}
NÃO execute o comando. Apenas analise e explique.
"""


class ForgeLLMAdapter:
    """
    Adapter para ForgeLLM.

    Parâmetros:
        api_key: chave de API do provider (ou None para usar variável de ambiente)
        provider: nome do provider (ollama, openai, anthropic, openrouter)
        model: modelo a usar
        timeout_seconds: timeout da requisição
        max_retries: tentativas em caso de falha transiente
    """

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "ollama",
        model: str = "llama3",
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ) -> None:
        self._agent = ChatAgent(provider=provider, api_key=api_key, model=model)
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def request(self, text: str, context: dict) -> NLResponse | None:
        """
        Enviar requisição NL ao ForgeLLM.

        Retorna NLResponse validada ou None em caso de falha.
        Nunca lança exceção para não travar o terminal.
        """
        prompt = self._build_prompt(text, context)
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ]

        for attempt in range(self._max_retries + 1):
            try:
                response = self._agent.chat(messages=messages)
                return self._parse(response.content)
            except TimeoutError:
                log.warning("ForgeLLM timeout (attempt %d/%d)", attempt + 1, self._max_retries + 1)
            except Exception as exc:
                log.warning("ForgeLLM error: %s", exc)
                break

        return None

    def explain(self, command: str, context: dict) -> NLResponse | None:
        """
        Analisar e explicar um comando sem executá-lo (:explain <cmd>).

        Retorna NLResponse ou None em caso de falha.
        """
        prompt = f"Comando a analisar: {command}"
        if context.get("cwd"):
            prompt += f"\nDiretório atual: {context['cwd']}"
        messages = [
            ChatMessage(role="system", content=_EXPLAIN_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ]
        for attempt in range(self._max_retries + 1):
            try:
                response = self._agent.chat(messages=messages)
                return self._parse(response.content)
            except TimeoutError:
                log.warning("ForgeLLM explain timeout (attempt %d/%d)", attempt + 1, self._max_retries + 1)
            except Exception as exc:
                log.warning("ForgeLLM explain error: %s", exc)
                break
        return None

    def _build_prompt(self, text: str, context: dict) -> str:
        parts = [f"Ação solicitada: {text}"]
        if context.get("cwd"):
            parts.append(f"Diretório atual: {context['cwd']}")
        if context.get("last_lines"):
            parts.append(f"Últimas linhas do terminal:\n{context['last_lines']}")
        return "\n".join(parts)

    def _parse(self, content: str) -> NLResponse | None:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            log.warning("ForgeLLM: resposta não é JSON válido")
            return None

        try:
            return NLResponse(
                commands=data["commands"],
                explanation=data["explanation"],
                risk_level=RiskLevel(data["risk_level"]),
                assumptions=data.get("assumptions", []),
                required_user_confirmation=data["required_user_confirmation"],
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("ForgeLLM: schema inválido — %s", exc)
            return None
