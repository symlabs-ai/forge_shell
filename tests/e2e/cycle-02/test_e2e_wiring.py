"""
E2E cycle-02 — Wiring validation (ft.e2e.01.cli_validation)

Valida que os subcomandos estão wired (não retornam mais stubs) e que
pyproject.toml + .gitattributes estão corretos.
"""
import subprocess
import sys
from pathlib import Path
import pytest

PYTHON = sys.executable
ROOT = Path(__file__).parent.parent.parent.parent


def run(*args, input_data=None) -> tuple[int, str, str]:
    result = subprocess.run(
        [PYTHON, "-m", "src.adapters.cli.main", *args],
        capture_output=True, text=True, timeout=10,
        input=input_data,
    )
    return result.returncode, result.stdout, result.stderr


class TestDoctorWiredE2E:
    def test_doctor_runs_and_shows_pty(self) -> None:
        rc, out, err = run("doctor")
        assert rc == 0
        assert "pty" in out.lower() or "PTY" in out

    def test_doctor_shows_ok_status(self) -> None:
        rc, out, err = run("doctor")
        assert "OK" in out or "ok" in out.lower()

    def test_doctor_no_longer_stub(self) -> None:
        rc, out, err = run("doctor")
        assert "não implementado" not in out


class TestShareWiredE2E:
    def test_share_runs_and_shows_session_id(self) -> None:
        rc, out, err = run("share")
        assert rc == 0
        assert "s-" in out  # session_id começa com "s-"

    def test_share_shows_token(self) -> None:
        rc, out, err = run("share")
        assert "Token" in out or "token" in out.lower()

    def test_share_no_longer_stub(self) -> None:
        rc, out, err = run("share")
        assert "não implementado" not in out


class TestPackagingE2E:
    def test_pyproject_has_entry_point(self) -> None:
        content = (ROOT / "pyproject.toml").read_text()
        assert "sym_shell" in content
        assert "main" in content

    def test_gitattributes_prevents_crlf_in_sh(self) -> None:
        content = (ROOT / ".gitattributes").read_text()
        assert "*.sh" in content
        assert "lf" in content

    def test_session_mode_enum_importable(self) -> None:
        result = subprocess.run(
            [PYTHON, "-c", "from src.application.usecases.terminal_session import SessionMode; print(SessionMode.NL.value)"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "nl" in result.stdout

    def test_nl_interceptor_importable(self) -> None:
        result = subprocess.run(
            [PYTHON, "-c", "from src.application.usecases.nl_interceptor import NLInterceptor; print('ok')"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
