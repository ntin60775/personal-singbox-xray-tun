#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP_TIMEOUT_SEC="${PWCLI_BOOTSTRAP_TIMEOUT_SEC:-20}"
ALLOW_CODEX_SANDBOX="${PWCLI_ALLOW_CODEX_SANDBOX:-0}"

stderr() {
  printf '%s\n' "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

is_meta_command() {
  local arg="${1:-}"
  case "$arg" in
    ""|-h|--help|help|doctor|version|--version)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

running_in_codex_sandbox() {
  local proc1_comm proc1_cmdline

  if [[ ! -r /proc/1/comm || ! -r /proc/1/cmdline ]]; then
    return 1
  fi

  proc1_comm="$(cat /proc/1/comm 2>/dev/null || true)"
  [[ "${proc1_comm}" == "bwrap" ]] || return 1

  proc1_cmdline="$(tr '\0' ' ' </proc/1/cmdline 2>/dev/null || true)"
  [[ "${proc1_cmdline}" == *"codex-linux-sandbox"* ]]
}

print_install_help() {
  stderr "Playwright CLI недоступен локально."
  stderr "Wrapper сначала ищет глобальный или project-local playwright-cli,"
  stderr "потом офлайн-кэш npm, и только в конце пытается сделать сетевой bootstrap."
  stderr
  stderr "Как исправить это один раз:"
  stderr "  1. Вне Codex sandbox выполните: npm install -g @playwright/cli@latest"
  stderr "  2. Либо добавьте project-local dependency с бинарём playwright-cli."
  stderr "  3. Затем проверьте: playwright-cli --help"
}

print_wrapper_help() {
  cat <<'EOF'
Playwright wrapper usage:
  playwright_cli.sh doctor
  playwright_cli.sh open https://example.com --headed
  playwright_cli.sh snapshot
  playwright_cli.sh click e12

Что делает wrapper:
  - ищет глобальный playwright-cli;
  - ищет project-local ./node_modules/.bin/playwright-cli;
  - использует офлайн-кэш npm для @playwright/cli, если он есть;
  - не зависает бесконечно на сетевом bootstrap;
  - блокирует browser-level команды в Codex sandbox, если не задан PWCLI_ALLOW_CODEX_SANDBOX=1.

Полезные переменные:
  PWCLI_ALLOW_CODEX_SANDBOX=1   сознательно попробовать запуск из sandbox
  PWCLI_BOOTSTRAP_TIMEOUT_SEC   таймаут сетевого bootstrap, по умолчанию 20
  PLAYWRIGHT_CLI_SESSION        дефолтная именованная сессия
  PWCLI_DOCTOR_STRICT=1         вернуть ненулевой код при проблемах в doctor
EOF
}

offline_pwcli_available() {
  have_cmd npx || return 1
  npx --offline --yes --package @playwright/cli playwright-cli --help >/dev/null 2>&1
}

append_session_args() {
  local has_session_flag="false"
  local -a result=()

  while (($#)); do
    case "$1" in
      --session)
        has_session_flag="true"
        if (($# < 2)); then
          stderr "Флаг --session требует значение."
          return 1
        fi
        result+=("-s=$2")
        shift 2
        ;;
      --session=*)
        has_session_flag="true"
        result+=("-s=${1#--session=}")
        shift
        ;;
      -s)
        has_session_flag="true"
        if (($# < 2)); then
          stderr "Флаг -s требует значение."
          return 1
        fi
        result+=("-s=$2")
        shift 2
        ;;
      -s=*)
        has_session_flag="true"
        result+=("$1")
        shift
        ;;
      *)
        result+=("$1")
        shift
        ;;
    esac
  done

  if [[ "${has_session_flag}" != "true" && -n "${PLAYWRIGHT_CLI_SESSION:-}" ]]; then
    result=("-s=${PLAYWRIGHT_CLI_SESSION}" "${result[@]}")
  fi

  printf '%s\0' "${result[@]}"
}

run_doctor() {
  local status=0
  local global_pwcli="missing"
  local local_pwcli="missing"
  local offline_cache="missing"
  local sandbox="no"
  local network="enabled"

  if ! have_cmd node; then
    stderr "node: missing"
    status=1
  else
    stderr "node: $(command -v node) ($(node --version))"
  fi

  if ! have_cmd npm; then
    stderr "npm: missing"
    status=1
  else
    stderr "npm: $(command -v npm) ($(npm --version))"
  fi

  if ! have_cmd npx; then
    stderr "npx: missing"
    status=1
  else
    stderr "npx: $(command -v npx) ($(npx --version))"
  fi

  if have_cmd playwright-cli; then
    global_pwcli="$(command -v playwright-cli)"
  fi
  stderr "global playwright-cli: ${global_pwcli}"

  if [[ -x "./node_modules/.bin/playwright-cli" ]]; then
    local_pwcli="./node_modules/.bin/playwright-cli"
  fi
  stderr "project-local playwright-cli: ${local_pwcli}"

  if have_cmd npx && offline_pwcli_available; then
    offline_cache="available"
  fi
  stderr "offline npm cache for @playwright/cli: ${offline_cache}"

  if running_in_codex_sandbox; then
    sandbox="yes"
    status=1
  fi
  stderr "codex sandbox detected: ${sandbox}"

  if [[ "${CODEX_SANDBOX_NETWORK_DISABLED:-0}" == "1" ]]; then
    network="disabled"
  fi
  stderr "network bootstrap from current shell: ${network}"

  if [[ -n "${DISPLAY:-}" ]]; then
    stderr "DISPLAY: ${DISPLAY}"
  else
    stderr "DISPLAY: missing"
  fi

  if [[ "${global_pwcli}" == "missing" && "${local_pwcli}" == "missing" && "${offline_cache}" == "missing" ]]; then
    status=1
    stderr
    print_install_help
  fi

  if [[ "${sandbox}" == "yes" ]]; then
    stderr
    stderr "Browser-level команды из текущего Codex sandbox лучше не запускать:"
    stderr "они либо не стартуют, либо падают на launch."
    stderr "Запускайте Codex с --sandbox danger-full-access,"
    stderr "либо установите PWCLI_ALLOW_CODEX_SANDBOX=1, если хотите сознательно попробовать."
  fi

  stderr
  if [[ "${status}" == "0" ]]; then
    stderr "doctor result: ready"
  else
    stderr "doctor result: not ready"
  fi

  if [[ "${PWCLI_DOCTOR_STRICT:-0}" == "1" ]]; then
    return "${status}"
  fi

  return 0
}

resolve_runner() {
  local probe_status

  if have_cmd playwright-cli; then
    RUNNER=(playwright-cli)
    return 0
  fi

  if [[ -x "./node_modules/.bin/playwright-cli" ]]; then
    RUNNER=("./node_modules/.bin/playwright-cli")
    return 0
  fi

  if ! have_cmd npx; then
    stderr "npx недоступен, а локальный playwright-cli не найден."
    print_install_help
    return 1
  fi

  if offline_pwcli_available; then
    RUNNER=(npx --offline --yes --package @playwright/cli playwright-cli)
    return 0
  fi

  if [[ "${CODEX_SANDBOX_NETWORK_DISABLED:-0}" == "1" ]]; then
    stderr "Сетевой bootstrap @playwright/cli в текущем shell отключён."
    print_install_help
    return 1
  fi

  if ! have_cmd timeout; then
    stderr "Команда timeout недоступна, поэтому безопасный сетевой bootstrap невозможен."
    print_install_help
    return 1
  fi

  if timeout "${BOOTSTRAP_TIMEOUT_SEC}s" npx --yes --package @playwright/cli playwright-cli --help >/dev/null 2>&1; then
    RUNNER=(npx --yes --package @playwright/cli playwright-cli)
    return 0
  fi

  probe_status=$?
  if [[ "${probe_status}" == "124" ]]; then
    stderr "Bootstrap @playwright/cli через npx превысил ${BOOTSTRAP_TIMEOUT_SEC}s."
  else
    stderr "Bootstrap @playwright/cli через npx завершился ошибкой (${probe_status})."
  fi
  print_install_help
  return 1
}

main() {
  local primary_arg="${1:-}"
  local -a args
  local runner_status

  if [[ "${primary_arg}" == "doctor" ]]; then
    shift
    run_doctor "$@"
    exit $?
  fi

  if [[ "${primary_arg}" == "-h" || "${primary_arg}" == "--help" || "${primary_arg}" == "help" ]]; then
    print_wrapper_help
    exit 0
  fi

  if ! is_meta_command "${primary_arg}" && running_in_codex_sandbox && [[ "${ALLOW_CODEX_SANDBOX}" != "1" ]]; then
    stderr "Browser-level Playwright команды заблокированы в текущем Codex sandbox."
    stderr "Это сделано намеренно, чтобы не зависать на bootstrap и не падать на browser launch."
    stderr "Решение: перезапустите Codex с --sandbox danger-full-access."
    stderr "Если вы осознанно хотите всё равно попробовать, установите PWCLI_ALLOW_CODEX_SANDBOX=1."
    exit 1
  fi

  mapfile -d '' args < <(append_session_args "$@")
  unset PLAYWRIGHT_CLI_SESSION

  if ! resolve_runner; then
    runner_status=$?
    exit "${runner_status}"
  fi

  exec "${RUNNER[@]}" "${args[@]}"
}

main "$@"
