"""
TerminalSession — C2-T-03 + C2-T-09.

Loop principal do forge_shell: une PTYEngine, NLInterceptor, AlternateScreenDetector
e AuditLogger em uma sessão interativa completa.

Modos:
- SessionMode.NL        — NL Mode ativo (padrão da config)
- SessionMode.BASH      — Bash Mode (NL desativado via config ou toggle)
- SessionMode.PASSTHROUGH — PTY puro sem qualquer interceptação
"""
from __future__ import annotations

import os
import queue
import re
import select
import signal
import sys
import termios
import threading
import time
from collections import deque
from enum import Enum

# Log de timing para diagnóstico — escreve em /tmp/forge_shell_timing.log
import logging
_tlog = logging.getLogger("forge_shell.timing")
_tlog.setLevel(logging.DEBUG)
_tlog.propagate = False  # não vaza para o root logger (evita eco no PTY)
_th = logging.FileHandler("/tmp/forge_shell_timing.log", mode="w")
_th.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S"))
_tlog.addHandler(_th)

from src.infrastructure.config.loader import ForgeShellConfig
from src.infrastructure.terminal_engine.pty_engine import PTYEngine
from src.infrastructure.terminal_engine.alternate_screen import AlternateScreenDetector
from src.application.usecases.nl_interceptor import InterceptAction


class SessionMode(str, Enum):
    NL = "nl"
    BASH = "bash"
    PASSTHROUGH = "passthrough"


class TerminalSession:
    """
    Sessão interativa do forge_shell.

    Parâmetros:
        config: configuração carregada do ~/.forge_shell/config.yaml
        passthrough: se True, liga PTY puro sem NL/collab/audit
    """

    def __init__(
        self,
        config: ForgeShellConfig,
        passthrough: bool = False,
    ) -> None:
        self.config = config

        if passthrough:
            self._mode = SessionMode.PASSTHROUGH
        elif config.nl_mode.default_active:
            self._mode = SessionMode.NL
        else:
            self._mode = SessionMode.BASH

        self._engine = PTYEngine()
        self._detector = AlternateScreenDetector()
        self._interceptor = None    # injetado após construção (lazy / DI)
        self._auditor = None        # injetado via DI; None = sem auditoria
        self._relay_bridge = None   # injetado via DI; None = sem relay streaming
        self._stdout = None         # injetado para testes; padrão: sys.stdout.buffer
        self._nl_buffer: bytes = b""  # buffer de linha no NL Mode
        self._llm_queue: queue.Queue = queue.Queue()  # resultados assíncronos do LLM
        self._llm_pending: bool = False  # evita chamadas simultâneas
        self._llm_cancel: threading.Event = threading.Event()  # sinaliza cancelamento ao LLM thread
        self._pty_running: bool = False  # True enquanto comando está em execução no PTY
        self._in_password_entry: bool = False  # True após prompt de senha detectado
        # contexto LLM: últimas N linhas de output e cwd
        self._output_lines: deque = deque(maxlen=config.nl_mode.context_lines)
        self._output_partial: str = ""
        self._redactor = None  # injetado via DI; None = sem redaction

    def _flush_pending_llm(self, timeout: float = 0.5) -> None:
        """Drena resultado pendente do LLM. Usado em testes (sem select loop)."""
        try:
            result = self._llm_queue.get(timeout=timeout)
            self._llm_pending = False
            self._handle_intercept_result(result)
        except queue.Empty:
            pass

    @property
    def mode(self) -> SessionMode:
        return self._mode

    # ------------------------------------------------------------------
    # I/O routing (testável sem I/O real)
    # ------------------------------------------------------------------

    def _route_input(self, data: bytes) -> None:
        """Rotear bytes de input: PTY direto (passthrough/alternate) ou interceptor."""
        if self._mode == SessionMode.PASSTHROUGH:
            self._engine.write(data)
            return

        if self._detector.is_active:
            # app full-screen (vim, top, etc.) — input vai direto para PTY
            self._engine.write(data)
            return

        # comando em execução: todo input vai direto para PTY (senha, confirmações, etc.)
        if self._pty_running:
            self._engine.write(data)
            return

        if self._interceptor is not None:
            self._buffer_nl_input(data)
            return

        # fallback: sem interceptor configurado, vai direto para PTY
        self._engine.write(data)

    def _buffer_nl_input(self, data: bytes) -> None:
        """Acumula input no NL Mode; só chama LLM quando Enter é pressionado."""
        out = self._stdout or getattr(sys.stdout, "buffer", None)

        # Backspace / DEL — remove último byte do buffer e apaga char na tela
        if data in (b'\x7f', b'\x08'):
            if self._nl_buffer:
                self._nl_buffer = self._nl_buffer[:-1]
                if out:
                    out.write(b'\x08 \x08')
                    out.flush()
            return

        # Ctrl-C — cancela LLM pendente ou interrompe bash
        if data == b'\x03':
            if self._llm_pending:
                # sinaliza cancelamento para a thread LLM e restaura estado
                self._llm_cancel.set()
                self._llm_pending = False
                try:
                    self._llm_queue.get_nowait()
                except queue.Empty:
                    pass
                if out:
                    out.write(b']\033[0m\r\n\033[33m[forge_shell: cancelado]\033[0m\r\n')
                    out.flush()
            else:
                self._nl_buffer = b""
                self._engine.write(data)
            return

        # Enter (\r ou \n) — acumula prefixo antes do newline, dispara LLM em thread
        if b'\r' in data or b'\n' in data:
            t0 = time.monotonic()
            idx_r = data.find(b'\r') if b'\r' in data else len(data)
            idx_n = data.find(b'\n') if b'\n' in data else len(data)
            pre = data[:min(idx_r, idx_n)]
            if pre:
                self._nl_buffer += pre
            full = self._nl_buffer
            self._nl_buffer = b""
            _tlog.debug("ENTER received | full=%r | mode=%s | pty_running=%s | llm_pending=%s",
                        full, self._mode, self._pty_running, self._llm_pending)
            if out:
                out.write(b'\r\n')
                out.flush()
            if full.strip() and not self._llm_pending:
                stripped = full.strip().decode("utf-8", errors="replace")
                is_toggle    = stripped == "!"
                is_escape    = stripped.startswith("!") and len(stripped) > 1
                is_bash_mode = self._mode == SessionMode.BASH
                is_explain   = stripped.lower().startswith(":explain ") and len(stripped) > 9
                is_help      = stripped.lower() == ":help"
                is_risk      = stripped.lower().startswith(":risk ") and len(stripped) > 6
                _tlog.debug("  path: toggle=%s escape=%s bash_mode=%s explain=%s help=%s risk=%s | stripped=%r",
                            is_toggle, is_escape, is_bash_mode, is_explain, is_help, is_risk, stripped)
                if is_toggle or is_escape or is_help or is_risk or (is_bash_mode and not is_explain):
                    t1 = time.monotonic()
                    result = self._interceptor.intercept(full)
                    t2 = time.monotonic()
                    _tlog.debug("  intercept() took %.3fs → action=%s", t2 - t1,
                                result.action if result else None)
                    self._handle_intercept_result(result)
                    _tlog.debug("  handle_intercept_result() done, total=%.3fs", time.monotonic() - t0)
                else:
                    self._llm_pending = True
                    self._llm_cancel.clear()  # reset antes de cada dispatch
                    _tlog.debug("  dispatching LLM thread for NL query")
                    if self._interceptor is not None:
                        self._interceptor.set_context(self._build_context())
                    if out:
                        out.write(b'\033[36m[forge_shell: pensando')
                        out.flush()
                    interceptor = self._interceptor
                    llm_q = self._llm_queue
                    _out = out  # captura para closure da thread
                    _cancel = self._llm_cancel  # captura event de cancelamento

                    def _on_chunk(chunk_text: str) -> None:
                        if _cancel.is_set():
                            raise KeyboardInterrupt  # interrompe stream_chat()
                        if _out:
                            _out.write(b'.')
                            _out.flush()

                    def _llm_thread(text: bytes) -> None:
                        t_start = time.monotonic()
                        try:
                            res = interceptor.intercept(text, on_chunk=_on_chunk)
                        except Exception as e:
                            _tlog.debug("  LLM thread exception: %s", e)
                            res = None
                        if _cancel.is_set():
                            # Ctrl-C já escreveu o fechamento e resetou o estado
                            return
                        if _out:
                            _out.write(b']\033[0m\r\n')
                            _out.flush()
                        _tlog.debug("  LLM thread done in %.3fs", time.monotonic() - t_start)
                        llm_q.put(res)
                    threading.Thread(target=_llm_thread, args=(full,), daemon=True).start()
            else:
                _tlog.debug("  empty buffer Enter → passthrough to PTY")
                self._pty_running = True
                self._engine.write(b'\r')
            return

        # Caractere normal — acumula e faz echo local (não vai ao PTY)
        self._nl_buffer += data
        if out:
            out.write(data)
            out.flush()

    def _handle_intercept_result(self, result) -> None:
        """Processar resultado do NLInterceptor: executar comando, exibir sugestão ou indicador."""
        if result is None:
            return
        out = self._stdout or getattr(sys.stdout, "buffer", None)

        if result.action == InterceptAction.NOOP:
            return

        if result.action == InterceptAction.EXEC_BASH:
            cmd = (result.bash_command or "").strip()
            if cmd:
                self._engine.write(cmd.encode() + b"\n")
                # comando está rodando — input direto ao PTY (ex: senha de sudo)
                self._pty_running = True
            return

        if result.action == InterceptAction.TOGGLE:
            # alternar _mode e exibir indicador do novo estado
            if self._mode == SessionMode.NL:
                self._mode = SessionMode.BASH
                label = b"Bash Mode ativo"
            else:
                self._mode = SessionMode.NL
                label = b"NL Mode ativo"
            indicator = b"\r\n\033[33m[forge_shell: " + label + b"]\033[0m\r\n"
            if out:
                out.write(indicator)
                out.flush()
            # Envia \r ao PTY para forçar novo prompt do bash (sem isso o usuário
            # fica aguardando o prompt que nunca aparece automaticamente)
            self._pty_running = True
            self._engine.write(b"\r")
            return

        if result.action == InterceptAction.HELP:
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
            return

        if result.action == InterceptAction.RISK:
            level = result.risk_level
            level_str = level.value if level is not None else "unknown"
            if level_str == "low":
                color = b"\033[1;32m"   # verde
            elif level_str == "medium":
                color = b"\033[1;33m"   # amarelo
            else:
                color = b"\033[1;31m"   # vermelho
            if out:
                out.write(b"\r\n  Risco: " + color + level_str.upper().encode() + b"\033[0m\r\n\r\n")
                out.flush()
            return

        if result.action == InterceptAction.EXPLAIN:
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
            return

        if result.action == InterceptAction.SHOW_SUGGESTION:
            suggestion = result.suggestion
            if suggestion is None:
                return
            commands = getattr(suggestion, "commands", []) or []
            explanation = getattr(suggestion, "explanation", "") or ""
            risk = getattr(suggestion, "risk_level", None)
            risk_str = risk.value if hasattr(risk, "value") else str(risk)

            requires_confirm = getattr(result, "requires_double_confirm", False)

            # formatar sugestão para o terminal (todos os comandos, join com &&)
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
                # risco baixo/médio: injeta no PTY para o usuário revisar e pressionar Enter
                self._engine.write(cmd_str.encode())
            return

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _get_cwd(self) -> str:
        """Retorna o cwd atual do processo bash no PTY via /proc/<pid>/cwd."""
        try:
            pid = self._engine.pid
            if pid is None:
                return ""
            return os.readlink(f"/proc/{pid}/cwd")
        except (OSError, AttributeError):
            return ""

    def _accumulate_output_lines(self, data: bytes) -> None:
        """Acumula linhas de output do PTY para contexto LLM (strips ANSI)."""
        text = self._output_partial + data.decode("utf-8", errors="replace")
        clean = re.sub(r"\x1b\[[0-9;]*[mKHJA-Za-z]", "", text)
        lines = clean.split("\n")
        self._output_partial = lines[-1]  # último fragmento (pode ser incompleto)
        for line in lines[:-1]:
            stripped = line.strip()
            if stripped:
                self._output_lines.append(stripped)

    def _build_context(self) -> dict:
        """Constrói dict de contexto {cwd, last_lines} para o LLM."""
        cwd = self._get_cwd()
        last_lines = "\n".join(self._output_lines)
        if self._redactor is not None:
            last_lines = self._redactor.redact(last_lines)
        ctx: dict = {}
        if cwd:
            ctx["cwd"] = cwd
        if last_lines:
            ctx["last_lines"] = last_lines
        return ctx

    def _write_startup_hint(self) -> None:
        """Exibir hint de NL Mode na abertura da sessão (apenas modo NL/BASH)."""
        if self._mode == SessionMode.PASSTHROUGH:
            return
        out = self._stdout or getattr(sys.stdout, "buffer", None)
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

    _PROMPT_PATTERN = re.compile(rb'[\$#%]\s*$')
    # Detecta prompts de senha do sudo/ssh/su/doas
    # Ex: "[sudo] senha para palhano: ", "Password: ", "Enter passphrase for key '...': "
    _PASSWORD_PROMPT = re.compile(
        rb'(password|senha|passphrase|passcode|pass\s*phrase)[^\n]*:\s*$',
        re.IGNORECASE,
    )

    def _handle_pty_output(self, data: bytes) -> None:
        """Processar output do PTY: detectar alternate screen, auditar, relay e escrever em stdout."""
        self._detector.feed(data)
        # Detecta prompt bash/zsh/fish no output → comando terminou, volta ao NL buffer
        if self._pty_running:
            stripped = re.sub(rb'\x1b\[[0-9;]*[mKHJA-Za-z]', b'', data)
            if self._PROMPT_PATTERN.search(stripped):
                self._pty_running = False

        # Suprimir echo de senha: após detectar prompt de senha (sudo/ssh/su),
        # suprimir todo output do PTY até que uma nova linha seja recebida.
        if self._in_password_entry:
            if b'\n' in data or b'\r' in data:
                self._in_password_entry = False
            # suprimir o echo dos caracteres da senha
            return

        # Detectar prompt de senha pelo padrão (ex: "[sudo] senha:", "Password:")
        stripped_for_pwd = re.sub(rb'\x1b\[[0-9;]*[mKHJA-Za-z]', b'', data)
        if self._PASSWORD_PROMPT.search(stripped_for_pwd):
            self._in_password_entry = True
            # exibir o próprio prompt mas suprimir o que vier depois dele neste chunk
            prompt_match = self._PASSWORD_PROMPT.search(stripped_for_pwd)
            # exibir até o fim do match no chunk (inclui o prompt + espaço final)
            # para segurança exibimos tudo até aqui e suprimimos leituras seguintes
            out = self._stdout or getattr(sys.stdout, "buffer", None)
            if out is not None:
                out.write(data)
            return

        out = self._stdout or getattr(sys.stdout, "buffer", None)
        if out is not None:
            out.write(data)
        self._accumulate_output_lines(data)
        if self._relay_bridge is not None:
            try:
                self._relay_bridge.send(data)
            except Exception:
                pass
        if self._auditor is not None and b"\n" in data:
            line = data.decode("utf-8", errors="replace").strip()
            try:
                self._auditor.log_command(command=line, origin="pty", exit_code=0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # SIGWINCH
    # ------------------------------------------------------------------

    def _install_sigwinch_handler(self) -> None:
        """Instalar handler SIGWINCH que repassa resize ao PTY."""
        def _handler(signum: int, frame: object) -> None:
            try:
                import fcntl
                import struct
                import termios
                buf = b"\x00" * 8
                buf = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, buf)
                rows, cols = struct.unpack("HHHH", buf)[:2]
                self._engine.resize(rows=rows, cols=cols)
            except Exception:
                pass

        signal.signal(signal.SIGWINCH, _handler)

    # ------------------------------------------------------------------
    # run — I/O loop completo
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        Iniciar a sessão interativa.

        Faz spawn do PTY, entra em raw mode e inicia o I/O loop.
        Retorna exit code quando a sessão termina.
        """
        self._engine.spawn()
        self._install_sigwinch_handler()

        if self._stdout is None:
            self._stdout = getattr(sys.stdout, "buffer", None)

        stdin_fd = sys.stdin.fileno()
        self._engine.set_raw_stdin()

        try:
            while self._engine.is_alive:
                try:
                    rfds, _, _ = select.select(
                        [stdin_fd, self._engine.master_fd], [], [], 0.05
                    )
                except (select.error, ValueError):
                    break

                if stdin_fd in rfds:
                    chunk = os.read(stdin_fd, 1024)
                    if chunk:
                        self._route_input(chunk)

                if self._engine.master_fd in rfds:
                    try:
                        chunk = os.read(self._engine.master_fd, 4096)
                        if chunk:
                            self._handle_pty_output(chunk)
                            if self._stdout:
                                self._stdout.flush()
                    except OSError:
                        break

                # Drena resultado do LLM (thread assíncrona)
                if self._llm_pending:
                    try:
                        result = self._llm_queue.get_nowait()
                        self._llm_pending = False
                        self._handle_intercept_result(result)
                    except queue.Empty:
                        pass
        finally:
            self._engine.restore_stdin()
            self._engine.close()

        return 0
