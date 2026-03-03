"""
PromptRunner — execução one-shot de prompt NL (modo -p).

Recebe uma query em linguagem natural e usa um loop de investigação
(sonda) para resolver o problema iterativamente:

1. Traduz NL → bash via NLModeEngine
2. Executa silenciosamente (captura output)
3. Ecoa o passo + resumo do output para o usuário
4. Alimenta o output de volta ao LLM como contexto
5. Repete até resolver ou atingir max_iterations

A cada iteração, ecoa o processo de reflexão para o usuário:
o que foi tentado, o que a sonda devolveu, e por que está mudando
de estratégia.

Exit codes:
- 0: resolvido com sucesso
- 1: erro (LLM falhou em TODAS as tentativas)
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
        history: list[dict] = []  # [{cmd, output, stderr, explanation, rc}]
        llm_failures = 0

        for iteration in range(self._max_iterations):
            # Monta prompt enriquecido com histórico
            enriched_prompt = self._build_enriched_prompt(prompt, history)

            # Indicador de progresso
            step_num = len(history) + 1
            if not history:
                label = "pensando"
            else:
                label = f"refletindo sobre sonda {len(history)}"
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

            # Falha do LLM — NÃO desiste, tenta de novo
            if result is None or result.suggestion is None:
                llm_failures += 1
                sys.stderr.write(
                    f"{_YELLOW}   LLM não retornou sugestão válida, "
                    f"tentando novamente...{_RESET}\n"
                )
                continue

            suggestion = result.suggestion
            cmd_str = " && ".join(suggestion.commands)
            explanation = suggestion.explanation
            risk_level = suggestion.risk_level.value.upper()

            # HIGH risk: mostra e para
            if risk_level == "HIGH":
                self._show_sonda_step(step_num, cmd_str, explanation, risk_level)
                sys.stderr.write(
                    f"   {_RED}[!] Risco ALTO — comando não executado.{_RESET}\n"
                )
                return 2

            # Comando repetido — LLM acha que já resolveu
            if history and cmd_str == history[-1]["cmd"]:
                sys.stderr.write(
                    f"{_DIM}   (mesmo comando da tentativa anterior — "
                    f"encerrando investigação){_RESET}\n"
                )
                self._show_final_output(history[-1])
                return 0

            # Executa silenciosamente (sonda-style)
            try:
                proc = subprocess.run(
                    cmd_str,
                    shell=True,
                    capture_output=True,
                    cwd=os.getcwd(),
                    timeout=60,
                )
                stdout = proc.stdout.decode(errors="replace")
                stderr = proc.stderr.decode(errors="replace")
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                stdout = ""
                stderr = "Timeout: comando excedeu 60 segundos"
                rc = 124

            step = {
                "cmd": cmd_str,
                "output": stdout,
                "stderr": stderr,
                "explanation": explanation,
                "rc": rc,
            }
            history.append(step)

            # Ecoa o passo + resumo do output
            self._show_sonda_step(step_num, cmd_str, explanation, risk_level)
            self._show_sonda_output_summary(step)

        # Loop encerrado — mostra o melhor resultado que temos
        best = self._pick_best_result(history)
        if best:
            self._show_final_output(best)
            return best.get("rc", 0)

        sys.stderr.write(
            f"\n{_RED}[forge_shell] Não foi possível resolver após "
            f"{self._max_iterations} tentativas.{_RESET}\n"
        )
        return 1

    def _build_enriched_prompt(
        self, original: str, history: list[dict]
    ) -> str:
        """Constrói prompt enriquecido com histórico de tentativas."""
        if not history:
            return original

        parts = [f"Pedido original: {original}", "", "Tentativas anteriores:"]
        for i, step in enumerate(history, 1):
            parts.append(f"\n--- Tentativa {i} ---")
            parts.append(f"Comando: {step['cmd']}")

            output = step.get("output", "").strip()
            stderr = step.get("stderr", "").strip()
            rc = step.get("rc", 0)

            if rc != 0:
                parts.append(f"Exit code: {rc} (ERRO)")
            if output:
                preview = self._truncate_output(output)
                parts.append(f"Stdout: {preview}")
            else:
                parts.append("Stdout: (vazio)")
            if stderr:
                parts.append(f"Stderr: {self._truncate_output(stderr)}")

        parts.append("")
        parts.append(
            "ANÁLISE: Os comandos anteriores NÃO resolveram o pedido do usuário. "
            "Você DEVE usar uma estratégia DIFERENTE das anteriores. "
            "NÃO repita comandos que já falharam. "
            "Considere: find, locate, grep -r, which, whereis, dpkg -L, pip show."
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
        sys.stderr.write(f"   {explanation}\n")
        sys.stderr.write(f"   Risco: {risk_color}{risk_level.lower()}{_RESET}\n")
        sys.stderr.flush()

    @staticmethod
    def _show_sonda_output_summary(step: dict) -> None:
        """Mostra resumo do output da sonda para o usuário acompanhar."""
        output = step.get("output", "").strip()
        stderr = step.get("stderr", "").strip()
        rc = step.get("rc", 0)

        if rc != 0 and stderr:
            # Comando falhou — mostra o erro
            first_line = stderr.splitlines()[0][:120]
            sys.stderr.write(f"   {_RED}→ erro: {first_line}{_RESET}\n")
        elif output:
            # Comando teve output — mostra resumo
            lines = output.splitlines()
            if len(lines) == 1:
                preview = lines[0][:120]
                sys.stderr.write(f"   {_GREEN}→ {preview}{_RESET}\n")
            else:
                first = lines[0][:80]
                sys.stderr.write(
                    f"   {_GREEN}→ {first}  {_DIM}(+{len(lines) - 1} linhas){_RESET}\n"
                )
        else:
            sys.stderr.write(f"   {_YELLOW}→ (sem output){_RESET}\n")

        sys.stderr.flush()

    @staticmethod
    def _pick_best_result(history: list[dict]) -> dict | None:
        """Escolhe o melhor resultado do histórico (prefere output com conteúdo)."""
        if not history:
            return None
        # Prefere o último passo que teve output com sucesso
        for step in reversed(history):
            if step.get("output", "").strip() and step.get("rc", 1) == 0:
                return step
        # Senão, prefere qualquer um com output
        for step in reversed(history):
            if step.get("output", "").strip():
                return step
        # Senão, o último
        return history[-1]

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
