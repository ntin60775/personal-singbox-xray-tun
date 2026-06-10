#!/usr/bin/env bash
# Thin wrapper — all runtime logic moved to subvostd Go binary.
# This script is invoked by pkexec and delegates to the Go backend.
set -euo pipefail

SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SUBVOST_PROJECT_ROOT="$PROJECT_ROOT"

source "${PROJECT_ROOT}/lib/subvost-common.sh"
subvost_export_project_layout

exec "${PROJECT_ROOT}/subvostd" --mode start
