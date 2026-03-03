"""
PromptRunner — execução one-shot de prompt NL (modo -p).

Recebe uma query em linguagem natural, traduz via NLModeEngine,
exibe o comando sugerido e executa se o risco for LOW/MEDIUM.

Exit codes:
- 0: comando executado com sucesso
- 1: erro (LLM falhou, parse falhou)
- 2: risco HIGH (não executado)
"""
from __future__ import annotations

import os
import subprocess
import sys

from src.application.usecases.nl_mode_engine import NLModeEngine


# ANSI helpers
_BOLD = "\033[1m"
_GREEN = "\033[1;32m"
_YELLOW = "\033[1;33m"
_RED = "\033[1;31m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_CYAN = "\033[36m"


class PromptRunner:
    """Executa prompt NL one-shot sem PTY interativo."""

    def __init__(self, engine: NLModeEngine) -> None:
        self._engine = engine

    def run(self, prompt: str) -> int:
        """Processa o prompt e retorna exit code."""
        context = {"cwd": os.getcwd()}

        # Indicador de progresso
        sys.stderr.write(f"{_CYAN}[forge_shell: pensando")
        sys.stderr.flush()

        def on_chunk(_chunk: str) -> None:
            sys.stderr.write(".")
            sys.stderr.flush()

        result = self._engine.process_input(
            text=prompt,
            context=context,
            on_chunk=on_chunk,
        )

        sys.stderr.write(f"]{_RESET}\n")
        sys.stderr.flush()

        if result is None or result.suggestion is None:
            sys.stderr.write(f"{_RED}[forge_shell] Falha ao processar prompt.{_RESET}\n")
            return 1

        suggestion = result.suggestion
        commands = suggestion.commands
        explanation = suggestion.explanation
        risk_level = suggestion.risk_level.value.upper()

        cmd_str = " && ".join(commands)

        # Exibir sugestão
        sys.stderr.write(f"\n{_GREEN}[*]{_RESET} {_BOLD}{cmd_str}{_RESET}\n")
        sys.stderr.write(f"   {explanation}\n")

        if risk_level == "LOW":
            risk_color = _GREEN
        elif risk_level == "MEDIUM":
            risk_color = _YELLOW
        else:
            risk_color = _RED
        sys.stderr.write(f"   Risco: {risk_color}{risk_level.lower()}{_RESET}\n\n")

        # HIGH risk: não executar
        if risk_level == "HIGH":
            sys.stderr.write(
                f"{_RED}[!] Risco ALTO — comando não executado.{_RESET}\n"
            )
            return 2

        # Executar comando
        proc = subprocess.run(
            cmd_str,
            shell=True,
            cwd=os.getcwd(),
        )
        return proc.returncode
