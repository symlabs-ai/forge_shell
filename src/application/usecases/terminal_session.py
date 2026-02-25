"""
TerminalSession — C2-T-03 + C2-T-09.

Loop principal do sym_shell: une PTYEngine, NLInterceptor, AlternateScreenDetector
e AuditLogger em uma sessão interativa completa.

Modos:
- SessionMode.NL        — NL Mode ativo (padrão da config)
- SessionMode.BASH      — Bash Mode (NL desativado via config ou toggle)
- SessionMode.PASSTHROUGH — PTY puro sem qualquer interceptação
"""
from __future__ import annotations

import os
import select
import signal
import sys
from enum import Enum

from src.infrastructure.config.loader import SymShellConfig
from src.infrastructure.terminal_engine.pty_engine import PTYEngine
from src.infrastructure.terminal_engine.alternate_screen import AlternateScreenDetector


class SessionMode(str, Enum):
    NL = "nl"
    BASH = "bash"
    PASSTHROUGH = "passthrough"


class TerminalSession:
    """
    Sessão interativa do sym_shell.

    Parâmetros:
        config: configuração carregada do ~/.sym_shell/config.yaml
        passthrough: se True, liga PTY puro sem NL/collab/audit
    """

    def __init__(
        self,
        config: SymShellConfig,
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

        if self._interceptor is not None:
            self._interceptor.intercept(data)
            return

        # fallback: sem interceptor configurado, vai direto para PTY
        self._engine.write(data)

    def _handle_pty_output(self, data: bytes) -> None:
        """Processar output do PTY: detectar alternate screen, auditar, relay e escrever em stdout."""
        self._detector.feed(data)
        out = self._stdout or getattr(sys.stdout, "buffer", None)
        if out is not None:
            out.write(data)
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
        finally:
            self._engine.restore_stdin()
            self._engine.close()

        return 0
