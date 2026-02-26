"""
T-10/T-11 — Alternate screen buffer detection
DADO o detector de alternate screen buffer
QUANDO recebo chunks de output com escape sequences
ENTÃO o estado de alternate screen é atualizado corretamente
E a flag de interceptação NL é ativada/desativada
"""
import pytest
from src.infrastructure.terminal_engine.alternate_screen import AlternateScreenDetector


class TestAlternateScreenDetection:
    def setup_method(self) -> None:
        self.detector = AlternateScreenDetector()

    def test_starts_inactive(self) -> None:
        assert self.detector.is_active is False
        assert self.detector.nl_interception_allowed is True

    def test_enter_sequence_1049(self) -> None:
        self.detector.feed(b"\x1b[?1049h some output")
        assert self.detector.is_active is True
        assert self.detector.nl_interception_allowed is False

    def test_enter_sequence_47(self) -> None:
        self.detector.feed(b"\x1b[?47h")
        assert self.detector.is_active is True

    def test_exit_sequence_1049(self) -> None:
        self.detector.feed(b"\x1b[?1049h")
        self.detector.feed(b"\x1b[?1049l")
        assert self.detector.is_active is False
        assert self.detector.nl_interception_allowed is True

    def test_exit_sequence_47(self) -> None:
        self.detector.feed(b"\x1b[?47h")
        self.detector.feed(b"\x1b[?47l")
        assert self.detector.is_active is False

    def test_plain_output_no_change(self) -> None:
        self.detector.feed(b"hello world\r\n")
        assert self.detector.is_active is False

    def test_enter_exit_in_single_chunk(self) -> None:
        self.detector.feed(b"\x1b[?1049h\x1b[?1049l")
        assert self.detector.is_active is False

    def test_nested_enter_counted(self) -> None:
        self.detector.feed(b"\x1b[?1049h")
        self.detector.feed(b"\x1b[?1049h")
        self.detector.feed(b"\x1b[?1049l")
        # ainda ativo após 1 exit com 2 enters
        assert self.detector.is_active is True

    def test_reset_clears_state(self) -> None:
        self.detector.feed(b"\x1b[?1049h")
        self.detector.reset()
        assert self.detector.is_active is False
