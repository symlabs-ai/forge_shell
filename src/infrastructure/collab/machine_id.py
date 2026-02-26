"""
machine_id — Código de máquina persistente para relay do sym_shell.

Formato : NNN-NNN-NNN  (ex: 497-051-961)
Arquivo : ~/.sym_shell/machine_id

O código é gerado uma vez e reutilizado em todas as sessões.
Só é regerado quando regenerate() é chamado explicitamente
(ex: sym_shell share --regen).
"""
from __future__ import annotations

import random
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".sym_shell" / "machine_id"


def _generate() -> str:
    """Gera um código no formato NNN-NNN-NNN."""
    return "-".join(f"{random.randint(0, 999):03d}" for _ in range(3))


def _is_valid(code: str) -> bool:
    """Valida formato NNN-NNN-NNN."""
    parts = code.split("-")
    if len(parts) != 3:
        return False
    return all(len(p) == 3 and p.isdigit() for p in parts)


def load_or_create(path: Path | None = None) -> str:
    """Carrega o machine_id do disco ou cria um novo."""
    p = path or _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        code = p.read_text(encoding="utf-8").strip()
        if _is_valid(code):
            return code
    code = _generate()
    p.write_text(code, encoding="utf-8")
    return code


def regenerate(path: Path | None = None) -> str:
    """Força a regeneração do machine_id."""
    p = path or _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    code = _generate()
    p.write_text(code, encoding="utf-8")
    return code
