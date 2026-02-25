#!/usr/bin/env bash
# tests/e2e/cycle-02/run-all.sh — E2E Gate cycle-02 (ft.e2e.01.cli_validation)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="${RESULTS_DIR}/e2e_${TIMESTAMP}.log"

cd "${REPO_ROOT}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; RESET='\033[0m'
pass() { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; }
info() { echo -e "${YELLOW}» $1${RESET}"; }
FAILURES=0

run_check() {
    local name="$1"; shift
    if "$@" >> "${RESULTS_FILE}" 2>&1; then
        pass "${name}"
    else
        fail "${name}"
        FAILURES=$((FAILURES + 1))
    fi
}

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   sym_shell — E2E Gate · cycle-02            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

info "1/4  Unit tests (all cycles)"
run_check "unit tests" python -m pytest tests/unit/ -q --tb=short

echo ""
info "2/4  Integration tests"
run_check "integration tests" python -m pytest tests/integration/ -q --tb=short

echo ""
info "3/4  E2E cycle-01 (regressão)"
run_check "e2e cycle-01" python -m pytest tests/e2e/cycle-01/ -q --tb=short

echo ""
info "4/4  E2E cycle-02 (wiring)"
run_check "e2e cycle-02 wiring" python -m pytest tests/e2e/cycle-02/test_e2e_wiring.py -q --tb=short

echo ""
echo "══════════════════════════════════════════════"

if [[ ${FAILURES} -eq 0 ]]; then
    pass "E2E Gate PASSED — cycle-02 pode ser encerrado"
    echo ""; exit 0
else
    fail "E2E Gate FAILED — ${FAILURES} check(s) falharam"
    echo "  Log: ${RESULTS_FILE}"; exit 1
fi
