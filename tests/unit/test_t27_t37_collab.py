"""
T-27 a T-37 — Colaboração remota: sessão, tokens, permissões
DADO o sistema de colaboração
QUANDO gerencio sessões compartilhadas
ENTÃO tokens são gerados/validados e permissões são respeitadas
"""
import pytest
import time
from src.infrastructure.collab.session_manager import (
    SessionManager,
    Session,
    SessionMode,
    SessionError,
)


class TestSession:
    def test_create_session(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        assert session.session_id is not None
        assert session.token is not None
        assert session.is_valid is True
        assert session.host_id == "host-1"

    def test_session_has_expiry(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        assert session.expires_at is not None

    def test_token_validates(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        found = mgr.get_session_by_token(session.token)
        assert found is not None
        assert found.session_id == session.session_id

    def test_invalid_token_returns_none(self) -> None:
        mgr = SessionManager()
        found = mgr.get_session_by_token("bogus-token")
        assert found is None

    def test_revoke_session(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.revoke_session(session.session_id)
        found = mgr.get_session_by_token(session.token)
        assert found is None

    def test_expired_session_invalid(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=0)
        # expire_minutes=0 → expira imediatamente
        time.sleep(0.01)
        found = mgr.get_session_by_token(session.token)
        assert found is None or found.is_valid is False


class TestSessionPermissions:
    def test_view_only_cannot_inject_input(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.add_participant(session.session_id, participant_id="peer-1", mode=SessionMode.VIEW_ONLY)
        assert mgr.can_inject_input(session.session_id, "peer-1") is False

    def test_suggest_only_cannot_inject_input(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.add_participant(session.session_id, participant_id="peer-2", mode=SessionMode.SUGGEST_ONLY)
        assert mgr.can_inject_input(session.session_id, "peer-2") is False

    def test_suggest_only_can_send_cards(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.add_participant(session.session_id, participant_id="peer-2", mode=SessionMode.SUGGEST_ONLY)
        assert mgr.can_send_suggestions(session.session_id, "peer-2") is True

    def test_view_only_cannot_send_cards(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.add_participant(session.session_id, participant_id="peer-1", mode=SessionMode.VIEW_ONLY)
        assert mgr.can_send_suggestions(session.session_id, "peer-1") is False

    def test_unknown_participant_cannot_do_anything(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        assert mgr.can_inject_input(session.session_id, "nobody") is False
        assert mgr.can_send_suggestions(session.session_id, "nobody") is False

    def test_add_participant_to_invalid_session_raises(self) -> None:
        mgr = SessionManager()
        with pytest.raises(SessionError):
            mgr.add_participant("nonexistent", participant_id="x", mode=SessionMode.VIEW_ONLY)


class TestSessionState:
    def test_get_session_by_id(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        found = mgr.get_session(session.session_id)
        assert found is not None

    def test_list_participants(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.add_participant(session.session_id, "p1", SessionMode.VIEW_ONLY)
        mgr.add_participant(session.session_id, "p2", SessionMode.SUGGEST_ONLY)
        participants = mgr.list_participants(session.session_id)
        assert len(participants) == 2

    def test_remove_participant(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session(host_id="host-1", expire_minutes=60)
        mgr.add_participant(session.session_id, "p1", SessionMode.VIEW_ONLY)
        mgr.remove_participant(session.session_id, "p1")
        assert len(mgr.list_participants(session.session_id)) == 0
