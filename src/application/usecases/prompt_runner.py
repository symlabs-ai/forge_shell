"""
PromptRunner — execução one-shot de prompt NL (modo -p).

Recebe uma query em linguagem natural e usa um loop de investigação
(sonda) para resolver o problema iterativamente:

1. Traduz NL → bash via NLModeEngine
2. Executa silenciosamente (captura output)
3. Alimenta o output de volta ao LLM como contexto
4. Repete até resolver ou atingir max_iterations

A cada iteração, ecoa o processo de reflexão para o usuário.

Exit codes:
- 0: resolvido com sucesso
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
_MAGENTA = "\033[35m"

_MAX_SONDA_ITERATIONS = 5
_MAX_CONTEXT_LINES = 30


class PromptRunner:
    """Executa prompt NL com loop de investigação (sonda)."""

    def __init__(
        self,
        engine: NLModeEngine,
        max_iterations: int = _MAX_SONDA_ITERATIONS,
    ) -> None:
        self._engine = engine
        self._max_iterations = max_iterations

    def run(self, prompt: str) -> int:
        """Processa o prompt com loop iterativo e retorna exit code."""
        context = {"cwd": os.getcwd()}
        history: list[dict] = []  # [{cmd, output, explanation}]

        for iteration in range(self._max_iterations):
            # Monta prompt enriquecido com histórico
            enriched_prompt = self._build_enriched_prompt(prompt, history)

            # Indicador de progresso
            label = "pensando" if iteration == 0 else "refletindo"
            sys.stderr.write(f"{_CYAN}[forge_shell: {label}")
            sys.stderr.flush()

            def on_chunk(_chunk: str) -> None:
                sys.stderr.write(".")
                sys.stderr.flush()

            result = self._engine.process_input(
                text=enriched_prompt,
                context=context,
                on_chunk=on_chunk,
            )

            sys.stderr.write(f"]{_RESET}\n")
            sys.stderr.flush()

            # Falha do LLM
            if result is None or result.suggestion is None:
                if history:
                    # Temos resultado anterior — mostra o que tem
                    self._show_final_output(history[-1])
                    return 0
                sys.stderr.write(
                    f"{_RED}[forge_shell] Falha ao processar prompt.{_RESET}\n"
                )
                return 1

            suggestion = result.suggestion
            cmd_str = " && ".join(suggestion.commands)
            explanation = suggestion.explanation
            risk_level = suggestion.risk_level.value.upper()

            # HIGH risk: mostra e para
            if risk_level == "HIGH":
                self._show_sonda_step(iteration + 1, cmd_str, explanation, risk_level)
                sys.stderr.write(
                    f"{_RED}[!] Risco ALTO — comando não executado.{_RESET}\n"
                )
                return 2

            # Comando repetido — LLM acha que já resolveu
            if history and cmd_str == history[-1]["cmd"]:
                self._show_final_output(history[-1])
                return 0

            # Executa silenciosamente (sonda-style)
            proc = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                cwd=os.getcwd(),
                timeout=60,
            )
            stdout = proc.stdout.decode(errors="replace")
            stderr = proc.stderr.decode(errors="replace")

            step = {"cmd": cmd_str, "output": stdout, "stderr": stderr, "explanation": explanation}
            history.append(step)

            # Ecoa o passo de investigação para o usuário
            self._show_sonda_step(iteration + 1, cmd_str, explanation, risk_level)

            # Última iteração — mostra output final
            if iteration == self._max_iterations - 1:
                self._show_final_output(step)
                return proc.returncode

        # Fallback (não deve chegar aqui)
        if history:
            self._show_final_output(history[-1])
        return 0

    def _build_enriched_prompt(
        self, original: str, history: list[dict]
    ) -> str:
        """Constrói prompt enriquecido com histórico de tentativas."""
        if not history:
            return original

        parts = [f"Pedido original: {original}", "", "Tentativas anteriores:"]
        for i, step in enumerate(history, 1):
            output_preview = self._truncate_output(step["output"])
            parts.append(f"{i}. Comando: {step['cmd']}")
            if output_preview:
                parts.append(f"   Output: {output_preview}")
            else:
                parts.append("   Output: (vazio — o comando não encontrou nada)")

        parts.append("")
        parts.append(
            "Os comandos anteriores NÃO resolveram o pedido. "
            "Mude de estratégia: use um comando DIFERENTE dos anteriores. "
            "Dicas: find, locate, grep -r, which, whereis são boas opções para buscas."
        )
        return "\n".join(parts)

    @staticmethod
    def _truncate_output(output: str) -> str:
        """Trunca output para caber no contexto do LLM."""
        lines = output.strip().splitlines()
        if len(lines) > _MAX_CONTEXT_LINES:
            kept = lines[:_MAX_CONTEXT_LINES]
            kept.append(f"... (+{len(lines) - _MAX_CONTEXT_LINES} linhas)")
            return "\n".join(kept)
        return output.strip()

    @staticmethod
    def _show_sonda_step(
        step_num: int, cmd: str, explanation: str, risk_level: str
    ) -> None:
        """Ecoa passo de investigação para o usuário."""
        risk_color = _GREEN if risk_level == "LOW" else _YELLOW if risk_level == "MEDIUM" else _RED
        sys.stderr.write(
            f"\n{_MAGENTA}[sonda {step_num}]{_RESET} {_BOLD}{cmd}{_RESET}\n"
        )
        sys.stderr.write(f"   {_DIM}{explanation}{_RESET}\n")
        sys.stderr.write(f"   Risco: {risk_color}{risk_level.lower()}{_RESET}\n")
        sys.stderr.flush()

    @staticmethod
    def _show_final_output(step: dict) -> None:
        """Mostra output final da investigação."""
        output = step.get("output", "")
        stderr_out = step.get("stderr", "")
        has_output = bool(output.strip()) or bool(stderr_out.strip())

        if has_output:
            sys.stderr.write(f"\n{_GREEN}[resultado]{_RESET}\n")
            sys.stderr.flush()
            if output.strip():
                sys.stdout.write(output)
                if not output.endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()
            if stderr_out.strip():
                sys.stderr.write(stderr_out)
                if not stderr_out.endswith("\n"):
                    sys.stderr.write("\n")
                sys.stderr.flush()
        else:
            sys.stderr.write(
                f"\n{_YELLOW}[forge_shell] Investigação inconclusiva "
                f"— nenhum resultado encontrado.{_RESET}\n"
            )
            sys.stderr.flush()
