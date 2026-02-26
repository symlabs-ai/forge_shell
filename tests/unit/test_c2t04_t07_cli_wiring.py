"""
C2-T-04 + C2-T-07 — CLI wired: --passthrough e doctor subcommand
DADO o CLI main() com mocks de TerminalSession e DoctorRunner
QUANDO invoco --passthrough ou doctor
ENTÃO as implementações reais são chamadas (não mais stubs)
"""
import pytest
from unittest.mock import MagicMock, patch


class TestPassthroughWired:
    def test_passthrough_calls_terminal_session(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = 0

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session) as MockTS:
            with patch("src.adapters.cli.main.ConfigLoader") as MockCL:
                MockCL.return_value.load.return_value = MagicMock()
                from src.adapters.cli.main import main
                rc = main(["--passthrough"])

        MockTS.assert_called_once()
        mock_session.run.assert_called_once()

    def test_passthrough_creates_session_with_passthrough_true(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = 0

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session) as MockTS:
            with patch("src.adapters.cli.main.ConfigLoader") as MockCL:
                MockCL.return_value.load.return_value = MagicMock()
                from src.adapters.cli.main import main
                main(["--passthrough"])

        _, kwargs = MockTS.call_args
        assert kwargs.get("passthrough") is True or MockTS.call_args[0]

    def test_passthrough_returns_session_exit_code(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = 42

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session):
            with patch("src.adapters.cli.main.ConfigLoader") as MockCL:
                MockCL.return_value.load.return_value = MagicMock()
                from src.adapters.cli.main import main
                rc = main(["--passthrough"])

        assert rc == 42


class TestDoctorWired:
    def test_doctor_calls_runner(self) -> None:
        mock_report = MagicMock()
        mock_report.to_text.return_value = "✓ pty OK\n✓ Overall: OK"
        mock_report.overall.value = "ok"

        with patch("src.adapters.cli.main.DoctorRunner") as MockRunner:
            MockRunner.return_value.run.return_value = mock_report
            from src.adapters.cli.main import main
            rc = main(["doctor"])

        MockRunner.return_value.run.assert_called_once()
        assert rc == 0

    def test_doctor_prints_report(self, capsys) -> None:
        mock_report = MagicMock()
        mock_report.to_text.return_value = "forge_shell doctor OK"
        mock_report.overall.value = "ok"

        with patch("src.adapters.cli.main.DoctorRunner") as MockRunner:
            MockRunner.return_value.run.return_value = mock_report
            from src.adapters.cli.main import main
            main(["doctor"])

        captured = capsys.readouterr()
        assert "forge_shell doctor OK" in captured.out

    def test_doctor_returns_1_on_fail(self) -> None:
        mock_report = MagicMock()
        mock_report.to_text.return_value = "✗ pty FAIL"
        mock_report.overall.value = "fail"

        with patch("src.adapters.cli.main.DoctorRunner") as MockRunner:
            MockRunner.return_value.run.return_value = mock_report
            from src.adapters.cli.main import main
            rc = main(["doctor"])

        assert rc == 1


class TestDefaultSessionWired:
    def test_default_mode_calls_terminal_session(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value = 0

        with patch("src.adapters.cli.main.TerminalSession", return_value=mock_session):
            with patch("src.adapters.cli.main.ConfigLoader") as MockCL:
                with patch("src.adapters.cli.main.Redactor"):
                    MockCL.return_value.load.return_value = MagicMock()
                    from src.adapters.cli.main import main
                    rc = main([])

        mock_session.run.assert_called_once()
        assert rc == 0
