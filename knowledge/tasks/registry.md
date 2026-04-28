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
| `TASK-2026-0018` | `—` | `черновик` | `средний` | `main` | `knowledge/tasks/TASK-2026-0018-consumer-ux-and-localization/` | Потребительский UX и локализация клиента |
| `TASK-2026-0019` | `—` | `черновик` | `низкий` | `main` | `knowledge/tasks/TASK-2026-0019-deep-link-import/` | Deep link для импорта ссылок и подписок |
| `TASK-2026-0020` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0020-import-config-links/` | Импорт конфиг-ссылок из URL |
| `TASK-2026-0021` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0021-multi-profile-node-switching/` | Хранение нескольких профилей и быстрое переключение активного узла |
| `TASK-2026-0022` | `—` | `черновик` | `средний` | `main` | `knowledge/tasks/TASK-2026-0022-native-ui-gtk-direction/` | Следующий GUI-стек: GTK как основной путь, Tauri как отложенный fallback |
| `TASK-2026-0023` | `—` | `черновик` | `средний` | `main` | `knowledge/tasks/TASK-2026-0023-project-roadmap/` | Историческая дорожная карта проекта |
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
| `TASK-2026-0037` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0037-pure-xray-repo/` | Полная миграция репозитория на чистый `xray`, с одной рабочей web-GUI и сохранением импорта подписок по URL |
| `TASK-2026-0037.1` | `TASK-2026-0037` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0037-pure-xray-repo/subtasks/TASK-2026-0037.1-sidebar-navigation-fix/` | Упростить sidebar основной web-GUI и вернуть рабочую навигацию по пунктам меню |
| `TASK-2026-0037.2` | `TASK-2026-0037` | `завершена` | `высокий` | `—` | `knowledge/tasks/TASK-2026-0037-pure-xray-repo/subtasks/TASK-2026-0037.2-minimal-main-ui-refactor/` | Минималистичный рефакторинг основного web UI без постоянной боковой панели и с сохранением всех рабочих действий |
| `TASK-2026-0037.3` | `TASK-2026-0037` | `завершена` | `высокий` | `—` | `knowledge/tasks/TASK-2026-0037-pure-xray-repo/subtasks/TASK-2026-0037.3-fullscreen-operational-ui/` | Полноэкранный operational UI без вертикальной прокрутки страницы, с подписками, узлами, ping и постоянным логом |
| `TASK-2026-0037.4` | `TASK-2026-0037` | `завершена` | `высокий` | `—` | `knowledge/tasks/TASK-2026-0037-pure-xray-repo/subtasks/TASK-2026-0037.4-runtime-toolbar-feedback-round-2/` | Доработка верхней панели и баннера ошибок по новому скриншотному фидбеку |
| `TASK-2026-0038` | `—` | `завершена` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0038-embedded-webview-launcher/` | Перевести запуск GUI из внешнего браузера во встроенное окно на `Python + GTK + WebKitGTK` с fallback на браузер |
| `TASK-2026-0039` | `—` | `завершена` | `высокий` | `—` | `knowledge/tasks/TASK-2026-0039-production-bundle-sync-script/` | Добавить поддерживаемый deploy-скрипт для установки или обновления bundle-каталога и обновить production-копию |
| `TASK-2026-0040` | `—` | `завершена` | `средний` | `—` | `knowledge/tasks/TASK-2026-0040-anime-tech-icon/` | Обновить иконку bundle на простую техно-эмблему в логике типовых VPN-образов без смены текущего SVG-пути |
| `TASK-2026-0041` | `—` | `ждёт пользователя` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0041-public-repo-preparation/` | Подготовить репозиторий к публичной публикации, очистить Git от приватных артефактов и собрать public-facing repo hygiene |
| `TASK-2026-0042` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0042-webview-nvidia-software-fallback/` | Аппаратно-независимый software-rendering fallback для embedded webview вместо хрупкого GPU/GBM-пути |
| `TASK-2026-0043` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0043-gui-user-backend-pkexec-actions/` | Запуск GUI без раннего root-запроса и перенос root-действий GUI на `pkexec` |
| `TASK-2026-0044` | `—` | `на проверке` | `средний` | `main` | `knowledge/tasks/TASK-2026-0044-main-window-width-reduction/` | Уменьшить стартовую ширину главного окна до `1280` px, убрать боковые поля и снять регрессии верхней панели и мерцание embedded GUI |
| `TASK-2026-0045` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0045-ui-window-close-full-shutdown/` | Сделать закрытие GUI-окна полным shutdown приложения: окно, GUI-backend и VPN runtime должны останавливаться одним сценарием |
| `TASK-2026-0046` | `—` | `на проверке` | `средний` | `main` | `knowledge/tasks/TASK-2026-0046-desktop-icon-local-assets/` | Убрать абсолютный путь из `Icon=` в desktop launcher и перейти на локальный `assets` через user-local icon theme lookup |
| `TASK-2026-0047` | `—` | `завершена` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0047-runtime-ownership-isolation/` | Изолировать ownership runtime между копиями bundle, чтобы UI и stop-сценарии не останавливали чужой VPN runtime |
| `TASK-2026-0048` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0048-routing-profiles-minimal-happ-compat/` | Добавить упрощённые routing-профили по модели Happ: импорт, один активный профиль, geodata и применение в `Xray` |
| `TASK-2026-0048.1` | `TASK-2026-0048` | `на проверке` | `средний` | `main` | `knowledge/tasks/TASK-2026-0048-routing-profiles-minimal-happ-compat/subtasks/TASK-2026-0048.1-routing-auto-fetch-from-subscription/` | Автоматически получать routing-профиль из подписки через `routing` metadata и `providerId`, связывать auto-managed профиль с подпиской и чистить stale state |
| `TASK-2026-0049` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0049-gui-launcher-auto-port-fallback/` | Исключить конфликт GUI backend-а между production bundle и запуском GUI из репозитория: если базовый порт GUI занят несовместимым процессом, launcher должен выбрать свободный fallback-порт и открыть интерфейс на нём. |
| `TASK-2026-0050` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0050-web-gui-rescue-shutdown-and-layout/` | Починить web GUI после чёрного экрана: GUI-only shutdown, browser fallback для ярлыка и исправление layout routing-блока |
| `TASK-2026-0051` | `—` | `завершена` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0051-legacy-state-recovery/` | Убрать тупик stale legacy state без bundle identity, который блокирует и `run`, и `stop` |
| `TASK-2026-0052` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0052-web-ui-sidebar-navigation/` | Перепроектировать web UI: главный экран для подключения, служебные routing/log разделы через sidebar |
| `TASK-2026-0053` | `—` | `завершена` | `высокий` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/` | Закрытый этап отдельного нативного GTK4-интерфейса для bundle: service-layer, `Dashboard`, `Subscriptions`, `Log` и тестовый launcher |
| `TASK-2026-0053.1` | `TASK-2026-0053` | `завершена` | `высокий` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/` | Каркас нативного GTK4-окна, системный трей и минимальное окно настроек |
| `TASK-2026-0053.1.1` | `TASK-2026-0053.1` | `завершена` | `средний` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.1-gtk4-shell-tray-and-settings-shell/subtasks/TASK-2026-0053.1.1-raycast-dark-ui-contract/` | Raycast-ориентированный dark UI-contract для GTK4 shell, tray, settings и основных экранов |
| `TASK-2026-0053.2` | `TASK-2026-0053` | `завершена` | `высокий` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.2-dashboard-and-shared-service-layer/` | Общий runtime/service-layer и рабочий `Dashboard` для native GTK4 shell без внутренних `HTTP` вызовов |
| `TASK-2026-0053.3` | `TASK-2026-0053` | `завершена` | `высокий` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.3-subscriptions-vertical-slice/` | Рабочий vertical slice native-экрана `Subscriptions`: URL-подписки, узлы, отдельный `ping` и routing-профили |
| `TASK-2026-0053.4` | `TASK-2026-0053` | `завершена` | `высокий` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.4-log-vertical-slice/` | Рабочий vertical slice native-экрана `Log`: уровневый фильтр, ошибки, разделение источников и copy/export видимого журнала |
| `TASK-2026-0053.5` | `TASK-2026-0053` | `завершена` | `средний` | `topic/gtk4-native-ui-spike` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.5-gtk-test-launcher/` | Отдельный launcher и menu-entry для ручного тестирования `GTK4` native UI без смены основного GUI по умолчанию |
| `TASK-2026-0053.6` | `TASK-2026-0053` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/subtasks/TASK-2026-0053.6-gtk4-compact-ux-defect-pass/` | Компактный GTK4 UX-pass заморожен как fallback-кандидат: `Dashboard` получил master-`CTA`, UI локализован, а живой smoke остаётся отдельной проверкой возврата |
| `TASK-2026-0054` | `—` | `на проверке` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0054-full-ui-redesign/` | Полированный `GTK4` layout под фиксированное `1280×960` после review defect-pass: runtime-aware кнопка `Подключиться / Отключиться`, таймер в status-row и отдельная подписка; затем с главной вкладки убраны технический блок `Интерфейс` и нижняя карточка `Объём данных`, а `TUN`/`DNS` перенесены в `Диагностику`, скорость и объём объединены в верхнем traffic-pill, карточки узлов текущей подписки переехали на `Подключение` в фиксированную сетку `4×N`, выбор узла переведён на клик по карточке без отдельной кнопки, `Пинг` поднят в строку чипов для уменьшения высоты карточки, вкладка `Подписки` получила постоянно раскрытую маршрутизацию, а emoji-флаги убраны из UI-имён узлов, дальше нужен живой smoke против `TASK-2026-0053.6` |
| `TASK-2026-0055` | `—` | `завершена` | `средний` | `task/task-2026-0054-full-ui-redesign` | `knowledge/tasks/TASK-2026-0055-main-icon-eye-target/` | Основная `SVG`-иконка bundle заменена на eye-target вариант по прежнему пути `assets/subvost-xray-tun-icon.svg`; launcher и favicon сохранены совместимыми, а desktop sync дополнен refresh `icon-theme.cache` и invalidation preview для `Thunar` |
| `TASK-2026-0056` | `—` | `завершена` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0056-foreign-stale-state-recovery/` | Перевести владельца подключения с абсолютного пути на стабильный `install-id` установки |
| `TASK-2026-0057` | `—` | `завершена` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0057-stale-state-artifacts-control/` | Контроль stale-state и служебных артефактов без скрытого накопления мусора |
| `TASK-2026-0058` | `—` | `ждёт пользователя` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0058-win81-native-windows-port/` | Довести Windows 8.1 порт до проверенной поставки с нативным Windows UI, build scripts, runtime hardening и beginner README |
| `TASK-2026-0058.1` | `TASK-2026-0058` | `завершена` | `высокий` | `task/task-2026-0058-win81-native-windows-port` | `knowledge/tasks/TASK-2026-0058-win81-native-windows-port/subtasks/TASK-2026-0058.1-win81-release-package-and-build-chain/` | Сборочная цепочка, preflight, зависимости, pin/checksum runtime-бинарников и release-package layout |
| `TASK-2026-0058.2` | `TASK-2026-0058` | `завершена` | `высокий` | `task/task-2026-0058-win81-native-windows-port` | `knowledge/tasks/TASK-2026-0058-win81-native-windows-port/subtasks/TASK-2026-0058.2-native-windows-ui-shell/` | Нативный Windows UI без браузера: выбор стека, shell-контракт и первый рабочий vertical slice |
| `TASK-2026-0058.3` | `TASK-2026-0058` | `завершена` | `высокий` | `task/task-2026-0058-win81-native-windows-port` | `knowledge/tasks/TASK-2026-0058-win81-native-windows-port/subtasks/TASK-2026-0058.3-windows-runtime-routing-hardening/` | Hardening Windows runtime: маршруты, state/log paths, кодировки, stale adapter и recovery |
| `TASK-2026-0058.4` | `TASK-2026-0058` | `ждёт пользователя` | `высокий` | `main` | `knowledge/tasks/TASK-2026-0058-win81-native-windows-port/subtasks/TASK-2026-0058.4-win81-verification-and-user-docs/` | Живой Windows 8.1 smoke, beginner README, troubleshooting и handoff-комплект |
| `TASK-2026-0059` | `—` | `завершена` | `средний` | `topic/task-centric-knowledge-upgrade` | `knowledge/tasks/TASK-2026-0059-task-centric-knowledge-upgrade/` | Безопасный upgrade task-centric knowledge-системы до текущего дистрибутива skill-а |
