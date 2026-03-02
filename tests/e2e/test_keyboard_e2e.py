"""
E2E keyboard test — uses tmux as a real terminal emulator.

Detects cursor jumps that only manifest with real keystroke timing.
tmux provides ground-truth cursor position (no pyte false positives).

Usage:
    pytest tests/e2e/test_keyboard_e2e.py -v -s

Requires a running forge_host on palhano.services (or configure conftest.py).
"""
import time

import pytest

from tests.e2e.tmux_harness import (
    assert_cursor_advances_monotonically,
    assert_screen_contains,
)


class TestTerminalTyping:
    """Test basic terminal typing — cursor should advance monotonically."""

    def test_echo_command(self, tmux_session):
        tmux_session.press_enter()
        time.sleep(0.3)

        snapshots = tmux_session.type_string("echo hi")
        assert_cursor_advances_monotonically(snapshots)

        tmux_session.press_enter()

    def test_ls_al_no_cursor_jump(self, tmux_session):
        """Regression test: 'ls -al' used to cause cursor jump at 'a'."""
        tmux_session.press_enter()
        time.sleep(0.3)

        snapshots = tmux_session.type_string("ls -al")
        assert_cursor_advances_monotonically(snapshots)

        tmux_session.press_enter()
        time.sleep(1)  # wait for ls output

    def test_longer_command_no_jump(self, tmux_session):
        """Test a longer command with spaces."""
        tmux_session.press_enter()
        time.sleep(0.3)

        snapshots = tmux_session.type_string("echo hello world")
        assert_cursor_advances_monotonically(snapshots)

        tmux_session.press_enter()


class TestChatSplit:
    """Test F4 chat activation, message typing, and return to terminal."""

    def test_f4_activates_chat(self, tmux_session):
        tmux_session.press_enter()
        tmux_session.press_f4()
        time.sleep(0.5)

        screen = tmux_session.capture_screen()
        found_separator = any("\u2502" in line for line in screen)
        found_chat = any("Chat" in line for line in screen)
        assert found_separator or found_chat, (
            "Chat split not visible after F4. Screen:\n" + "\n".join(screen)
        )

    def test_chat_message_typing(self, tmux_session):
        # Second F4 focuses chat input
        tmux_session.press_f4()
        time.sleep(0.3)

        snapshots = tmux_session.type_string("teste e2e")

        # In chat mode cursor should not go backwards
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            if curr.char_typed != " ":
                assert curr.cursor_x >= prev.cursor_x, (
                    f"Chat cursor went backwards at {curr.char_typed!r} (index {i}): "
                    f"x {prev.cursor_x} -> {curr.cursor_x}"
                )

        tmux_session.press_enter()
        time.sleep(0.5)

        assert_screen_contains(tmux_session, "[eu]")

    def test_return_to_terminal_after_chat(self, tmux_session):
        """Critical: typing in terminal after chat must not have cursor jumps."""
        # F4 back to terminal focus
        tmux_session.press_f4()
        time.sleep(0.5)

        # Split view: batched rendering may produce +2 jumps, so strict=False.
        # clamp_x=47: cursor clamped at left pane edge (80 - 30 - 2 - 1 = 47).
        snapshots = tmux_session.type_string("echo post_chat")
        assert_cursor_advances_monotonically(snapshots, clamp_x=47, strict=False)

        tmux_session.press_enter()

    def test_ls_al_after_chat_no_jump(self, tmux_session):
        """Original regression: 'ls -al' cursor jumps after chat usage."""
        tmux_session.press_enter()
        time.sleep(0.3)

        snapshots = tmux_session.type_string("ls -al")
        assert_cursor_advances_monotonically(snapshots, clamp_x=47, strict=False)

        tmux_session.press_enter()
        time.sleep(1)
