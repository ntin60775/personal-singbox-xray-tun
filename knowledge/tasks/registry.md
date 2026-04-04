# Реестр задач

Реестр нужен только для навигации.
Источником истины по каждой задаче остаётся файл `knowledge/tasks/<TASK-ID>-<slug>/task.md`.

## Как вести

- одна строка на одну задачу;
- одна строка на одну значимую подзадачу;
- для подзадачи указывать родительский `ID`;
- статус и краткое описание должны совпадать с `task.md`;
- если задача переименована, ссылка на каталог обновляется;
- если задача разбита на подзадачи, декомпозиция отражается через `Parent ID`.

## Таблица

| ID | Parent ID | Статус | Приоритет | Ветка | Каталог | Краткое описание |
|----|-----------|--------|-----------|-------|---------|------------------|
| `TASK-2026-0001` | `—` | `завершена` | `средний` | `main` | `knowledge/tasks/TASK-2026-0001-task-centric-knowledge-rollout/` | Развёртывание task-centric knowledge-системы и перевод workflow с `plans/` на `knowledge/tasks/` |
| `TASK-2026-0002` | `—` | `завершена` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0002-plans-to-knowledge-migration/` | Полная миграция legacy-планов из `plans/` в `knowledge/` и подготовка безопасного удаления каталога |
| `TASK-2026-0003` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0003-desktop-icon-self-sync/` | Синхронизация иконки desktop launcher |
| `TASK-2026-0004` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0004-desktop-menu-entry/` | Установка ярлыка bundle в меню приложений |
| `TASK-2026-0005` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0005-project-structure-cleanup/` | Приведение структуры bundle к управляемому layout |
| `TASK-2026-0006` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0006-review-followup-hardening/` | Доработка после ревью hardening-правок |
| `TASK-2026-0007` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0007-tun-hardening-from-report/` | Заимствования из `docs/research/deep-research-report.md` для hardening bundle |
| `TASK-2026-0008` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0008-xray-installer-dedup-cleanup/` | Дедупликация installer-а xray |
| `TASK-2026-0009` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0009-add-public-service-direct-exception/` | Добавить direct-исключение для public-service.example.com |
| `TASK-2026-0010` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0010-force-gui-backend-restart-on-shortcut-launch/` | Принудительный restart GUI backend при запуске через ярлык |
| `TASK-2026-0011` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0011-remove-global-ru-direct/` | Убрать глобальный direct для национальных доменов |
| `TASK-2026-0012` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0012-routing-diagnostics-for-subvost-vs-flclashx/` | Диагностика policy-маршрутизации для `subvost` против `FlClashX` |
| `TASK-2026-0013` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0013-sync-bundle-routing-fixes/` | Синхронизировать routing-правки из рабочего bundle |
| `TASK-2026-0014` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0014-add-direct-exceptions-for-private-rdp-and-lan/` | Добавить direct-исключения для `private-rdp` и локальной сети |
| `TASK-2026-0015` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0015-track-sanitized-xray-config/` | Добавление санитизированного xray-конфига в репозиторий |
| `TASK-2026-0016` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0016-update-finland-node-from-happ/` | Обновление Finland-узла из Happ для desktop bundle |
| `TASK-2026-0017` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0017-apply-happ-dns-profile/` | Взять DNS-часть из Happ routing profile |
| `TASK-2026-0018` | `—` | `черновик` | `средний` | `—` | `knowledge/tasks/TASK-2026-0018-consumer-ux-and-localization/` | Потребительский UX и локализация клиента |
| `TASK-2026-0019` | `—` | `черновик` | `низкий` | `—` | `knowledge/tasks/TASK-2026-0019-deep-link-import/` | Deep link для импорта ссылок и подписок |
| `TASK-2026-0020` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0020-import-config-links/` | Импорт конфиг-ссылок из URL |
| `TASK-2026-0021` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0021-multi-profile-node-switching/` | Хранение нескольких профилей и быстрое переключение активного узла |
| `TASK-2026-0022` | `—` | `черновик` | `средний` | `—` | `knowledge/tasks/TASK-2026-0022-native-ui-gtk-direction/` | Следующий GUI-стек: GTK как основной путь, Tauri как отложенный fallback |
| `TASK-2026-0023` | `—` | `черновик` | `средний` | `—` | `knowledge/tasks/TASK-2026-0023-project-roadmap/` | Историческая дорожная карта проекта |
| `TASK-2026-0024` | `—` | `отменена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0024-qr-import-share/` | QR import/share как secondary feature |
| `TASK-2026-0025` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0025-subscription-url-refresh/` | Импорт и обновление подписок по URL |
| `TASK-2026-0026` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0026-subscription-atomic-refresh-and-builtin-rollback/` | Атомарное обновление подписок и rollback на builtin |
| `TASK-2026-0027` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0027-subscription-delete-actions-fix/` | Исправление удаления подписок и row-actions в GUI |
| `TASK-2026-0028` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0028-ui-runtime-mode-polish/` | Полировка backend и web UI для подписок и runtime-режимов |
| `TASK-2026-0029` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0029-web-ui-redesign-options/` | Варианты полного редизайна web UI |
| `TASK-2026-0030` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0030-clash-candidate-feedback-round-1/` | Доработка Clash-кандидата по замечаниям со скриншота |
| `TASK-2026-0031` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0031-clash-reference-fullscreen-candidate/` | Полноэкранный Clash-референс для web UI |
| `TASK-2026-0032` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0032-gui-contract-version-sync/` | Синхронизация версии GUI-контракта между backend и launcher |
| `TASK-2026-0033` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0033-main-ui-functional-rebuild/` | Возврат рабочего web UI на основной маршрут |
| `TASK-2026-0034` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0034-promote-clash-ui-to-main/` | Перевод Clash-кандидата в основной web UI |
| `TASK-2026-0035` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0035-proxy-client-reference-ui/` | Редизайн review-экрана по референсам proxy-клиентов |
| `TASK-2026-0036` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0036-xray-core-only-runtime/` | Альтернативный TUN-runtime только на `xray-core` без обязательного `sing-box` |
| `TASK-2026-0037` | `—` | `на проверке` | `высокий` | `—` | `knowledge/tasks/TASK-2026-0037-pure-xray-repo/` | Полная миграция репозитория на чистый `xray`, с одной рабочей web-GUI и сохранением импорта подписок по URL |
