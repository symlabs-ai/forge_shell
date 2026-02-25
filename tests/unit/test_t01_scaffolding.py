"""
T-01 — Scaffolding: estrutura de pacotes
DADO a estrutura do projeto sym_shell
QUANDO importo os pacotes principais
ENTÃO todos existem e são importáveis sem erro
"""
import importlib
import pytest


EXPECTED_PACKAGES = [
    "src",
    "src.domain",
    "src.domain.entities",
    "src.domain.value_objects",
    "src.application",
    "src.application.usecases",
    "src.application.ports",
    "src.application.dtos",
    "src.infrastructure",
    "src.infrastructure.terminal_engine",
    "src.infrastructure.intelligence",
    "src.infrastructure.collab",
    "src.infrastructure.audit",
    "src.infrastructure.config",
    "src.adapters",
    "src.adapters.cli",
    "src.adapters.event_bus",
]


@pytest.mark.parametrize("package", EXPECTED_PACKAGES)
def test_package_is_importable(package: str) -> None:
    """Cada pacote deve ser importável sem erro."""
    mod = importlib.import_module(package)
    assert mod is not None
