"""
AlternateScreenDetector — detecta quando apps full-screen (vim, top, less)
ativam o alternate screen buffer via escape sequences ANSI.

Enquanto alternate screen está ativo, o NL Mode não deve tentar interceptar
a linha de input — apps full-screen gerenciam o terminal por conta própria.
"""
import re

# Escape sequences que ativam alternate screen buffer
_ENTER_PATTERNS = [
    re.compile(rb"\x1b\[\?1049h"),
    re.compile(rb"\x1b\[\?47h"),
]
# Escape sequences que desativam alternate screen buffer
_EXIT_PATTERNS = [
    re.compile(rb"\x1b\[\?1049l"),
    re.compile(rb"\x1b\[\?47l"),
]


class AlternateScreenDetector:
    """
    Monitora chunks de output do terminal e rastreia se o alternate screen
    buffer está ativo.

    Usa um contador de nível (depth) para lidar com apps que entram/saem
    múltiplas vezes antes de voltar ao buffer principal.
    """

    def __init__(self) -> None:
        self._depth: int = 0

    def feed(self, data: bytes) -> None:
        """Processar chunk de output e atualizar estado."""
        for pat in _ENTER_PATTERNS:
            self._depth += len(pat.findall(data))
        for pat in _EXIT_PATTERNS:
            exits = len(pat.findall(data))
            self._depth = max(0, self._depth - exits)

    def reset(self) -> None:
        """Resetar estado (ex: ao encerrar sessão)."""
        self._depth = 0

    @property
    def is_active(self) -> bool:
        """True se alternate screen buffer está ativo."""
        return self._depth > 0

    @property
    def nl_interception_allowed(self) -> bool:
        """True se NL Mode pode interceptar input (alternate screen inativo)."""
        return not self.is_active
