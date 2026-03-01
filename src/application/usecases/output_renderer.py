"""
OutputRenderer — renderização de sugestões, ajuda e indicadores no terminal.

Extraído de TerminalSession para separar a responsabilidade de formatação
ANSI/terminal do loop principal de I/O.
"""
from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from src.application.usecases.intercept_types import InterceptAction

if TYPE_CHECKING:
    from src.infrastructure.terminal_engine.pty_engine import PTYEngine


class OutputRenderer:
    """Renderiza output formatado (sugestões, ajuda, indicadores) no terminal."""

    def __init__(self, engine: PTYEngine, stdout=None) -> None:
        self._engine = engine
        self._stdout = stdout

    @property
    def _out(self):
        return self._stdout or getattr(sys.stdout, "buffer", None)

    def handle_intercept_result(self, result, mode, set_mode, set_pty_running) -> None:
        """Processar resultado do NLInterceptor: executar comando, exibir sugestão ou indicador.

        Args:
            result: InterceptResult from NLInterceptor
            mode: current SessionMode
            set_mode: callable(new_mode) to update session mode
            set_pty_running: callable(bool) to update pty_running state
        """
        if result is None:
            return
        out = self._out

        if result.action == InterceptAction.NOOP:
            return

        if result.action == InterceptAction.EXEC_BASH:
            cmd = (result.bash_command or "").strip()
            if cmd:
                self._engine.write(cmd.encode() + b"\n")
                set_pty_running(True)
            return

        if result.action == InterceptAction.TOGGLE:
            from src.application.usecases.terminal_session import SessionMode
            if mode == SessionMode.NL:
                set_mode(SessionMode.BASH)
                label = b"Bash Mode ativo"
            else:
                set_mode(SessionMode.NL)
                label = b"NL Mode ativo"
            indicator = b"\r\n\033[33m[forge_shell: " + label + b"]\033[0m\r\n"
            if out:
                out.write(indicator)
                out.flush()
            set_pty_running(True)
            self._engine.write(b"\r")
            return

        if result.action == InterceptAction.HELP:
            self._render_help(out)
            return

        if result.action == InterceptAction.RISK:
            self._render_risk(out, result)
            return

        if result.action == InterceptAction.EXPLAIN:
            self._render_explain(out, result)
            return

        if result.action == InterceptAction.SHOW_SUGGESTION:
            self._render_suggestion(out, result)
            return

    def handle_agent_suggest(self, payload: dict) -> None:
        """Renderiza sugestão recebida de um agent remoto."""
        out = self._out
        if out is None:
            return

        commands = payload.get("commands", [])
        explanation = payload.get("explanation", "")
        risk_level = payload.get("risk_level", "LOW").upper()

        risk_color = self._risk_color(risk_level)
        cmd_str = " && ".join(commands) if commands else ""

        lines = [b"\r\n"]
        lines.append(b"\033[1;35m[Agent]\033[0m ")
        if cmd_str:
            lines.append(cmd_str.encode() + b"\r\n")
        if explanation:
            lines.append(b"   " + explanation.encode() + b"\r\n")
        lines.append(b"   Risco: " + risk_color + risk_level.encode() + b"\033[0m\r\n")

        if risk_level in ("LOW", "MEDIUM"):
            lines.append(b"\033[2m   Enter para executar  \xc2\xb7  Ctrl-C para cancelar\033[0m\r\n")
        else:
            lines.append(b"\033[1;31m   [!] Risco ALTO \xe2\x80\x94 digite o comando manualmente.\033[0m\r\n")

        lines.append(b"\r\n")

        for line in lines:
            out.write(line)
        out.flush()

        if risk_level in ("LOW", "MEDIUM") and cmd_str:
            self._engine.write(cmd_str.encode())

    def write_startup_hint(self, mode) -> None:
        """Exibir hint de NL Mode na abertura da sessão."""
        from src.application.usecases.terminal_session import SessionMode
        if mode == SessionMode.PASSTHROUGH:
            return
        out = self._out
        if out is None:
            return
        hint = (
            b"\033[36mforge_shell\033[0m"
            b"  |  \033[1mNL Mode\033[0m"
            b"  |  \033[33m!\033[0m para bash"
            b"  |  \033[33m!<cmd>\033[0m bash direto"
            b"  |  \033[33m:explain <cmd>\033[0m analisar"
            b"  |  \033[33m:risk <cmd>\033[0m risco"
            b"  |  \033[33m:help\033[0m ajuda"
            b"\r\n"
        )
        out.write(hint)

    # ------------------------------------------------------------------
    # Private rendering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_color(level: str) -> bytes:
        if level == "LOW":
            return b"\033[1;32m"   # verde
        elif level == "MEDIUM":
            return b"\033[1;33m"   # amarelo
        return b"\033[1;31m"       # vermelho

    def _render_help(self, out) -> None:
        lines = [
            b"\r\n",
            b"\033[1;36mforge_shell\033[0m \xe2\x80\x94 comandos dispon\xc3\xadveis\r\n",
            b"\r\n",
            b"  \033[33m!\033[0m              alternar NL Mode \xe2\x86\x94 Bash Mode\r\n",
            b"  \033[33m!<cmd>\033[0m         executar bash direto (ex: \033[2m!ls -la\033[0m)\r\n",
            b"  \033[33m:explain <cmd>\033[0m analisar comando sem executar\r\n",
            b"  \033[33m:risk <cmd>\033[0m    classificar risco de um comando\r\n",
            b"  \033[33m:help\033[0m          exibir esta ajuda\r\n",
            b"\r\n",
            b"  \033[2mNL Mode:\033[0m descreva em portugu\xc3\xaas \xe2\x86\x92 forge_shell gera o comando\r\n",
            b"  \033[2mCtrl-C:\033[0m cancela consulta LLM em andamento\r\n",
            b"\r\n",
        ]
        if out:
            for line in lines:
                out.write(line)
            out.flush()

    def _render_risk(self, out, result) -> None:
        level = result.risk_level
        level_str = level.value if level is not None else "unknown"
        color = self._risk_color(level_str.upper())
        if out:
            out.write(b"\r\n  Risco: " + color + level_str.upper().encode() + b"\033[0m\r\n\r\n")
            out.flush()

    def _render_explain(self, out, result) -> None:
        suggestion = result.suggestion
        if suggestion is None:
            return
        explanation = getattr(suggestion, "explanation", "") or ""
        commands = getattr(suggestion, "commands", []) or []
        risk = getattr(suggestion, "risk_level", None)
        risk_str = risk.value if hasattr(risk, "value") else str(risk)
        lines = [b"\r\n"]
        if commands:
            cmd_str = " && ".join(commands)
            lines.append(b"\033[1;34m[?] " + cmd_str.encode() + b"\033[0m\r\n")
        if explanation:
            lines.append(b"   " + explanation.encode() + b"\r\n")
        lines.append(b"   Risco: " + risk_str.encode() + b"\r\n\r\n")
        if out:
            for line in lines:
                out.write(line)
            out.flush()

    def _render_suggestion(self, out, result) -> None:
        suggestion = result.suggestion
        if suggestion is None:
            return
        commands = getattr(suggestion, "commands", []) or []
        explanation = getattr(suggestion, "explanation", "") or ""
        risk = getattr(suggestion, "risk_level", None)
        risk_str = risk.value if hasattr(risk, "value") else str(risk)

        requires_confirm = getattr(result, "requires_double_confirm", False)

        cmd_str = " && ".join(commands) if commands else ""
        lines = [b"\r\n"]
        if cmd_str:
            lines.append(b"\033[1;32m[*] " + cmd_str.encode() + b"\033[0m\r\n")
        if explanation:
            lines.append(b"   " + explanation.encode() + b"\r\n")
        lines.append(b"   Risco: " + risk_str.encode() + b"\r\n")

        if requires_confirm:
            lines.append(b"\r\n")
            lines.append(b"\033[1;31m[!] Risco ALTO \xe2\x80\x94 confirme digitando o comando manualmente.\033[0m\r\n")
            lines.append(b"\r\n")
        else:
            lines.append(b"\033[2m   Enter para executar  \xc2\xb7  Ctrl-C para cancelar\033[0m\r\n")
            lines.append(b"\r\n")

        if out:
            for line in lines:
                out.write(line)
            out.flush()

        if not requires_confirm and cmd_str:
            self._engine.write(cmd_str.encode())
