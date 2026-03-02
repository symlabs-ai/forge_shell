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

# Log de timing para diagnóstico — arquivo por PID em /tmp/
import logging
import tempfile
_tlog = logging.getLogger("forge_shell.timing")
_tlog.setLevel(logging.DEBUG)
_tlog.propagate = False  # não vaza para o root logger (evita eco no PTY)
_log_path = os.path.join(tempfile.gettempdir(), f"forge_shell_timing_{os.getpid()}.log")
_th = logging.FileHandler(_log_path, mode="w")
_th.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S"))
_tlog.addHandler(_th)

import fcntl
import struct

from src.infrastructure.config.loader import ForgeShellConfig
from src.infrastructure.terminal_engine.pty_engine import PTYEngine
from src.infrastructure.terminal_engine.alternate_screen import AlternateScreenDetector
from src.application.usecases.intercept_types import InterceptAction

from src.infrastructure.terminal_engine.input_router import InputFocus
from src.application.usecases.output_renderer import OutputRenderer
from src.application.usecases.chat_manager import ChatManager


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
        *,
        interceptor=None,
        auditor=None,
        redactor=None,
        relay_bridge=None,
        chat_agent=None,
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
        self._interceptor = interceptor
        self._auditor = auditor
        self._relay_bridge = relay_bridge
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
        self._redactor = redactor
        self._chat_agent = chat_agent  # ChatAgentWorker | None
        # Chat panel (Phase 3) — delegado ao ChatManager
        self._chat = ChatManager(self._engine, self._get_terminal_size)
        self._renderer = OutputRenderer(self._engine)

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
    # Chat panel management (delegado ao ChatManager)
    # ------------------------------------------------------------------

    def _get_terminal_size(self) -> tuple[int, int]:
        """Get current terminal rows, cols."""
        try:
            buf = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
            rows, cols = struct.unpack("HHHH", buf)[:2]
            return (rows, cols)
        except Exception:
            return (24, 80)

    def _sync_chat(self) -> None:
        """Sync ChatManager references (needed when tests replace fields)."""
        self._chat._stdout = self._stdout
        self._chat._engine = self._engine
        self._chat._get_terminal_size = self._get_terminal_size

    def _activate_chat_panel(self) -> None:
        self._sync_chat()
        self._chat.activate()

    def _deactivate_chat_panel(self) -> None:
        self._sync_chat()
        self._chat.deactivate()

    def _handle_chat_message(self, payload: dict) -> None:
        self._sync_chat()
        self._chat.handle_message(payload)
        # Route to chat agent if available
        if self._chat_agent is not None:
            sender = payload.get("sender", "?")
            text = payload.get("text", "")
            if sender != "agent" and text.strip():
                self._chat_agent.submit(sender, text)

    def _send_chat_message(self, text: str) -> None:
        self._sync_chat()
        self._chat.send_message(text, relay_bridge=self._relay_bridge)

    def _handle_chat_agent_result(self, result) -> None:
        """Process result from ChatAgentWorker and send as agent chat message."""
        if result.response is None:
            return
        text = result.response.explanation
        if result.response.commands:
            cmds = "\n".join(f"$ {c}" for c in result.response.commands)
            text = f"{text}\n\n{cmds}"
        self._send_chat_agent_message(text)
        # Optionally render as agent suggestion in terminal
        if result.response.commands:
            self._handle_agent_suggest({
                "commands": result.response.commands,
                "explanation": result.response.explanation,
                "risk_level": result.response.risk_level.value,
            })

    def _send_chat_agent_message(self, text: str) -> None:
        """Send a message as role 'agent' to chat panel and relay."""
        self._sync_chat()
        if self._chat.chat_panel is not None:
            self._chat.chat_panel.add_message("agent", text, "agent")
        if self._relay_bridge is not None:
            self._relay_bridge.send_chat(text, sender="agent")
        if self._chat.split_renderer:
            self._chat.split_renderer.render()

    # Compatibility properties — delegate to ChatManager fields
    @property
    def _chat_active(self) -> bool:
        return self._chat.active

    @_chat_active.setter
    def _chat_active(self, value: bool) -> None:
        self._chat.active = value

    @property
    def _vt_screen(self):
        return self._chat.vt_screen

    @property
    def _chat_panel(self):
        return self._chat.chat_panel

    @property
    def _split_renderer(self):
        return self._chat.split_renderer

    @property
    def _input_router(self):
        return self._chat.input_router

    @property
    def _alt_screen_was_active(self) -> bool:
        return self._chat.alt_screen_was_active

    @_alt_screen_was_active.setter
    def _alt_screen_was_active(self, value: bool) -> None:
        self._chat.alt_screen_was_active = value

    # ------------------------------------------------------------------
    # I/O routing (testável sem I/O real)
    # ------------------------------------------------------------------

    def _route_input(self, data: bytes) -> None:
        """Rotear bytes de input: PTY direto (passthrough/alternate) ou interceptor."""
        # Ctrl+X encerra sessão de share (apenas quando relay ativo)
        if data == b"\x18" and self._relay_bridge is not None:
            self._engine.close()
            return

        if self._mode == SessionMode.PASSTHROUGH:
            self._engine.write(data)
            return

        if self._detector.is_active:
            # app full-screen (vim, top, etc.) — input vai direto para PTY
            self._engine.write(data)
            return

        # Chat split active: route through InputRouter
        if self._chat_active and self._input_router:
            for target, chunk in self._input_router.feed(data):
                if target == "toggle":
                    self._input_router.toggle_focus()
                    self._split_renderer.set_focus(self._input_router.focus.value)
                    self._split_renderer.render(force=True)
                elif target == "terminal":
                    self._route_input_to_pty(chunk)
                elif target == "chat":
                    msg = self._chat_panel.handle_key(chunk)
                    if msg is not None:
                        self._send_chat_message(msg)
                    if self._split_renderer:
                        self._split_renderer.render()
            return

        self._route_input_to_pty(data)

    def _route_input_to_pty(self, data: bytes) -> None:
        """Route input to PTY (original _route_input logic without chat split)."""
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

    def _sync_renderer(self) -> None:
        """Sync renderer references (needed when tests replace _engine/_stdout)."""
        self._renderer._stdout = self._stdout
        self._renderer._engine = self._engine

    def _handle_intercept_result(self, result) -> None:
        """Processar resultado do NLInterceptor (delega ao OutputRenderer)."""
        self._sync_renderer()
        self._renderer.handle_intercept_result(
            result,
            mode=self._mode,
            set_mode=self._set_mode,
            set_pty_running=self._set_pty_running,
        )

    def _set_mode(self, new_mode: SessionMode) -> None:
        self._mode = new_mode

    def _set_pty_running(self, value: bool) -> None:
        self._pty_running = value

    def _handle_agent_suggest(self, payload: dict) -> None:
        """Renderiza sugestão recebida de um agent remoto (delega ao OutputRenderer)."""
        self._sync_renderer()
        self._renderer.handle_agent_suggest(payload)

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
        """Exibir hint de NL Mode na abertura da sessão (delega ao OutputRenderer)."""
        self._sync_renderer()
        self._renderer.write_startup_hint(self._mode)

    _PROMPT_PATTERN = re.compile(rb'[\$#%]\s*$')
    # Detecta prompts de senha do sudo/ssh/su/doas
    # Ex: "[sudo] senha para palhano: ", "Password: ", "Enter passphrase for key '...': "
    _PASSWORD_PROMPT = re.compile(
        rb'(password|senha|passphrase|passcode|pass\s*phrase)[^\n]*:\s*$',
        re.IGNORECASE,
    )

    def _handle_pty_output(self, data: bytes) -> None:
        """Processar output do PTY: detectar alternate screen, auditar, relay e escrever em stdout."""
        prev_alt = self._detector.is_active
        self._detector.feed(data)
        curr_alt = self._detector.is_active

        # Handle alternate screen transitions when chat is active
        if self._chat_active:
            self._sync_chat()
            if not prev_alt and curr_alt:
                self._chat.handle_enter_alt_screen()
            elif prev_alt and not curr_alt and self._alt_screen_was_active:
                self._chat.handle_exit_alt_screen()

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
            out = self._stdout or getattr(sys.stdout, "buffer", None)
            if self._chat_active and not self._alt_screen_was_active and self._vt_screen:
                self._vt_screen.feed(data)
                if self._split_renderer:
                    self._split_renderer.render()
            elif out is not None:
                out.write(data)
            return

        # Write output: through VTScreen (split) or direct to stdout
        if self._chat_active and not self._alt_screen_was_active and self._vt_screen:
            self._vt_screen.feed(data)
            if self._split_renderer:
                self._split_renderer.render()
        else:
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
        """Instalar handler SIGWINCH que repassa resize ao PTY (e chat panel se ativo)."""
        def _handler(signum: int, frame: object) -> None:
            try:
                rows, cols = self._get_terminal_size()
                if self._chat_active:
                    self._sync_chat()
                    self._chat.handle_resize(rows, cols)
                else:
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

                # Drena sugestões do agent via relay
                if self._relay_bridge is not None:
                    suggestion = self._relay_bridge.get_suggest()
                    if suggestion is not None:
                        self._handle_agent_suggest(suggestion)

                # Drena mensagens de chat via relay
                if self._relay_bridge is not None:
                    chat = self._relay_bridge.get_chat()
                    if chat is not None:
                        self._handle_chat_message(chat)

                # Poll chat agent results
                if self._chat_agent is not None:
                    agent_result = self._chat_agent.poll()
                    if agent_result is not None:
                        self._handle_chat_agent_result(agent_result)

                # Drena input remoto de viewer/agent via relay
                if self._relay_bridge is not None:
                    remote_input = self._relay_bridge.get_input()
                    if remote_input:
                        self._engine.write(remote_input)

                # Auto-ativar chat quando primeiro participante conecta
                # (detectado pelo recebimento de chat ou suggest)
                # NÃO ativar imediatamente — preserva session info na tela

                # Flush escape buffer on timeout (no stdin data this iteration)
                if self._input_router and stdin_fd not in rfds:
                    for target, chunk in self._input_router.flush_esc_buffer():
                        if target == "terminal":
                            self._route_input_to_pty(chunk)
                        elif target == "chat" and self._chat_panel:
                            msg = self._chat_panel.handle_key(chunk)
                            if msg is not None:
                                self._send_chat_message(msg)
                            if self._split_renderer:
                                self._split_renderer.render()
        finally:
            if self._chat_active:
                self._deactivate_chat_panel()
            self._engine.restore_stdin()
            self._engine.close()

        return 0
