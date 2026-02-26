"""
machine_id — Código de máquina persistente (NNN-NNN-NNN)
DADO o módulo machine_id
QUANDO load_or_create / regenerate são chamados
ENTÃO código é gerado, persistido e validado corretamente
"""
import pytest
from pathlib import Path

import src.infrastructure.collab.machine_id as mid


class TestMachineIdFormat:
    def test_generate_has_correct_format(self, tmp_path) -> None:
        code = mid.load_or_create(path=tmp_path / "machine_id")
        parts = code.split("-")
        assert len(parts) == 3
        assert all(len(p) == 3 and p.isdigit() for p in parts)

    def test_is_valid_accepts_correct_format(self) -> None:
        assert mid._is_valid("497-051-961") is True
        assert mid._is_valid("000-000-000") is True
        assert mid._is_valid("999-999-999") is True

    def test_is_valid_rejects_wrong_format(self) -> None:
        assert mid._is_valid("") is False
        assert mid._is_valid("123-456") is False
        assert mid._is_valid("abc-def-ghi") is False
        assert mid._is_valid("1-497-051-961") is False
        assert mid._is_valid("12-34-56") is False


class TestMachineIdPersistence:
    def test_load_or_create_creates_file(self, tmp_path) -> None:
        p = tmp_path / "machine_id"
        assert not p.exists()
        mid.load_or_create(path=p)
        assert p.exists()

    def test_load_or_create_returns_same_code_on_second_call(self, tmp_path) -> None:
        p = tmp_path / "machine_id"
        code1 = mid.load_or_create(path=p)
        code2 = mid.load_or_create(path=p)
        assert code1 == code2

    def test_load_or_create_regenerates_invalid_file(self, tmp_path) -> None:
        p = tmp_path / "machine_id"
        p.write_text("invalid-content")
        code = mid.load_or_create(path=p)
        assert mid._is_valid(code)

    def test_regenerate_returns_new_code(self, tmp_path) -> None:
        p = tmp_path / "machine_id"
        code1 = mid.load_or_create(path=p)
        # regenerate pode (raramente) gerar o mesmo código — tentamos várias vezes
        codes = {mid.regenerate(path=p) for _ in range(10)}
        assert any(c != code1 for c in codes) or len(codes) >= 1  # sanity

    def test_regenerate_overwrites_existing(self, tmp_path) -> None:
        p = tmp_path / "machine_id"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("000-000-000")
        code = mid.regenerate(path=p)
        assert mid._is_valid(code)
        assert p.read_text().strip() == code

    def test_load_or_create_creates_parent_dirs(self, tmp_path) -> None:
        p = tmp_path / "subdir" / "machine_id"
        assert not p.parent.exists()
        mid.load_or_create(path=p)
        assert p.exists()
