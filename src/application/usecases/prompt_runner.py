"""
PromptRunner — execução one-shot de prompt NL (modo -p).

Recebe uma query em linguagem natural e usa um loop de investigação
(sonda) para resolver o problema iterativamente:

1. Traduz NL → bash via NLModeEngine
2. Executa silenciosamente (captura output)
3. Mostra a reflexão: o que tentou, o que aconteceu, e qual a próxima estratégia
4. Alimenta o output de volta ao LLM como contexto
5. Repete até resolver ou atingir max_iterations

O usuário vê o encadeamento de pensamentos emergindo em tempo real.

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
from src.infrastructure.intelligence.risk_engine import RiskEngine


# ANSI helpers
_BOLD = "\033[1m"
_GREEN = "\033[1;32m"
_YELLOW = "\033[1;33m"
_RED = "\033[1;31m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"
_WHITE = "\033[37m"

_MAX_SONDA_ITERATIONS = 5
_MAX_CONTEXT_LINES = 30


class PromptRunner:
    """Executa prompt NL com loop de investigação (sonda)."""

    def __init__(
        self,
        engine: NLModeEngine,
        risk_engine: RiskEngine | None = None,
        max_iterations: int = _MAX_SONDA_ITERATIONS,
    ) -> None:
        self._engine = engine
        self._risk = risk_engine or RiskEngine()
        self._max_iterations = max_iterations

    def run(self, prompt: str) -> int:
        """Processa o prompt com loop iterativo e retorna exit code."""
        context = {"cwd": os.getcwd()}
        history: list[dict] = []  # [{cmd, output, stderr, explanation, rc}]

        for iteration in range(self._max_iterations):
            enriched_prompt = self._build_enriched_prompt(prompt, history)

            # Indicador de progresso
            if not history:
                sys.stderr.write(f"{_CYAN}[forge_shell: pensando")
            else:
                sys.stderr.write(f"{_CYAN}[forge_shell: reformulando")
            sys.stderr.flush()
            _indicator_open = True

            def on_chunk(_chunk: str) -> None:
                nonlocal _indicator_open
                if _chunk.startswith("\n"):
                    # Atividade de sonda interna do agent — mostra como texto
                    if _indicator_open:
                        sys.stderr.write(f"]{_RESET}\n")
                        _indicator_open = False
                    sys.stderr.write(_chunk + "\n")
                    sys.stderr.flush()
                else:
                    if not _indicator_open:
                        sys.stderr.write(f"{_CYAN}[forge_shell: pensando")
                        _indicator_open = True
                    sys.stderr.write(".")
                    sys.stderr.flush()

            result = self._engine.process_input(
                text=enriched_prompt,
                context=context,
                on_chunk=on_chunk,
            )

            if _indicator_open:
                sys.stderr.write(f"]{_RESET}\n")
                sys.stderr.flush()

            # Falha do LLM — NÃO desiste, tenta de novo
            if result is None or result.suggestion is None:
                sys.stderr.write(
                    f"{_YELLOW}   LLM não retornou sugestão válida, "
                    f"tentando novamente...{_RESET}\n"
                )
                continue

            suggestion = result.suggestion
            cmd_str = " && ".join(suggestion.commands)
            explanation = suggestion.explanation

            # Use local RiskEngine (pattern-based) — more reliable than LLM
            local_risk = self._risk.classify(cmd_str)
            risk_level = local_risk.value.upper()

            # HIGH risk: mostra e para
            if risk_level == "HIGH":
                if history:
                    self._show_reflection(explanation)
                self._show_sonda_cmd(len(history) + 1, cmd_str, risk_level)
                sys.stderr.write(
                    f"   {_RED}Risco ALTO — comando não executado.{_RESET}\n"
                )
                return 2

            # Comando repetido — LLM acha que já resolveu
            if history and cmd_str == history[-1]["cmd"]:
                self._show_reflection(
                    "Mesmo comando da tentativa anterior — a investigação convergiu."
                )
                self._show_final_output(history[-1])
                return 0

            # Conclusão via echo — o agente já tem a resposta
            if self._is_echo_conclusion(cmd_str):
                if history:
                    self._show_reflection(explanation)
                sys.stderr.write(f"\n{_GREEN}[resultado]{_RESET}\n")
                sys.stderr.flush()
                # Extrai o conteúdo do echo
                msg = self._extract_echo_message(cmd_str)
                sys.stdout.write(msg + "\n")
                sys.stdout.flush()
                return 0

            # --- Reflexão narrativa (entre sondas) ---
            if history:
                self._show_reflection(explanation)

            # --- Executa sonda ---
            self._show_sonda_cmd(len(history) + 1, cmd_str, risk_level)

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

            # Mostra o que a sonda devolveu
            self._show_sonda_result(step)

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

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_enriched_prompt(
        self, original: str, history: list[dict]
    ) -> str:
        """Constrói prompt enriquecido com histórico de tentativas.

        Inclui avaliação explícita de cada resultado e instrui o LLM
        a concluir quando a investigação já respondeu à pergunta.
        """
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

            # Avaliação explícita do resultado
            parts.append(self._evaluate_step(step, original))

        parts.append("")
        parts.append(
            "INSTRUÇÕES:\n"
            "1. AVALIE: o resultado das tentativas anteriores RESPONDE "
            "à pergunta do usuário?\n"
            "2. Se SIM (mesmo que a resposta seja 'não encontrado'): "
            "CONCLUA usando echo, ex: commands: [\"echo 'Resposta aqui'\"]\n"
            "3. Se NÃO: tente uma abordagem DIFERENTE. No campo "
            "'explanation', explique por que a anterior não funcionou.\n"
            "4. NUNCA sugira comandos em caminhos que você não verificou.\n"
            "5. NUNCA sugira 'ls' em um diretório aleatório como resposta."
        )
        return "\n".join(parts)

    @staticmethod
    def _evaluate_step(step: dict, original_query: str) -> str:
        """Avalia se o resultado de uma tentativa responde à pergunta."""
        output = step.get("output", "").strip()
        stderr = step.get("stderr", "").strip()
        rc = step.get("rc", 0)
        cmd = step.get("cmd", "")

        # find com output vazio = não encontrado
        if "find " in cmd and not output and rc in (0, 1):
            return "AVALIAÇÃO: Busca não retornou resultados — o item NÃO existe no caminho buscado."

        # Comando falhou
        if rc != 0 and not output:
            return "AVALIAÇÃO: Comando falhou. O resultado NÃO responde à pergunta."

        # Comando teve output — mas é relevante?
        if output and "echo " not in cmd:
            return "AVALIAÇÃO: Comando retornou output. Verifique se este output RESPONDE à pergunta original."

        return ""

    @staticmethod
    def _is_echo_conclusion(cmd: str) -> bool:
        """Detecta se o comando é uma conclusão via echo (resposta direta)."""
        stripped = cmd.strip()
        return stripped.startswith("echo ") or stripped.startswith("echo\t")

    @staticmethod
    def _extract_echo_message(cmd: str) -> str:
        """Extrai a mensagem de um comando echo."""
        stripped = cmd.strip()
        msg = stripped[5:].strip()  # remove "echo "
        # Remove aspas envolventes
        if len(msg) >= 2:
            if (msg[0] == "'" and msg[-1] == "'") or (msg[0] == '"' and msg[-1] == '"'):
                msg = msg[1:-1]
        return msg

    @staticmethod
    def _truncate_output(output: str) -> str:
        """Trunca output para caber no contexto do LLM."""
        lines = output.strip().splitlines()
        if len(lines) > _MAX_CONTEXT_LINES:
            kept = lines[:_MAX_CONTEXT_LINES]
            kept.append(f"... (+{len(lines) - _MAX_CONTEXT_LINES} linhas)")
            return "\n".join(kept)
        return output.strip()

    # ------------------------------------------------------------------
    # Output rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _show_reflection(text: str) -> None:
        """Mostra bloco de reflexão narrativa entre sondas."""
        sys.stderr.write(f"\n{_CYAN}   >> {text}{_RESET}\n")
        sys.stderr.flush()

    @staticmethod
    def _show_sonda_cmd(step_num: int, cmd: str, risk_level: str) -> None:
        """Mostra o comando da sonda que vai executar."""
        risk_color = _GREEN if risk_level == "LOW" else _YELLOW if risk_level == "MEDIUM" else _RED
        sys.stderr.write(
            f"\n{_MAGENTA}[sonda {step_num}]{_RESET} {_BOLD}{cmd}{_RESET}\n"
        )
        sys.stderr.write(f"   Risco: {risk_color}{risk_level.lower()}{_RESET}\n")
        sys.stderr.flush()

    @staticmethod
    def _show_sonda_result(step: dict) -> None:
        """Mostra resumo do que a sonda devolveu."""
        output = step.get("output", "").strip()
        stderr = step.get("stderr", "").strip()
        rc = step.get("rc", 0)

        if rc != 0 and stderr:
            first_line = stderr.splitlines()[0][:120]
            sys.stderr.write(f"   {_RED}→ erro: {first_line}{_RESET}\n")
        elif output:
            lines = output.splitlines()
            if len(lines) == 1:
                preview = lines[0][:120]
                sys.stderr.write(f"   {_GREEN}→ {preview}{_RESET}\n")
            elif len(lines) <= 3:
                for line in lines:
                    sys.stderr.write(f"   {_GREEN}→ {line[:120]}{_RESET}\n")
            else:
                for line in lines[:2]:
                    sys.stderr.write(f"   {_GREEN}→ {line[:120]}{_RESET}\n")
                sys.stderr.write(
                    f"   {_DIM}  (+{len(lines) - 2} linhas){_RESET}\n"
                )
        else:
            sys.stderr.write(f"   {_YELLOW}→ (sem output){_RESET}\n")

        sys.stderr.flush()

    @staticmethod
    def _pick_best_result(history: list[dict]) -> dict | None:
        """Escolhe o melhor resultado do histórico (prefere output com conteúdo)."""
        if not history:
            return None
        for step in reversed(history):
            if step.get("output", "").strip() and step.get("rc", 1) == 0:
                return step
        for step in reversed(history):
            if step.get("output", "").strip():
                return step
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
