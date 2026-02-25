"""
T-02 — Event bus: schema de eventos padronizados
DADO o sistema de eventos do sym_shell
QUANDO crio cada tipo de evento com os campos obrigatórios
ENTÃO o evento é criado corretamente e tem os atributos esperados
"""
import pytest
from datetime import datetime

from src.adapters.event_bus.events import (
    EventKind,
    TerminalOutputEvent,
    UserInputEvent,
    NLRequestEvent,
    AuditEvent,
    SessionEvent,
    SessionEventKind,
)


class TestEventKind:
    def test_all_kinds_defined(self) -> None:
        kinds = {e.value for e in EventKind}
        assert "terminal_output" in kinds
        assert "user_input" in kinds
        assert "nl_request" in kinds
        assert "audit" in kinds
        assert "session" in kinds


class TestTerminalOutputEvent:
    def test_creation_with_required_fields(self) -> None:
        ev = TerminalOutputEvent(data=b"hello\r\n")
        assert ev.kind == EventKind.TERMINAL_OUTPUT
        assert ev.data == b"hello\r\n"
        assert isinstance(ev.timestamp, datetime)

    def test_empty_data_allowed(self) -> None:
        ev = TerminalOutputEvent(data=b"")
        assert ev.data == b""


class TestUserInputEvent:
    def test_creation(self) -> None:
        ev = UserInputEvent(data=b"ls -la\n")
        assert ev.kind == EventKind.USER_INPUT
        assert ev.data == b"ls -la\n"

    def test_is_nl_trigger_bang_prefix(self) -> None:
        ev = UserInputEvent(data=b"!ls -la\n")
        assert ev.is_nl_escape is True

    def test_is_nl_toggle_bang_only(self) -> None:
        ev = UserInputEvent(data=b"!\n")
        assert ev.is_nl_toggle is True

    def test_plain_input_not_escape(self) -> None:
        ev = UserInputEvent(data=b"ls -la\n")
        assert ev.is_nl_escape is False
        assert ev.is_nl_toggle is False


class TestNLRequestEvent:
    def test_creation(self) -> None:
        ev = NLRequestEvent(text="listar arquivos maiores que 500MB")
        assert ev.kind == EventKind.NL_REQUEST
        assert ev.text == "listar arquivos maiores que 500MB"
        assert isinstance(ev.timestamp, datetime)

    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="text"):
            NLRequestEvent(text="")


class TestAuditEvent:
    def test_creation(self) -> None:
        ev = AuditEvent(
            action="command_executed",
            origin="user",
            details={"command": "ls -la", "exit_code": 0},
        )
        assert ev.kind == EventKind.AUDIT
        assert ev.action == "command_executed"
        assert ev.origin == "user"
        assert ev.details["command"] == "ls -la"

    def test_invalid_origin_raises(self) -> None:
        with pytest.raises(ValueError, match="origin"):
            AuditEvent(action="x", origin="alien", details={})

    def test_valid_origins(self) -> None:
        for origin in ("user", "llm", "remote"):
            ev = AuditEvent(action="x", origin=origin, details={})
            assert ev.origin == origin


class TestSessionEvent:
    def test_join(self) -> None:
        ev = SessionEvent(kind=SessionEventKind.JOIN, session_id="s-123", participant="peer-1")
        assert ev.kind == EventKind.SESSION
        assert ev.session_kind == SessionEventKind.JOIN
        assert ev.session_id == "s-123"

    def test_leave(self) -> None:
        ev = SessionEvent(kind=SessionEventKind.LEAVE, session_id="s-123", participant="peer-1")
        assert ev.session_kind == SessionEventKind.LEAVE
