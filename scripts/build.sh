#!/usr/bin/env bash
# scripts/build.sh — Build pipeline multi-target (T-43)
#
# Gera binários standalone Linux usando PyInstaller.
# Uso:
#   ./scripts/build.sh            Build todos (relay, host, shell)
#   ./scripts/build.sh relay      Build apenas forge_relay (~5MB)
#   ./scripts/build.sh host       Build apenas forge_host (~5MB)
#   ./scripts/build.sh shell      Build apenas forge_shell (~50MB)
#   ./scripts/build.sh --clean    Limpar + build todos

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

CLEAN=false
TARGETS=()

# Parse args
for arg in "$@"; do
    case "${arg}" in
        --clean)
            CLEAN=true
            ;;
        relay|host|shell)
            TARGETS+=("${arg}")
            ;;
        *)
            echo "[build] ERRO: argumento desconhecido: ${arg}"
            echo "[build] Uso: $0 [--clean] [relay|host|shell]"
            exit 1
            ;;
    esac
done

# Se nenhum target especificado, build todos
if [[ ${#TARGETS[@]} -eq 0 ]]; then
    TARGETS=(relay host shell)
fi

echo "[build] forge_shell — PyInstaller multi-target build"
echo "[build] Diretório: ${REPO_ROOT}"
echo "[build] Targets: ${TARGETS[*]}"

# Limpar build anterior se solicitado
if [[ "${CLEAN}" == true ]]; then
    echo "[build] Limpando build anterior..."
    rm -rf build/ dist/ __pycache__/
fi

# Verificar se pyinstaller está disponível
if ! command -v pyinstaller &>/dev/null; then
    echo "[build] ERRO: pyinstaller não encontrado. Instale com: pip install pyinstaller"
    exit 1
fi

# Build cada target
for target in "${TARGETS[@]}"; do
    case "${target}" in
        relay)
            echo "[build] === forge_relay ==="
            pyinstaller forge_relay.spec --noconfirm
            ;;
        host)
            echo "[build] === forge_host ==="
            pyinstaller forge_host.spec --noconfirm
            ;;
        shell)
            echo "[build] === forge_shell ==="
            pyinstaller forge_shell.spec --noconfirm
            ;;
    esac
done

echo "[build] Build concluído!"

# Verificar tamanho dos binários gerados
for target in "${TARGETS[@]}"; do
    binary="dist/forge_${target}"
    if [[ "${target}" == "shell" ]]; then
        binary="dist/forge_shell"
    fi
    if [[ -f "${binary}" ]]; then
        SIZE=$(du -sh "${binary}" | cut -f1)
        echo "[build] ${binary}: ${SIZE}"
    fi
done
