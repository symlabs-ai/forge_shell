"""
T-42 — sym_shell doctor: diagnóstico da engine
DADO o DoctorRunner
QUANDO executo diagnóstico
ENTÃO recebo relatório com status de PTY, termios, sinais e resize
"""
import pytest
import sys

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="PTY não disponível no Windows")

from src.application.usecases.doctor_runner import DoctorRunner, DoctorReport, CheckStatus


class TestDoctorRunner:
    def test_doctor_returns_report(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert isinstance(report, DoctorReport)

    def test_report_has_pty_check(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert "pty" in report.checks

    def test_report_has_termios_check(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert "termios" in report.checks

    def test_report_has_resize_check(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert "resize" in report.checks

    def test_report_has_signals_check(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert "signals" in report.checks

    def test_pty_check_passes(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report.checks["pty"] == CheckStatus.OK

    def test_resize_check_passes(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        assert report.checks["resize"] == CheckStatus.OK

    def test_report_overall_ok(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        # em ambiente Unix sem PTY falho, deve ser ok
        assert report.overall in (CheckStatus.OK, CheckStatus.WARN)

    def test_report_to_text(self) -> None:
        runner = DoctorRunner()
        report = runner.run()
        text = report.to_text()
        assert "pty" in text.lower() or "PTY" in text
        assert isinstance(text, str)

    def test_check_status_values(self) -> None:
        assert CheckStatus.OK.value == "ok"
        assert CheckStatus.WARN.value == "warn"
        assert CheckStatus.FAIL.value == "fail"
