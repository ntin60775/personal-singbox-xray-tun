#!/usr/bin/env bash
# Обертка: при ошибке запуска TUI оставляет терминал открытым
# с сообщением и ожиданием Enter, чтобы пользователь успел прочитать ошибку.
set -uo pipefail
# set -e убран намеренно: иначе при ненулевом коде целевого скрипта
# bash выйдет немедленно, не дав отработать read -r ниже.

SCRIPT_PATH="$1"
shift

bash "$SCRIPT_PATH" "$@"
exit_code=$?

if [[ $exit_code -ne 0 ]]; then
  echo
  echo "Ошибка запуска (код $exit_code). Нажмите Enter для закрытия..."
  read -r
fi

exit $exit_code
