#!/usr/bin/env bash
# scripts/build.sh — Build pipeline sym_shell (T-43)
#
# Gera binário standalone Linux usando PyInstaller.
# Uso: ./scripts/build.sh [--clean]
#
# Saída: dist/sym_shell (binário standalone)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "[build] sym_shell — PyInstaller build"
echo "[build] Diretório: ${REPO_ROOT}"

# Limpar build anterior se solicitado
if [[ "${1:-}" == "--clean" ]]; then
    echo "[build] Limpando build anterior..."
    rm -rf build/ dist/ __pycache__/
fi

# Verificar se pyinstaller está disponível
if ! command -v pyinstaller &>/dev/null; then
    echo "[build] ERRO: pyinstaller não encontrado. Instale com: pip install pyinstaller"
    exit 1
fi

echo "[build] Executando PyInstaller..."
pyinstaller sym_shell.spec --noconfirm

echo "[build] Build concluído!"
echo "[build] Binário: ${REPO_ROOT}/dist/sym_shell"

# Verificar tamanho do binário
if [[ -f "dist/sym_shell" ]]; then
    SIZE=$(du -sh dist/sym_shell | cut -f1)
    echo "[build] Tamanho: ${SIZE}"
fi
