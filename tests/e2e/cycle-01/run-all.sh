#!/usr/bin/env bash
# tests/e2e/cycle-01/run-all.sh — E2E Gate cycle-01 (ft.e2e.01.cli_validation)
#
# Critério de saída: exit 0 somente se TODOS os checks passarem.
# Uso: ./tests/e2e/cycle-01/run-all.sh [--save-results]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="${RESULTS_DIR}/e2e_${TIMESTAMP}.log"

cd "${REPO_ROOT}"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

pass() { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; }
info() { echo -e "${YELLOW}» $1${RESET}"; }

FAILURES=0

run_check() {
    local name="$1"
    shift
    if "$@" ; then
        pass "${name}"
    else
        fail "${name}"
        FAILURES=$((FAILURES + 1))
    fi
}

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   sym_shell — E2E Gate · cycle-01            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Suite de testes unitários ──────────────────
info "1/4  Unit tests"
run_check "unit tests (154+ passing)" \
    python -m pytest tests/unit/ -q --tb=short 2>&1 | tee -a "${RESULTS_FILE}"

echo ""

# ── 2. Suite de testes de integração ──────────────
info "2/4  Integration tests"
run_check "integration tests (PTY)" \
    python -m pytest tests/integration/ -q --tb=short 2>&1 | tee -a "${RESULTS_FILE}"

echo ""

# ── 3. E2E CLI validation ──────────────────────────
info "3/4  E2E CLI + imports"
run_check "e2e cli + module imports" \
    python -m pytest tests/e2e/cycle-01/test_e2e_cli.py -q --tb=short 2>&1 | tee -a "${RESULTS_FILE}"

echo ""

# ── 4. E2E PTY + Doctor smoke ──────────────────────
info "4/4  E2E PTY smoke + Doctor"
run_check "e2e pty smoke + doctor" \
    python -m pytest tests/e2e/cycle-01/test_e2e_pty_smoke.py tests/e2e/cycle-01/test_e2e_doctor.py -q --tb=short 2>&1 | tee -a "${RESULTS_FILE}"

echo ""
echo "══════════════════════════════════════════════"

if [[ ${FAILURES} -eq 0 ]]; then
    pass "E2E Gate PASSED — cycle-01 pode ser encerrado"
    echo ""
    exit 0
else
    fail "E2E Gate FAILED — ${FAILURES} check(s) falharam"
    echo ""
    echo "  Resultados salvos em: ${RESULTS_FILE}"
    exit 1
fi
