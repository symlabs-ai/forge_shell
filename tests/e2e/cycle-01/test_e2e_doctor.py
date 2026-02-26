"""
E2E — Doctor Smoke (ft.e2e.01.cli_validation)

Valida que o DoctorRunner produz relatório correto em ambiente real
e que o overall status é OK ou WARN (nunca FAIL em ambiente Unix saudável).
"""
import sys
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="PTY não disponível no Windows"
)

from src.application.usecases.doctor_runner import DoctorRunner, CheckStatus


class TestDoctorE2E:
    def test_doctor_runs_without_exception(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report is not None

    def test_pty_check_ok_in_unix(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report.checks["pty"] == CheckStatus.OK

    def test_resize_check_ok_in_unix(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report.checks["resize"] == CheckStatus.OK

    def test_signals_check_ok_in_unix(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report.checks["signals"] == CheckStatus.OK

    def test_overall_not_fail(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report.overall != CheckStatus.FAIL

    def test_report_text_readable(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        text = report.to_text()
        assert len(text) > 0
        assert "PTY" in text or "pty" in text
