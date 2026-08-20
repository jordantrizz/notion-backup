#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${SCRIPT_DIR}"

usage() {
    cat <<'EOF'
Usage: ./start.sh [OPTIONS] [COMMAND] [ARGS...]

Bootstrap the Python virtual environment and run the Notion Backup CLI.

Options:
  -h, --help    Show this help message and exit

Commands:
  env           Create/update the virtual environment and open a shell with
                it activated, so you can run 'python3 main.py' directly.
  (none)        Create/update the virtual environment, then run 'main.py'
                with any remaining arguments.

Examples:
  ./start.sh
  ./start.sh --debug backup
  ./start.sh env
EOF
}

setup_env() {
    if [[ ! -d "${VENV_DIR}" ]]; then
        "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    fi
    "${VENV_DIR}/bin/python" -m pip install --upgrade pip
    "${VENV_DIR}/bin/python" -m pip install -r requirements.txt
}

case "${1:-}" in
    -h|--help)
        usage
        ;;
    env)
        setup_env
        echo "Virtual environment ready at ${VENV_DIR}"
        echo "Opening a shell with the environment activated..."
        if [[ "${SHELL}" == *zsh ]]; then
            exec zsh -c "source '${VENV_DIR}/bin/activate' && exec zsh"
        else
            exec bash -c "source '${VENV_DIR}/bin/activate' && exec bash"
        fi
        ;;
    *)
        setup_env
        exec "${VENV_DIR}/bin/python" main.py "$@"
        ;;
esac
