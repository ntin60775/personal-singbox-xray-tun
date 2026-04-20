#!/usr/bin/env bash
set -euo pipefail

WRAPPER_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${WRAPPER_DIR}/lib/subvost-common.sh"

PROJECT_ROOT="$(subvost_resolve_project_root_from_entrypoint "${BASH_SOURCE[0]}")"
subvost_export_project_layout "$PROJECT_ROOT"

exec "${SUBVOST_LIBEXEC_DIR}/update-xray-core-subvost.sh" "$@"
