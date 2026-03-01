"""
InterceptAction e InterceptResult — tipos leves para intercept de input.

Extraídos de nl_interceptor.py para quebrar a cadeia de imports pesados:
  terminal_session → nl_interceptor → nl_mode_engine → forge_llm_adapter → forge_llm

Este módulo depende APENAS da stdlib (dataclasses, enum, typing).
Isso permite que terminal_session e output_renderer importem InterceptAction
sem puxar forge_llm, httpx, pyte etc.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class InterceptAction(str, Enum):
    TOGGLE = "toggle"
    EXEC_BASH = "exec_bash"
    SHOW_SUGGESTION = "show_suggestion"
    EXPLAIN = "explain"
    HELP = "help"
    RISK = "risk"
    NOOP = "noop"


@dataclass
class InterceptResult:
    action: InterceptAction
    bash_command: str | None = None
    suggestion: Any | None = None
    requires_double_confirm: bool = False
    risk_level: Any | None = None
