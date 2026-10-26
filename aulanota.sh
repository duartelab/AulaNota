#!/usr/bin/env bash
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$RAIZ${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m aulanota "$@"
