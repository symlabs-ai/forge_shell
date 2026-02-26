"""
Unit tests — Agent suggest display in TerminalSession.

Verifica que sugestões de agents remotos são renderizadas corretamente
no terminal do host e que o PTY injection segue a política de risco.
"""
import io
from unittest.mock import MagicMock

import pytest

from src.application.usecases.terminal_session import TerminalSession, SessionMode


def _make_session() -> tuple[TerminalSession, io.BytesIO, MagicMock]:
    """Cria TerminalSession com stdout capturado e engine mockado."""
    config = MagicMock()
    config.nl_mode.default_active = True
    config.nl_mode.context_lines = 50
    session = TerminalSession(config=config, passthrough=False)
    buf = io.BytesIO()
    session._stdout = buf
    engine = MagicMock()
    session._engine = engine
    return session, buf, engine


class TestAgentSuggestDisplay:
    def test_agent_suggest_renders_prefix(self) -> None:
        """Output contém [Agent] em magenta."""
        session, buf, _ = _make_session()
        session._handle_agent_suggest({
            "commands": ["ls -la"],
            "explanation": "listar arquivos",
            "risk_level": "LOW",
        })
        output = buf.getvalue()
        assert b"[Agent]" in output
        # magenta prefix: \033[1;35m
        assert b"\033[1;35m[Agent]" in output

    def test_agent_suggest_low_risk_injects_pty(self) -> None:
        """LOW risk: injeta comando no PTY."""
        session, buf, engine = _make_session()
        session._handle_agent_suggest({
            "commands": ["echo hello"],
            "explanation": "test",
            "risk_level": "LOW",
        })
        engine.write.assert_called_once_with(b"echo hello")

    def test_agent_suggest_medium_risk_injects_pty(self) -> None:
        """MEDIUM risk: também injeta no PTY."""
        session, buf, engine = _make_session()
        session._handle_agent_suggest({
            "commands": ["apt update"],
            "explanation": "atualizar pacotes",
            "risk_level": "MEDIUM",
        })
        engine.write.assert_called_once_with(b"apt update")

    def test_agent_suggest_high_risk_no_inject(self) -> None:
        """HIGH risk: NÃO injeta no PTY, apenas exibe."""
        session, buf, engine = _make_session()
        session._handle_agent_suggest({
            "commands": ["rm -rf /"],
            "explanation": "destruir tudo",
            "risk_level": "HIGH",
        })
        engine.write.assert_not_called()
        output = buf.getvalue()
        assert b"rm -rf /" in output
        assert b"ALTO" in output or b"HIGH" in output

    def test_agent_suggest_shows_risk_colors(self) -> None:
        """Risco LOW=verde, MEDIUM=amarelo, HIGH=vermelho."""
        for level, color_code in [("LOW", b"\033[1;32m"), ("MEDIUM", b"\033[1;33m"), ("HIGH", b"\033[1;31m")]:
            session, buf, _ = _make_session()
            session._handle_agent_suggest({
                "commands": ["cmd"],
                "explanation": "x",
                "risk_level": level,
            })
            output = buf.getvalue()
            assert color_code in output, f"Expected {color_code!r} for {level}"

    def test_agent_suggest_multiple_commands_joined(self) -> None:
        """Múltiplos comandos são concatenados com &&."""
        session, buf, engine = _make_session()
        session._handle_agent_suggest({
            "commands": ["cd /tmp", "ls -la"],
            "explanation": "navegar e listar",
            "risk_level": "LOW",
        })
        output = buf.getvalue()
        assert b"cd /tmp && ls -la" in output
        engine.write.assert_called_once_with(b"cd /tmp && ls -la")
