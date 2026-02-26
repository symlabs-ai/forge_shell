"""
ForgeLLMAdapter — adapter para o ForgeLLM (forge-llm library).

Converte requisições NL em NLResponse validada.
Em caso de falha (timeout, schema inválido, exceção), retorna None
sem propagar exceção — o terminal nunca trava por causa do LLM.

Funcionalidades do ForgeLLM aproveitadas:
- ChatConfig(temperature=0.2): respostas determinísticas para shell commands
- Histórico multi-turn: últimas N exchanges incluídas em cada requisição,
  permitindo follow-ups naturais ("mostre só os 3 maiores")
- stream_chat(): tokens chegam em chunks via on_chunk(), habilitando
  indicador animado de "pensando" no terminal
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable

from forge_llm import ChatAgent, ChatConfig, ChatMessage, SummarizeCompactor

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
    Adapter para ForgeLLM com histórico multi-turn e streaming.

    Parâmetros:
        api_key: chave de API do provider (ou None para usar variável de ambiente)
        provider: nome do provider (ollama, openai, anthropic, openrouter, xai)
        model: modelo a usar
        timeout_seconds: timeout da requisição
        max_retries: tentativas em caso de falha transiente (caminho não-streaming)
        max_history: número máximo de exchanges (pares user/assistant) mantidos
    """

    _ENV_KEY_MAP = {
        "xai": "XAI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "symrouter": "SYMROUTER_API_KEY",
    }

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "ollama",
        model: str = "llama3",
        timeout_seconds: int = 30,
        max_retries: int = 2,
        max_history: int = 5,
    ) -> None:
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._agent = None  # lazy: criado na primeira chamada a request()/explain()
        # histórico multi-turn: lista alternada [user, assistant, user, assistant, ...]
        self._history: list[ChatMessage] = []
        self._max_history = max_history
        # temperatura baixa = respostas mais determinísticas para shell commands
        self._config = ChatConfig(temperature=0.2)

    def _get_agent(self) -> ChatAgent:
        """Retorna o ChatAgent, criando-o lazily na primeira chamada."""
        if self._agent is None:
            resolved_key = self._api_key or os.environ.get(
                self._ENV_KEY_MAP.get(self._provider, ""), None
            )
            self._agent = ChatAgent(
                provider=self._provider, api_key=resolved_key, model=self._model
            )
        return self._agent

    def _compact_history(self) -> None:
        """
        Compactar histórico quando excede max_history exchanges.

        Usa SummarizeCompactor: o LLM resume as mensagens mais antigas em um
        bloco de contexto compacto, preservando semântica (não apenas trunca).
        Se a sumarização falhar, cai back para truncação simples.
        """
        max_msgs = self._max_history * 2
        if len(self._history) <= max_msgs:
            return
        try:
            compactor = SummarizeCompactor(
                agent=self._get_agent(),
                summary_tokens=150,
                keep_recent=4,
            )
            # ~250 tokens por mensagem como estimativa para o target
            self._history = compactor.compact(
                self._history, target_tokens=max_msgs * 250
            )
        except Exception as exc:
            log.warning("SummarizeCompactor falhou, truncando: %s", exc)
            self._history = self._history[-max_msgs:]

    def request(
        self,
        text: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResponse | None:
        """
        Enviar requisição NL ao ForgeLLM.

        Retorna NLResponse validada ou None em caso de falha.
        Nunca lança exceção para não travar o terminal.

        Parâmetros:
            on_chunk: callback chamado com cada chunk de texto durante streaming.
                      Se fornecido, usa stream_chat() em vez de chat().
                      Se None, usa chat() com retry normal.
        """
        prompt = self._build_prompt(text, context)
        user_msg = ChatMessage(role="user", content=prompt)
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            *self._history,
            user_msg,
        ]

        if on_chunk is not None:
            # caminho streaming: sem retry (evita duplicar output no terminal)
            try:
                raw_content = ""
                for chunk in self._get_agent().stream_chat(
                    messages=messages, config=self._config
                ):
                    if chunk.content:
                        raw_content += chunk.content
                        on_chunk(chunk.content)
                result = self._parse(raw_content)
                if result is not None:
                    self._history.append(user_msg)
                    self._history.append(
                        ChatMessage(role="assistant", content=raw_content)
                    )
                    self._compact_history()
                return result
            except Exception as exc:
                log.warning("ForgeLLM stream error: %s", exc)
                return None

        # caminho não-streaming: mantém retry para tolerância a falhas transientes
        for attempt in range(self._max_retries + 1):
            try:
                response = self._get_agent().chat(
                    messages=messages, config=self._config
                )
                result = self._parse(response.content)
                if result is not None:
                    self._history.append(user_msg)
                    self._history.append(
                        ChatMessage(role="assistant", content=response.content)
                    )
                    self._compact_history()
                return result
            except TimeoutError:
                log.warning(
                    "ForgeLLM timeout (attempt %d/%d)", attempt + 1, self._max_retries + 1
                )
            except Exception as exc:
                log.warning("ForgeLLM error: %s", exc)
                break

        return None

    def explain(
        self,
        command: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResponse | None:
        """
        Analisar e explicar um comando sem executá-lo (:explain <cmd>).

        Usa system prompt separado; sem histórico (análise pontual).
        Retorna NLResponse ou None em caso de falha.
        """
        prompt = f"Comando a analisar: {command}"
        if context.get("cwd"):
            prompt += f"\nDiretório atual: {context['cwd']}"
        messages = [
            ChatMessage(role="system", content=_EXPLAIN_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ]
        if on_chunk is not None:
            try:
                raw_content = ""
                for chunk in self._get_agent().stream_chat(
                    messages=messages, config=self._config
                ):
                    if chunk.content:
                        raw_content += chunk.content
                        on_chunk(chunk.content)
                return self._parse(raw_content)
            except Exception as exc:
                log.warning("ForgeLLM explain stream error: %s", exc)
                return None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._get_agent().chat(
                    messages=messages, config=self._config
                )
                return self._parse(response.content)
            except TimeoutError:
                log.warning(
                    "ForgeLLM explain timeout (attempt %d/%d)",
                    attempt + 1, self._max_retries + 1,
                )
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
