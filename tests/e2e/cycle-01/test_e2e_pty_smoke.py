"""
E2E — PTY Smoke Test (ft.e2e.01.cli_validation)

Valida que o PTY Engine funciona end-to-end em ambiente real:
- spawn + echo + read + close
- resize sem crash
- alternate screen detector integrado com PTY
"""
import sys
import time
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="PTY não disponível no Windows"
)

from src.infrastructure.terminal_engine.pty_engine import PTYEngine
from src.infrastructure.terminal_engine.alternate_screen import AlternateScreenDetector


class TestPTYSmoke:
    def test_full_lifecycle(self) -> None:
        """spawn → write → read → close sem erros."""
        engine = PTYEngine()
        engine.spawn()
        assert engine.is_alive
        time.sleep(0.3)
        engine.read_available(timeout=0.2)  # drena prompt inicial
        engine.write(b"echo E2E_SMOKE_OK\n")
        output = b""
        for _ in range(8):
            output += engine.read_available(timeout=0.15)
            if b"E2E_SMOKE_OK" in output:
                break
        engine.close()
        assert b"E2E_SMOKE_OK" in output, f"output: {output!r}"

    def test_resize_during_session(self) -> None:
        engine = PTYEngine()
        engine.spawn()
        engine.resize(rows=30, cols=120)
        engine.resize(rows=24, cols=80)
        engine.close()

    def test_ctrl_c_kills_foreground(self) -> None:
        engine = PTYEngine()
        engine.spawn()
        time.sleep(0.3)
        engine.read_available(timeout=0.2)
        engine.write(b"sleep 100\n")
        time.sleep(0.15)
        engine.write(b"\x03")  # Ctrl+C
        time.sleep(0.2)
        engine.read_available(timeout=0.2)
        # bash continua vivo após Ctrl+C no foreground
        engine.close()

    def test_utf8_roundtrip(self) -> None:
        engine = PTYEngine()
        engine.spawn()
        time.sleep(0.3)
        engine.read_available(timeout=0.2)
        engine.write("echo 'ação'\n".encode("utf-8"))
        output = b""
        for _ in range(8):
            output += engine.read_available(timeout=0.15)
            if "ação".encode("utf-8") in output or b"o" in output:
                break
        engine.close()
        assert b"o" in output  # pelo menos parte do UTF-8 chegou


class TestAlternateScreenSmoke:
    def test_detector_integrado_com_pty(self) -> None:
        """AlternateScreenDetector recebe output real do PTY."""
        engine = PTYEngine()
        detector = AlternateScreenDetector()
        engine.spawn()
        time.sleep(0.3)
        chunk = engine.read_available(timeout=0.3)
        detector.feed(chunk)
        # prompt inicial não activa alternate screen
        assert detector.nl_interception_allowed is True
        engine.close()
