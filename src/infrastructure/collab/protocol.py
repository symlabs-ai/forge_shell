"""
Protocolo host↔relay — T-27.

Define o schema de mensagens, framing JSON e tratamento de erros
para comunicação entre o host forge_shell e o relay server.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class ClientRole(str, Enum):
    HOST = "host"
    VIEWER = "viewer"
    AGENT = "agent"


class MessageType(str, Enum):
    TERMINAL_OUTPUT = "terminal_output"
    CHAT = "chat"
    SUGGEST = "suggest"
    PING = "ping"
    PONG = "pong"
    SESSION_JOIN = "session_join"
    SESSION_LEAVE = "session_leave"
    ERROR = "error"


class FrameError(Exception):
    pass


@dataclass
class RelayMessage:
    type: MessageType
    session_id: str
    payload: dict = field(default_factory=dict)


def encode_message(msg: RelayMessage) -> bytes:
    """Serializar RelayMessage para bytes JSON."""
    data = {
        "type": msg.type.value,
        "session_id": msg.session_id,
        "payload": msg.payload,
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def decode_message(raw: bytes) -> RelayMessage:
    """Deserializar bytes JSON para RelayMessage. Lança FrameError se inválido."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FrameError(f"JSON inválido: {exc}") from exc

    if "type" not in data:
        raise FrameError("Campo 'type' ausente na mensagem")

    try:
        msg_type = MessageType(data["type"])
    except ValueError as exc:
        raise FrameError(f"Tipo de mensagem desconhecido: {data['type']}") from exc

    return RelayMessage(
        type=msg_type,
        session_id=data.get("session_id", ""),
        payload=data.get("payload", {}),
    )
