"""
PTYEngine — engine de terminal baseado em PTY real (Unix).

Spawna /bin/bash em um PTY master/slave, garantindo compatibilidade completa
com aplicações interativas (sudo, vim, top, ssh, job control).

Responsabilidades:
- Criar PTY master/slave
- Spawnar bash em modo interativo
- Expor interface de leitura/escrita de bytes
- Enviar resize (SIGWINCH) ao processo filho
- Restaurar termios do terminal host ao fechar
"""
from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import termios
import tty
import sys
import time


class PTYEngine:
    """
    Controla um processo bash em PTY real.

    Uso:
        engine = PTYEngine()
        engine.spawn()
        engine.write(b"ls -la\\n")
        data = engine.read_available()
        engine.close()
    """

    def __init__(self) -> None:
        self._master_fd: int | None = None
        self._pid: int | None = None
        self._saved_termios: list | None = None
        self._buffer: bytes = b""

    def spawn(self, shell: str = "/bin/bash") -> None:
        """Spawnar bash em PTY. Deve ser chamado uma vez."""
        self._pid, self._master_fd = pty.fork()

        if self._pid == 0:
            # processo filho — executa o shell
            os.execvp(shell, [shell, "-i"])
            # nunca chega aqui
            os._exit(1)

        # processo pai — configura o master PTY
        # definir tamanho inicial padrão
        self._set_winsize(self._master_fd, rows=24, cols=80)

    def write(self, data: bytes) -> None:
        """Escrever bytes no PTY (input para o bash)."""
        if self._master_fd is None:
            raise RuntimeError("PTYEngine: spawn() não foi chamado")
        os.write(self._master_fd, data)

    def read_available(self, timeout: float = 0.1) -> bytes:
        """Ler todos os bytes disponíveis no PTY com timeout."""
        if self._master_fd is None:
            return b""
        result = b""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                rlist, _, _ = select.select([self._master_fd], [], [], min(0.02, remaining))
            except (select.error, ValueError):
                break
            if not rlist:
                continue  # sem dados agora, mas ainda há tempo — continuar polling
            try:
                chunk = os.read(self._master_fd, 4096)
                if not chunk:
                    break
                result += chunk
            except OSError:
                break
        return result

    def resize(self, rows: int, cols: int) -> None:
        """Atualizar tamanho do PTY e enviar SIGWINCH ao processo filho."""
        if self._master_fd is None:
            return
        self._set_winsize(self._master_fd, rows=rows, cols=cols)
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGWINCH)
            except ProcessLookupError:
                pass

    def close(self) -> None:
        """Encerrar o processo filho e fechar o master PTY."""
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self._pid, os.WNOHANG)
            except ChildProcessError:
                pass
            self._pid = None

        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

    def set_raw_stdin(self) -> None:
        """Colocar stdin em raw mode (para sessão interativa completa)."""
        fd = sys.stdin.fileno()
        try:
            self._saved_termios = termios.tcgetattr(fd)
            tty.setraw(fd)
        except termios.error:
            self._saved_termios = None

    def restore_stdin(self) -> None:
        """Restaurar stdin ao estado original (deve sempre ser chamado no exit)."""
        if self._saved_termios is not None:
            try:
                termios.tcsetattr(
                    sys.stdin.fileno(),
                    termios.TCSADRAIN,
                    self._saved_termios,
                )
            except termios.error:
                pass
            self._saved_termios = None

    @property
    def is_alive(self) -> bool:
        """True se o processo filho ainda está em execução."""
        if self._pid is None:
            return False
        try:
            pid, status = os.waitpid(self._pid, os.WNOHANG)
            if pid == self._pid:
                self._pid = None
                return False
            return True
        except ChildProcessError:
            return False

    @property
    def master_fd(self) -> int | None:
        """File descriptor do PTY master (para uso no I/O loop)."""
        return self._master_fd

    @property
    def pid(self) -> int | None:
        """PID do processo filho."""
        return self._pid

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _set_winsize(fd: int, rows: int, cols: int) -> None:
        """Definir tamanho da janela no PTY via ioctl TIOCSWINSZ."""
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass
