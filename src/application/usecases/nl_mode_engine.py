"""
NLModeEngine — motor de estado do NL Mode.

Gerencia a alternância entre NL Mode e Bash Mode, processa input
do usuário e retorna a ação correta (sugestão NL ou comando bash direto).

Fluxo:
- NL Mode ativo (padrão): texto → ForgeLLM → NLResult com sugestão
- ``!`` sozinho → toggle NL ↔ Bash
- ``!<cmd>`` → executa bash direto, retorna ao NL Mode
- Bash Mode ativo: todo input é passthrough para o PTY
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from src.application.ports.agent_port import AgentPort
from src.infrastructure.intelligence.forge_llm_adapter import ForgeLLMAdapter
from src.infrastructure.intelligence.nl_response import NLResponse, RiskLevel
from src.infrastructure.intelligence.risk_engine import RiskEngine


class NLModeState(str, Enum):
    NL_ACTIVE = "nl_active"
    BASH_ACTIVE = "bash_active"


@dataclass
class NLResult:
    """Resultado do processamento de input pelo NLModeEngine."""
    suggestion: NLResponse | None = None
    bash_command: str | None = None
    requires_double_confirm: bool = False
    state_changed: bool = False
    is_explanation: bool = False
    is_help: bool = False
    is_risk: bool = False
    risk_level: RiskLevel | None = None


class NLModeEngine:
    """
    Motor central do NL Mode.

    Parâmetros:
        llm_adapter: adapter ForgeLLM para requisições NL
        risk_engine: engine de classificação de risco
    """

    def __init__(
        self,
        llm_adapter: ForgeLLMAdapter,
        risk_engine: RiskEngine,
        agent_service: AgentPort | None = None,
        default_active: bool = True,
    ) -> None:
        self._adapter = llm_adapter
        self._risk = risk_engine
        self._agent = agent_service
        self._state = NLModeState.NL_ACTIVE if default_active else NLModeState.BASH_ACTIVE

    @property
    def state(self) -> NLModeState:
        return self._state

    def toggle(self) -> None:
        """Alternar entre NL Mode e Bash Mode."""
        if self._state == NLModeState.NL_ACTIVE:
            self._state = NLModeState.BASH_ACTIVE
        else:
            self._state = NLModeState.NL_ACTIVE

    def process_input(
        self,
        text: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResult | None:
        """
        Processar input do usuário.

        Retorna:
        - None se foi toggle (sem ação de output)
        - NLResult com bash_command se foi escape ``!<cmd>``
        - NLResult com suggestion se foi requisição NL
        - NLResult com bash_command se estiver em Bash Mode
        """
        stripped = text.strip()

        # --- toggle ``!`` sozinho ---
        if stripped == "!":
            self.toggle()
            return None

        # --- escape ``!<cmd>`` → bash direto, volta ao NL Mode ---
        if stripped.startswith("!") and len(stripped) > 1:
            bash_cmd = stripped[1:].lstrip()
            self._state = NLModeState.NL_ACTIVE
            return NLResult(bash_command=bash_cmd)

        # --- :help → exibir ajuda local (sem LLM, funciona em ambos os modos) ---
        if stripped.lower() == ":help":
            return NLResult(is_help=True)

        # --- :risk <cmd> → classificar risco local (sem LLM, funciona em ambos os modos) ---
        if stripped.lower().startswith(":risk ") and len(stripped) > 6:
            cmd = stripped[6:].strip()
            level = self._risk.classify(cmd)
            return NLResult(is_risk=True, risk_level=level)

        # --- :explain <cmd> → análise pontual do LLM (funciona em ambos os modos) ---
        if stripped.lower().startswith(":explain ") and len(stripped) > 9:
            cmd = stripped[9:].strip()
            response = self._adapter.explain(command=cmd, context=context, on_chunk=on_chunk)
            return NLResult(suggestion=response, is_explanation=True)

        # --- Bash Mode passthrough ---
        if self._state == NLModeState.BASH_ACTIVE:
            return NLResult(bash_command=stripped)

        # --- shell builtins: sempre passthrough sem LLM ---
        if stripped in {"exit", "logout"}:
            return NLResult(bash_command=stripped)

        # --- NL Mode: envia ao Agent (se habilitado) ou ForgeLLM ---
        if self._agent is not None:
            response = self._agent.process(text=text, context=context, on_chunk=on_chunk)
        else:
            response = self._adapter.request(text=text, context=context, on_chunk=on_chunk)

        if response is None:
            return NLResult()

        double_confirm = self._risk.requires_double_confirm(
            response.commands[0] if response.commands else ""
        )

        return NLResult(
            suggestion=response,
            requires_double_confirm=double_confirm,
        )
