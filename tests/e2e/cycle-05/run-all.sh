#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; RESET='\033[0m'
pass() { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; }
info() { echo -e "${YELLOW}» $1${RESET}"; }
FAILURES=0
run_check() { local name="$1"; shift; if "$@"; then pass "${name}"; else fail "${name}"; FAILURES=$((FAILURES+1)); fi; }
echo ""; echo "╔══════════════════════════════════════════════╗"; echo "║   sym_shell — E2E Gate · cycle-05            ║"; echo "╚══════════════════════════════════════════════╝"; echo ""
info "1/3  Unit + Integration (regressão)"
run_check "unit + integration" python -m pytest tests/unit/ tests/integration/ -q --tb=short
echo ""
info "2/3  E2E anteriores (regressão)"
run_check "e2e cycle-01..04" python -m pytest tests/e2e/cycle-01/ tests/e2e/cycle-02/ tests/e2e/cycle-03/ tests/e2e/cycle-04/ -q --tb=short
echo ""
info "3/3  cycle-05: NL loop wired + config default + startup hint"
run_check "cycle-05 unit" python -m pytest tests/unit/test_c5t01_intercept_result_handling.py tests/unit/test_c5t02_startup_config.py -q --tb=short
echo ""; echo "══════════════════════════════════════════════"
if [[ ${FAILURES} -eq 0 ]]; then pass "E2E Gate PASSED — cycle-05 encerrado (NL loop demonstrável)"; echo ""; exit 0
else fail "E2E Gate FAILED — ${FAILURES} check(s) falharam"; exit 1; fi
