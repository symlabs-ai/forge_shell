"""
T-27 a T-38 — Protocolo host↔relay e infraestrutura de colaboração
DADO o protocolo de mensagens e componentes de relay
QUANDO processo frames e gerencio sessões
ENTÃO framing, privacidade e indicadores funcionam corretamente
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from src.infrastructure.collab.protocol import (
    MessageType,
    RelayMessage,
    encode_message,
    decode_message,
    FrameError,
)
from src.infrastructure.collab.session_manager import SessionManager, SessionMode
from src.infrastructure.collab.input_privacy import InputPrivacyFilter
from src.infrastructure.collab.session_indicator import SessionIndicator


class TestRelayProtocol:
    """T-27 — Protocolo host↔relay."""

    def test_encode_decode_terminal_output(self) -> None:
        msg = RelayMessage(
            type=MessageType.TERMINAL_OUTPUT,
            session_id="s-abc",
            payload={"data": "SGVsbG8="},  # base64
        )
        raw = encode_message(msg)
        decoded = decode_message(raw)
        assert decoded.type == MessageType.TERMINAL_OUTPUT
        assert decoded.session_id == "s-abc"
        assert decoded.payload["data"] == "SGVsbG8="

    def test_encode_produces_json_bytes(self) -> None:
        msg = RelayMessage(
            type=MessageType.PING,
            session_id="s-001",
            payload={},
        )
        raw = encode_message(msg)
        assert isinstance(raw, bytes)
        parsed = json.loads(raw)
        assert parsed["type"] == "ping"

    def test_decode_invalid_raises_frame_error(self) -> None:
        with pytest.raises(FrameError):
            decode_message(b"not json")

    def test_decode_missing_type_raises_frame_error(self) -> None:
        raw = json.dumps({"session_id": "s-1", "payload": {}}).encode()
        with pytest.raises(FrameError):
            decode_message(raw)

    def test_all_message_types_defined(self) -> None:
        expected = {
            "terminal_output", "chat", "suggest", "ping", "pong",
            "session_join", "session_leave", "error",
        }
        defined = {t.value for t in MessageType}
        assert expected.issubset(defined)

    def test_encode_chat_message(self) -> None:
        msg = RelayMessage(
            type=MessageType.CHAT,
            session_id="s-xyz",
            payload={"from": "alice", "text": "olá"},
        )
        raw = encode_message(msg)
        decoded = decode_message(raw)
        assert decoded.payload["from"] == "alice"

    def test_encode_suggest_message(self) -> None:
        msg = RelayMessage(
            type=MessageType.SUGGEST,
            session_id="s-xyz",
            payload={"command": "ls -la", "explanation": "lista arquivos"},
        )
        raw = encode_message(msg)
        decoded = decode_message(raw)
        assert decoded.payload["command"] == "ls -la"


class TestInputPrivacyFilter:
    """T-34 — Não transmitir input quando echo está desativado."""

    def test_allows_transmission_when_echo_on(self) -> None:
        f = InputPrivacyFilter()
        f.set_echo(True)
        assert f.should_transmit(b"ls -la\n") is True

    def test_blocks_transmission_when_echo_off(self) -> None:
        f = InputPrivacyFilter()
        f.set_echo(False)
        assert f.should_transmit(b"mysecretpassword\n") is False

    def test_detects_echo_off_via_ansi(self) -> None:
        """bash envia stty -echo antes de ler senhas — detectar isso."""
        f = InputPrivacyFilter()
        f.process_output(b"\x1b[8m")  # sequence de ocultar texto
        # não deve transmitir enquanto detectar echo-off state
        assert f.should_transmit(b"password\n") is False

    def test_restores_echo_on_ansi_reset(self) -> None:
        f = InputPrivacyFilter()
        f.process_output(b"\x1b[8m")
        f.process_output(b"\x1b[0m")
        assert f.should_transmit(b"visible text\n") is True

    def test_default_allows_transmission(self) -> None:
        f = InputPrivacyFilter()
        assert f.should_transmit(b"hello\n") is True


class TestSessionIndicator:
    """T-35 — Indicador de sessão compartilhada."""

    def test_inactive_when_no_session(self) -> None:
        ind = SessionIndicator()
        assert ind.is_active is False

    def test_active_after_join(self) -> None:
        ind = SessionIndicator()
        ind.on_participant_joined("alice")
        assert ind.is_active is True

    def test_inactive_after_all_leave(self) -> None:
        ind = SessionIndicator()
        ind.on_participant_joined("alice")
        ind.on_participant_left("alice")
        assert ind.is_active is False

    def test_status_text_contains_session_info(self) -> None:
        ind = SessionIndicator()
        ind.on_participant_joined("alice")
        text = ind.status_text()
        assert "ATIVA" in text or "ativa" in text.lower() or "alice" in text

    def test_status_text_inactive(self) -> None:
        ind = SessionIndicator()
        text = ind.status_text()
        assert text == "" or "inativa" in text.lower() or text == "—"

    def test_multiple_participants(self) -> None:
        ind = SessionIndicator()
        ind.on_participant_joined("alice")
        ind.on_participant_joined("bob")
        ind.on_participant_left("alice")
        assert ind.is_active is True  # bob ainda está
        ind.on_participant_left("bob")
        assert ind.is_active is False
