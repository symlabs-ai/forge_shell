"""
DoctorRunner — T-42.

Executa diagnóstico da engine sym_shell:
- PTY: consegue criar master/slave?
- termios: consegue ler attrs do stdin?
- resize: consegue fazer ioctl TIOCSWINSZ?
- signals: SIGWINCH está disponível?
"""
from __future__ import annotations

import fcntl
import os
import pty
import signal
import struct
import sys
import termios
from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class DoctorReport:
    checks: dict[str, CheckStatus] = field(default_factory=dict)

    @property
    def overall(self) -> CheckStatus:
        statuses = list(self.checks.values())
        if CheckStatus.FAIL in statuses:
            return CheckStatus.FAIL
        if CheckStatus.WARN in statuses:
            return CheckStatus.WARN
        return CheckStatus.OK

    def to_text(self) -> str:
        lines = ["sym_shell doctor — diagnóstico da engine", ""]
        for name, status in self.checks.items():
            icon = {"ok": "✓", "warn": "⚠", "fail": "✗"}.get(status.value, "?")
            lines.append(f"  {icon} {name:<12} {status.value.upper()}")
        lines.append("")
        lines.append(f"  Overall: {self.overall.value.upper()}")
        return "\n".join(lines)


class DoctorRunner:
    """Executa todos os checks de diagnóstico e retorna DoctorReport."""

    def run(self) -> DoctorReport:
        report = DoctorReport()
        report.checks["pty"] = self._check_pty()
        report.checks["termios"] = self._check_termios()
        report.checks["resize"] = self._check_resize()
        report.checks["signals"] = self._check_signals()
        return report

    def _check_pty(self) -> CheckStatus:
        try:
            master_fd, slave_fd = pty.openpty()
            os.close(slave_fd)
            os.close(master_fd)
            return CheckStatus.OK
        except OSError:
            return CheckStatus.FAIL

    def _check_termios(self) -> CheckStatus:
        try:
            fd = sys.__stdin__.fileno()
            termios.tcgetattr(fd)
            return CheckStatus.OK
        except (AttributeError, termios.error, Exception):
            return CheckStatus.WARN  # warn: sem TTY real (ex.: CI), não é falha crítica

    def _check_resize(self) -> CheckStatus:
        try:
            master_fd, slave_fd = pty.openpty()
            winsize = struct.pack("HHHH", 24, 80, 0, 0)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
            os.close(slave_fd)
            os.close(master_fd)
            return CheckStatus.OK
        except OSError:
            return CheckStatus.FAIL

    def _check_signals(self) -> CheckStatus:
        try:
            # verifica se SIGWINCH está disponível (sempre True em Unix)
            _ = signal.SIGWINCH
            return CheckStatus.OK
        except AttributeError:
            return CheckStatus.FAIL
