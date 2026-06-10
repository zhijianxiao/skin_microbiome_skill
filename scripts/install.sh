#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="skin_microbiome"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Creating Conda environment: ${ENV_NAME}"
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "    Environment '${ENV_NAME}' already exists, skipping creation."
else
    conda create -n "${ENV_NAME}" python=3.10 -y
fi

echo "==> Activating environment and installing dependencies"
eval "$(conda shell.bash hook)"
conda activate "${ENV_NAME}"
pip install --upgrade pip
pip install -r "${PROJECT_DIR}/requirements.txt"
pip install -e "${PROJECT_DIR}"

echo ""
echo "==> Checking external tools in PATH"

check_tool() {
    local tool="$1"
    if command -v "${tool}" &> /dev/null; then
        echo "    [OK] ${tool} found: $(command -v "${tool}")"
    else
        echo "    [WARN] ${tool} not found in PATH. Please install it manually if needed."
    fi
}

check_tool "fastq-dump"       # sra-tools
check_tool "enaBrowserTools"  # enaBrowserTools (enaDataGet / enaGroupGet)

echo ""
echo "==> Installation complete."
echo "Activate with: conda activate ${ENV_NAME}"
echo "Run: skinmicrobiome"
