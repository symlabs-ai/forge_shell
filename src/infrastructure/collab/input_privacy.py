"""
InputPrivacyFilter — T-34.

Garante que input do usuário não seja transmitido para o relay
quando o echo está desativado (ex.: digitação de senha).

Detecta \x1b[8m (concealer ANSI / echo-off indicator) e \x1b[0m (reset).
"""
from __future__ import annotations

import re

# Sequência ANSI que oculta texto (conceal) — usada por bash ao ler senhas
_ANSI_CONCEAL = re.compile(rb"\x1b\[8m")
_ANSI_RESET = re.compile(rb"\x1b\[0m")


class InputPrivacyFilter:
    """
    Filtra transmissão de input baseado no estado de echo do terminal.

    Quando echo está desativado (senha sendo digitada), bloqueia transmissão.
    """

    def __init__(self) -> None:
        self._echo_enabled: bool = True
        self._concealed: bool = False

    def set_echo(self, enabled: bool) -> None:
        """Definir estado de echo explicitamente."""
        self._echo_enabled = enabled

    def process_output(self, data: bytes) -> None:
        """
        Analisar output do PTY para detectar mudanças de estado de echo.
        Chamar com cada chunk de output antes de transmitir.
        """
        if _ANSI_CONCEAL.search(data):
            self._concealed = True
        if _ANSI_RESET.search(data):
            self._concealed = False

    def should_transmit(self, input_data: bytes) -> bool:
        """True se o input pode ser transmitido para o relay."""
        if self._concealed:
            return False
        return self._echo_enabled
