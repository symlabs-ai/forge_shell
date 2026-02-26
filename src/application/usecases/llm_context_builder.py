"""
LLMContextBuilder — constrói o contexto enviado ao ForgeLLM.

Inclui: pwd, últimas N linhas de output, último comando executado,
e variáveis de ambiente via whitelist (configurável em config.yaml).
"""
from __future__ import annotations

_DEFAULT_MAX_LINES = 20


class LLMContextBuilder:
    """Constrói dict de contexto para requisições NL."""

    def __init__(
        self,
        max_lines: int = _DEFAULT_MAX_LINES,
        env_whitelist: list[str] | None = None,
    ) -> None:
        self.max_lines = max_lines
        self._env_whitelist: list[str] = env_whitelist if env_whitelist is not None else []

    def build(
        self,
        cwd: str,
        last_lines: list[str],
        last_cmd: str,
        env: dict[str, str] | None = None,
    ) -> dict:
        truncated = last_lines[-self.max_lines:] if len(last_lines) > self.max_lines else last_lines

        ctx: dict = {
            "cwd": cwd,
            "last_cmd": last_cmd,
            "last_output": truncated,
        }

        if self._env_whitelist and env:
            ctx["env"] = {k: v for k, v in env.items() if k in self._env_whitelist}

        return ctx
