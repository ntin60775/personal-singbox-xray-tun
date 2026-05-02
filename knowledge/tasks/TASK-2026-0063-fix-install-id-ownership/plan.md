# План задачи TASK-2026-0063: fix-install-id-ownership

## 1. Анализ текущего кода

- [x] Проверить `lib/subvost-common.sh` — функция `subvost_ensure_install_id()` (строка 111)
- [x] Проверить `gui/subvost_app_service.py` — функция `ensure_bundle_install_id()` (строка 160)
- [x] Проверить наличие helper для определения реального пользователя (`subvost_resolve_real_user_name` в shell, `discover_real_user` в Python)

## 2. Исправление shell-уровня

- [x] В `lib/subvost-common.sh` в `subvost_ensure_install_id()`:
  - После создания файла выполнён `chown` на реального пользователя (`subvost_resolve_real_user_name`)
  - Каталог `.subvost` тоже получает корректного owner
- [x] Проверено, что `subvost_resolve_real_user_name()` возвращает корректное имя

## 3. Исправление Python-уровня

- [x] В `gui/subvost_app_service.py` в `ensure_bundle_install_id()`:
  - После создания файла выполнён `os.chown` с uid/gid реального пользователя
  - Использованы `discover_real_user()` и `pwd.getpwnam()`
- [x] Каталог `.subvost` тоже получает корректного owner и group

## 4. Preflight проверки

- [x] `bash -n lib/subvost-common.sh`
- [x] `python3 -m py_compile gui/subvost_app_service.py`

## 5. Ручной smoke-check

- [x] Удалить `.subvost` полностью
- [x] Запустить `./open-subvost-gtk-ui.sh` — GUI поднялось, `install-id` = `prog7:prog7`
- [x] Удалить `.subvost` полностью
- [x] Запустить `sudo bash -c '...subvost_ensure_install_id...'` — `install-id` = `prog7:root` (owner корректен)
- [x] Удалить `.subvost` полностью
- [x] Запустить `sudo python3 -c '...ensure_bundle_install_id...'` — `install-id` = `prog7:prog7`

## 6. Фиксация

- [x] Обновить `task.md` статусом и итогом
- [x] Сделать task-scoped commit
