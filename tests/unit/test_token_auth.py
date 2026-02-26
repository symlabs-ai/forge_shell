"""
Testes — Viewer password auth
DADO sym_shell attach com machine_code + password
QUANDO o viewer envia password correta/errada ao relay
ENTÃO acesso é permitido ou negado
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.cli.main import build_parser
from src.infrastructure.collab.relay_handler import RelayHandler
from src.infrastructure.collab.viewer_client import ViewerClient


class TestAttachArguments:
    def test_attach_has_machine_code_and_password(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["attach", "497-051-961", "321321"])
        assert args.machine_code == "497-051-961"
        assert args.password == "321321"

    def test_attach_machine_code_stored_correctly(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["attach", "100-200-300", "000000"])
        assert args.machine_code == "100-200-300"

    def test_attach_password_stored_correctly(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["attach", "999-888-777", "654321"])
        assert args.password == "654321"


class TestRelayTokenValidation:
    """Testa que RelayHandler valida token do viewer."""

    def _make_ws(self, messages: list) -> MagicMock:
        """Cria mock de websocket que entrega mensagens e depois fecha."""
        ws = MagicMock()

        async def _aiter():
            for msg in messages:
                yield msg

        ws.__aiter__ = lambda self: _aiter()
        ws.send = AsyncMock()
        ws.close = AsyncMock()
        return ws

    def test_relay_handler_init_accepts_ssl_context(self) -> None:
        handler = RelayHandler(host="0.0.0.0", port=8060, ssl_context=None)
        assert handler._ssl_context is None

    def test_relay_handler_init_stores_ssl_context(self) -> None:
        mock_ctx = MagicMock()
        handler = RelayHandler(host="0.0.0.0", port=8060, ssl_context=mock_ctx)
        assert handler._ssl_context is mock_ctx

    @pytest.mark.asyncio
    async def test_relay_accepts_viewer_with_correct_token(self) -> None:
        """Viewer com token correto é aceito (sem mensagem de erro)."""
        import src.infrastructure.collab.relay_handler as rh
        # Limpar estado global
        rh._sessions.clear()
        rh._session_tokens.clear()

        handler = RelayHandler()
        session_id = "test-session-1"

        # Host registra com token
        host_join = json.dumps({
            "type": "session_join",
            "session_id": session_id,
            "payload": {"role": "host", "token": "secret-token"},
        })
        host_ws = self._make_ws([host_join])
        await handler._handle(host_ws)
        assert rh._session_tokens.get(session_id) == "secret-token"

        # Viewer com token correto
        viewer_join = json.dumps({
            "type": "session_join",
            "session_id": session_id,
            "payload": {"role": "viewer", "token": "secret-token"},
        })
        viewer_ws = self._make_ws([viewer_join])
        await handler._handle(viewer_ws)
        # Nenhuma mensagem de erro enviada
        viewer_ws.send.assert_not_called()
        viewer_ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_relay_rejects_viewer_with_wrong_token(self) -> None:
        """Viewer com token errado recebe erro e conexão é fechada."""
        import src.infrastructure.collab.relay_handler as rh
        rh._sessions.clear()
        rh._session_tokens.clear()

        handler = RelayHandler()
        session_id = "test-session-2"

        # Host registra com token
        host_join = json.dumps({
            "type": "session_join",
            "session_id": session_id,
            "payload": {"role": "host", "token": "correct-token"},
        })
        host_ws = self._make_ws([host_join])
        await handler._handle(host_ws)

        # Viewer com token errado
        viewer_join = json.dumps({
            "type": "session_join",
            "session_id": session_id,
            "payload": {"role": "viewer", "token": "wrong-token"},
        })
        viewer_ws = self._make_ws([viewer_join])
        await handler._handle(viewer_ws)

        # Deve ter enviado mensagem de erro
        viewer_ws.send.assert_called_once()
        sent_data = json.loads(viewer_ws.send.call_args[0][0])
        assert sent_data["type"] == "error"
        assert "inválido" in sent_data["payload"]["message"].lower() or \
               "negado" in sent_data["payload"]["message"].lower()
        viewer_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_relay_accepts_viewer_when_no_token_registered(self) -> None:
        """Viewer pode entrar se host não registrou token (sem token = sem auth)."""
        import src.infrastructure.collab.relay_handler as rh
        rh._sessions.clear()
        rh._session_tokens.clear()

        handler = RelayHandler()
        session_id = "test-session-3"

        # Host registra SEM token
        host_join = json.dumps({
            "type": "session_join",
            "session_id": session_id,
            "payload": {"role": "host", "token": ""},
        })
        host_ws = self._make_ws([host_join])
        await handler._handle(host_ws)
        # Token vazio não é registrado
        assert session_id not in rh._session_tokens

        # Viewer sem token pode entrar
        viewer_join = json.dumps({
            "type": "session_join",
            "session_id": session_id,
            "payload": {"role": "viewer", "token": ""},
        })
        viewer_ws = self._make_ws([viewer_join])
        await handler._handle(viewer_ws)
        viewer_ws.send.assert_not_called()
        viewer_ws.close.assert_not_called()


class TestViewerClientSslParam:
    def test_viewer_client_accepts_ssl_none(self) -> None:
        vc = ViewerClient(
            relay_url="ws://localhost:8060",
            session_id="s-test",
            token="",
            ssl=None,
        )
        assert vc._ssl is None

    def test_viewer_client_accepts_ssl_true(self) -> None:
        vc = ViewerClient(
            relay_url="wss://localhost:8060",
            session_id="s-test",
            token="tok",
            ssl=True,
        )
        assert vc._ssl is True

    def test_viewer_client_backward_compat_no_ssl_arg(self) -> None:
        """Construção sem ssl= funciona (default None)."""
        vc = ViewerClient(
            relay_url="ws://localhost:8060",
            session_id="s-test",
            token="",
        )
        assert vc._ssl is None
