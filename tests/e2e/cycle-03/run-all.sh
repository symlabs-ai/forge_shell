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
echo ""; echo "╔══════════════════════════════════════════════╗"; echo "║   forge_shell — E2E Gate · cycle-03            ║"; echo "╚══════════════════════════════════════════════╝"; echo ""
info "1/3  Unit + Integration (regressão)"
run_check "unit + integration" python -m pytest tests/unit/ tests/integration/ -q --tb=short
echo ""
info "2/3  E2E anteriores (regressão)"
run_check "e2e cycle-01+02" python -m pytest tests/e2e/cycle-01/ tests/e2e/cycle-02/ -q --tb=short
echo ""
info "3/3  Smoke: relay WebSocket + NL interceptor"
run_check "relay + nl smoke" python -m pytest tests/integration/test_c3t01_t03_relay_websocket.py tests/unit/test_c3t06_nl_smoke_attach.py tests/unit/test_c3t05_install_smoke.py -q --tb=short
echo ""; echo "══════════════════════════════════════════════"
if [[ ${FAILURES} -eq 0 ]]; then pass "E2E Gate PASSED — cycle-03 pode ser encerrado"; echo ""; exit 0
else fail "E2E Gate FAILED — ${FAILURES} check(s) falharam"; exit 1; fi
