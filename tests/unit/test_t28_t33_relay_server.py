"""
T-28 a T-33 — Relay server, share, attach, client terminal, chat, suggest-only cards
DADO o RelayServer e os usecases de share/attach
QUANDO gerencio streams e mensagens
ENTÃO distribuição, chat e cards funcionam corretamente
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call

from src.infrastructure.collab.relay_server import RelayServer, RelaySession
from src.infrastructure.collab.protocol import (
    RelayMessage, MessageType, encode_message, decode_message,
)
from src.application.usecases.share_session import ShareSession
from src.application.usecases.suggest_card import SuggestCard


class TestRelaySession:
    """T-28 — Relay session: distribui output do host para clients."""

    def test_create_relay_session(self) -> None:
        session = RelaySession(session_id="s-001", token="tok123")
        assert session.session_id == "s-001"
        assert session.token == "tok123"
        assert session.client_count == 0

    def test_add_and_remove_client(self) -> None:
        session = RelaySession(session_id="s-001", token="tok123")
        client = AsyncMock()
        session.add_client("c-1", client)
        assert session.client_count == 1
        session.remove_client("c-1")
        assert session.client_count == 0

    def test_broadcast_to_all_clients(self) -> None:
        session = RelaySession(session_id="s-001", token="tok123")
        client_a = AsyncMock()
        client_b = AsyncMock()
        session.add_client("c-1", client_a)
        session.add_client("c-2", client_b)

        msg = RelayMessage(
            type=MessageType.TERMINAL_OUTPUT,
            session_id="s-001",
            payload={"data": "SGVsbG8="},
        )

        asyncio.run(session.broadcast(msg))

        client_a.send.assert_called_once()
        client_b.send.assert_called_once()

    def test_broadcast_skips_disconnected_client(self) -> None:
        """Client que lança exceção no send é removido graciosamente."""
        session = RelaySession(session_id="s-001", token="tok123")
        bad_client = AsyncMock()
        bad_client.send.side_effect = Exception("disconnected")
        session.add_client("c-bad", bad_client)

        msg = RelayMessage(
            type=MessageType.PING,
            session_id="s-001",
            payload={},
        )
        asyncio.run(session.broadcast(msg))
        # não deve lançar exceção
        assert session.client_count == 0  # removido automaticamente


class TestRelayServer:
    """T-28 — RelayServer: gerencia múltiplas sessões."""

    def test_create_and_get_session(self) -> None:
        server = RelayServer()
        session = server.create_session("s-001", "tok123")
        assert session.session_id == "s-001"
        assert server.get_session("s-001") is session

    def test_get_nonexistent_session_returns_none(self) -> None:
        server = RelayServer()
        assert server.get_session("s-999") is None

    def test_get_session_by_token(self) -> None:
        server = RelayServer()
        server.create_session("s-001", "mytoken")
        session = server.get_session_by_token("mytoken")
        assert session is not None
        assert session.session_id == "s-001"

    def test_get_session_by_invalid_token(self) -> None:
        server = RelayServer()
        assert server.get_session_by_token("badtoken") is None

    def test_remove_session(self) -> None:
        server = RelayServer()
        server.create_session("s-001", "tok")
        server.remove_session("s-001")
        assert server.get_session("s-001") is None


class TestShareSession:
    """T-29 — usecase sym_shell share."""

    def test_share_returns_session_info(self) -> None:
        sm = MagicMock()
        sm.create_session.return_value = MagicMock(
            session_id="s-abc",
            token="tok-xyz",
        )
        uc = ShareSession(session_manager=sm)
        result = uc.run(host_id="host-1", expire_minutes=60)
        assert result["session_id"] == "s-abc"
        assert result["token"] == "tok-xyz"

    def test_share_calls_session_manager(self) -> None:
        sm = MagicMock()
        sm.create_session.return_value = MagicMock(session_id="s-1", token="t-1")
        uc = ShareSession(session_manager=sm)
        uc.run(host_id="host-1", expire_minutes=30)
        sm.create_session.assert_called_once_with(host_id="host-1", expire_minutes=30)


class TestSuggestCard:
    """T-33 — Suggest-only card: client propõe, host confirma."""

    def test_suggest_card_fields(self) -> None:
        card = SuggestCard(
            command="ls -la /tmp",
            explanation="Lista arquivos temporários",
            participant_id="alice",
            session_id="s-001",
        )
        assert card.command == "ls -la /tmp"
        assert card.explanation == "Lista arquivos temporários"
        assert card.participant_id == "alice"
        assert card.session_id == "s-001"
        assert card.accepted is False

    def test_suggest_card_accept(self) -> None:
        card = SuggestCard(
            command="ls",
            explanation="lista",
            participant_id="alice",
            session_id="s-001",
        )
        card.accept()
        assert card.accepted is True

    def test_suggest_card_reject(self) -> None:
        card = SuggestCard(
            command="rm -rf /",
            explanation="apaga tudo",
            participant_id="bob",
            session_id="s-001",
        )
        card.reject()
        assert card.accepted is False

    def test_suggest_card_to_relay_message(self) -> None:
        card = SuggestCard(
            command="git status",
            explanation="ver status do git",
            participant_id="carol",
            session_id="s-001",
        )
        msg = card.to_relay_message()
        assert msg.type == MessageType.SUGGEST
        assert msg.payload["command"] == "git status"
        assert msg.payload["explanation"] == "ver status do git"
