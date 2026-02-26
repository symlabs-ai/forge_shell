"""
NLInterceptor — C2-T-05 + C2-T-06.

Intercepta bytes de input do usuário e os roteia para o NLModeEngine.
Retorna um InterceptResult que descreve a ação a tomar:
- TOGGLE: usuário digitou "!"
- EXEC_BASH: bash command (escape "!<cmd>" ou bash mode passthrough)
- SHOW_SUGGESTION: NL Mode produziu sugestão LLM
- NOOP: input vazio ou sem ação
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from src.application.usecases.nl_mode_engine import NLModeEngine
from src.infrastructure.intelligence.nl_response import NLResponse


class InterceptAction(str, Enum):
    TOGGLE = "toggle"
    EXEC_BASH = "exec_bash"
    SHOW_SUGGESTION = "show_suggestion"
    EXPLAIN = "explain"
    HELP = "help"
    NOOP = "noop"


@dataclass
class InterceptResult:
    action: InterceptAction
    bash_command: str | None = None
    suggestion: NLResponse | None = None
    requires_double_confirm: bool = False


class NLInterceptor:
    """
    Intercepta input bruto do terminal e o passa pelo NLModeEngine.

    Recebe bytes (linha digitada pelo usuário), decodifica, processa
    e retorna InterceptResult com a ação a tomar.
    """

    def __init__(self, nl_engine: NLModeEngine, context: dict | None = None) -> None:
        self._engine = nl_engine
        self._context: dict = context or {}

    def set_context(self, context: dict) -> None:
        """Atualizar contexto LLM (cwd, last_lines, last_cmd)."""
        self._context = context

    def intercept(
        self,
        data: bytes,
        on_chunk: Callable[[str], None] | None = None,
    ) -> InterceptResult:
        """
        Processar chunk de input.

        Retorna InterceptResult com a ação a executar.
        """
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = ""

        stripped = text.strip()

        if not stripped:
            return InterceptResult(action=InterceptAction.NOOP)

        result = self._engine.process_input(
            text=stripped, context=self._context, on_chunk=on_chunk
        )

        if result is None:
            # toggle — NLModeEngine retorna None quando há mudança de estado
            return InterceptResult(action=InterceptAction.TOGGLE)

        if result.is_help:
            return InterceptResult(action=InterceptAction.HELP)

        if result.is_explanation:
            return InterceptResult(
                action=InterceptAction.EXPLAIN,
                suggestion=result.suggestion,
            )

        if result.bash_command is not None:
            return InterceptResult(
                action=InterceptAction.EXEC_BASH,
                bash_command=result.bash_command,
            )

        if result.suggestion is not None:
            return InterceptResult(
                action=InterceptAction.SHOW_SUGGESTION,
                suggestion=result.suggestion,
                requires_double_confirm=result.requires_double_confirm,
            )

        return InterceptResult(action=InterceptAction.NOOP)
