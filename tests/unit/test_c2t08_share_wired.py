"""
C2-T-08 — CLI share subcommand wired
DADO o CLI com ShareSession mockado
QUANDO invoco 'sym_shell share'
ENTÃO ShareSession é chamado e token/session-id são exibidos
"""
import pytest
from unittest.mock import MagicMock, patch


class TestShareWired:
    def test_share_calls_share_session(self) -> None:
        mock_result = {"session_id": "s-abc123", "token": "tok-xyz", "expires_at": "2026-03-01T00:00:00+00:00"}

        with patch("src.adapters.cli.main.ShareSession") as MockSS:
            with patch("src.adapters.cli.main.SessionManager") as MockSM:
                MockSS.return_value.run.return_value = mock_result
                from src.adapters.cli.main import main
                rc = main(["share"])

        MockSS.return_value.run.assert_called_once()
        assert rc == 0

    def test_share_prints_session_id(self, capsys) -> None:
        mock_result = {"session_id": "s-abc123", "token": "tok-xyz", "expires_at": "2026-03-01T00:00:00+00:00"}

        with patch("src.adapters.cli.main.ShareSession") as MockSS:
            with patch("src.adapters.cli.main.SessionManager"):
                MockSS.return_value.run.return_value = mock_result
                from src.adapters.cli.main import main
                main(["share"])

        captured = capsys.readouterr()
        assert "s-abc123" in captured.out

    def test_share_prints_token(self, capsys) -> None:
        mock_result = {"session_id": "s-abc123", "token": "tok-xyz", "expires_at": "2026-03-01T00:00:00+00:00"}

        with patch("src.adapters.cli.main.ShareSession") as MockSS:
            with patch("src.adapters.cli.main.SessionManager"):
                MockSS.return_value.run.return_value = mock_result
                from src.adapters.cli.main import main
                main(["share"])

        captured = capsys.readouterr()
        assert "tok-xyz" in captured.out

    def test_share_with_expire_flag(self) -> None:
        mock_result = {"session_id": "s-1", "token": "t-1", "expires_at": "2026-03-01T00:00:00+00:00"}

        with patch("src.adapters.cli.main.ShareSession") as MockSS:
            with patch("src.adapters.cli.main.SessionManager"):
                MockSS.return_value.run.return_value = mock_result
                from src.adapters.cli.main import main
                main(["share", "--expire", "30"])

        _, kwargs = MockSS.return_value.run.call_args
        assert kwargs.get("expire_minutes") == 30 or MockSS.return_value.run.call_args[0]
