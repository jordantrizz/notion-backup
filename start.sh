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
  env           Create the virtual environment if needed and print the command
                to activate it. Run 'eval "$(./start.sh env)"' to activate
                the venv in your current shell, then run 'python3 main.py'.
  (none)        Create the virtual environment if needed, then run 'main.py'
                with any remaining arguments.

Examples:
  ./start.sh
  ./start.sh --debug backup
  eval "$(./start.sh env)"
EOF
}

setup_env() {
    # Install dependencies only when constructing the environment; routine
    # backups should not silently resolve new package versions from the network.
    if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
        "${PYTHON_BIN}" -m venv "${VENV_DIR}" >&2
        "${VENV_DIR}/bin/python" -m pip install -r requirements.txt >&2
    fi
}

case "${1:-}" in
    -h|--help)
        usage
        ;;
    env)
        setup_env
        # stdout is reserved for shell code because callers evaluate it;
        # human-readable status remains on stderr.
        printf 'source %q\n' "${VENV_DIR}/bin/activate"
        echo "Virtual environment ready at ${VENV_DIR}" >&2
        ;;
    *)
        setup_env
        exec "${VENV_DIR}/bin/python" main.py "$@"
        ;;
esac
