"""
ChatManager — gerenciamento do chat panel (split view).

Extraído de TerminalSession para separar a responsabilidade de ativação,
desativação e comunicação do chat panel do loop principal de I/O.

Imports de pyte/VTScreen/SplitRenderer são lazy (dentro de activate) para
permitir que TerminalSession seja importado sem puxar pyte — necessário
para o binário forge_host standalone.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.terminal_engine.pty_engine import PTYEngine

_tlog = logging.getLogger("forge_shell.timing")

_CHAT_WIDTH = 30
_MIN_SPLIT_COLS = 60  # mirrored from split_renderer.MIN_SPLIT_COLS


class ChatManager:
    """Gerencia o chat panel em split view."""

    def __init__(self, engine: PTYEngine, get_terminal_size, stdout=None) -> None:
        self._engine = engine
        self._get_terminal_size = get_terminal_size
        self._stdout = stdout
        self.vt_screen = None          # VTScreen | None
        self.chat_panel = None         # ChatPanel | None
        self.split_renderer = None     # SplitRenderer | None
        self.input_router = None       # InputRouter | None
        self.active = False            # split view ativo?
        self.alt_screen_was_active = False  # track alternate screen transitions

    @property
    def _out(self):
        return self._stdout or getattr(sys.stdout, "buffer", None)

    def activate(self) -> None:
        """Activate split view with VTScreen + ChatPanel + SplitRenderer."""
        try:
            from src.infrastructure.terminal_engine.vt_screen import PYTE_AVAILABLE
        except ImportError:
            _tlog.debug("chat: pyte not available, skipping activation")
            return
        if not PYTE_AVAILABLE:
            _tlog.debug("chat: pyte not available, skipping activation")
            return

        from src.infrastructure.terminal_engine.vt_screen import VTScreen
        from src.infrastructure.terminal_engine.chat_panel import ChatPanel
        from src.infrastructure.terminal_engine.split_renderer import SplitRenderer
        from src.infrastructure.terminal_engine.input_router import InputRouter

        rows, cols = self._get_terminal_size()
        if cols < _MIN_SPLIT_COLS:
            _tlog.debug("chat: terminal too narrow (%d cols), skipping", cols)
            return

        out = self._out
        if out is None:
            return

        left_cols = cols - _CHAT_WIDTH - 1

        self.vt_screen = VTScreen(rows, left_cols)
        self.chat_panel = ChatPanel(rows, _CHAT_WIDTH)
        self.split_renderer = SplitRenderer(out, rows, cols, chat_width=_CHAT_WIDTH)
        self.split_renderer.attach(self.vt_screen, self.chat_panel)
        self.input_router = InputRouter()
        self.active = True

        self._engine.resize(rows, left_cols)
        self.split_renderer.render(force=True)
        _tlog.debug("chat: activated (left=%d, right=%d)", left_cols, _CHAT_WIDTH)

    def deactivate(self) -> None:
        """Deactivate split view, restore full-screen terminal."""
        if not self.active:
            return

        if self.split_renderer:
            self.split_renderer.detach()

        self.vt_screen = None
        self.chat_panel = None
        self.split_renderer = None
        self.input_router = None
        self.active = False

        rows, cols = self._get_terminal_size()
        self._engine.resize(rows, cols)
        _tlog.debug("chat: deactivated, PTY full-screen (%dx%d)", rows, cols)

    def handle_message(self, payload: dict) -> None:
        """Handle incoming chat message from relay."""
        if not self.active:
            self.activate()
        if self.chat_panel is None:
            return
        sender = payload.get("sender", "?")
        text = payload.get("text", "")
        role = payload.get("role", sender)
        self.chat_panel.add_message(sender, text, role)
        if self.split_renderer:
            self.split_renderer.render()

    def send_message(self, text: str, relay_bridge=None) -> None:
        """Send chat message via relay and add to local panel."""
        if self.chat_panel is not None:
            self.chat_panel.add_message("host", text, "host")
        if relay_bridge is not None:
            try:
                relay_bridge.send_chat(text, sender="host")
            except Exception:
                pass
        if self.split_renderer:
            self.split_renderer.render()

    def handle_resize(self, rows: int, cols: int) -> None:
        """Handle terminal resize for chat panel."""
        if cols >= _MIN_SPLIT_COLS:
            left_cols = cols - _CHAT_WIDTH - 1
            if self.vt_screen:
                self.vt_screen.resize(rows, left_cols)
            if self.chat_panel:
                self.chat_panel.resize(rows, _CHAT_WIDTH)
            if self.split_renderer:
                self.split_renderer.resize(rows, cols)
            self._engine.resize(rows=rows, cols=left_cols)
        else:
            self.deactivate()

    def handle_enter_alt_screen(self) -> None:
        """Entering alternate screen (vim, top): hide chat, go full-width."""
        self.alt_screen_was_active = True
        if self.split_renderer:
            self.split_renderer.detach()
        rows, cols = self._get_terminal_size()
        self._engine.resize(rows, cols)

    def handle_exit_alt_screen(self) -> None:
        """Exiting alternate screen: restore split."""
        self.alt_screen_was_active = False
        rows, cols = self._get_terminal_size()
        if self.vt_screen and self.chat_panel and self.split_renderer:
            from src.infrastructure.terminal_engine.split_renderer import SplitRenderer
            out = self._out
            left_cols = cols - _CHAT_WIDTH - 1
            self.vt_screen.resize(rows, left_cols)
            self.chat_panel.resize(rows, _CHAT_WIDTH)
            self.split_renderer = SplitRenderer(out, rows, cols, chat_width=_CHAT_WIDTH)
            self.split_renderer.attach(self.vt_screen, self.chat_panel)
            self._engine.resize(rows, left_cols)
            self.split_renderer.render(force=True)
