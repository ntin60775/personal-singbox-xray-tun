# План задачи TASK-2026-0023

## Правило

Для задачи существует только один файл плана: `plan.md`.
Если задача декомпозируется, каждая подзадача получает свой собственный `plan.md` внутри своей папки.

## Паспорт плана

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0023` |
| Parent ID | `—` |
| Версия плана | `1` |
| Дата обновления | `2026-04-03` |

## Цель

Зафиксировать текущее состояние `personal-singbox-xray-tun`, перечислить уже реализованные этапы и определить очередность следующих доработок так, чтобы проект эволюционировал из переносимого operator-oriented bundle в полноценный Linux-native клиент под MX Linux / XFCE.

## Границы

### Входит

- исторический объём legacy-плана, сохранённого в `artifacts/legacy-plan.md`;
- сохранение исходного Markdown в `artifacts/legacy-plan.md`;
- приведение записи к task-centric структуре без потери контекста.

### Не входит

- новая реализация темы во время миграции;
- изменение исторического статуса legacy-задачи.

## Планируемые изменения

### Код

- содержание legacy-плана сохранено без переписывания; детали см. в историческом блоке ниже и в `artifacts/legacy-plan.md`.

### Конфигурация / схема данных / именуемые сущности

- при наличии изменений они описаны в историческом блоке ниже и в `artifacts/legacy-plan.md`.

### Документация

- task-centric карточка и план созданы в `knowledge/tasks/TASK-2026-0023-project-roadmap/`.

## Риски и зависимости

- legacy-план мог использовать ссылки удалённого legacy-контура; они сохраняются как исторический контекст внутри `artifacts/legacy-plan.md`.
- продолжение этой темы, если оно потребуется, должно идти уже из knowledge-системы через отдельные task-каталоги, а не через восстановление roadmap как текущей активной задачи.

## Проверки

### Что можно проверить кодом или тестами

- при наличии команд и автоматизируемых проверок см. исторический блок `Проверки` ниже.

### Что остаётся на ручную проверку

- сверить migrated-каталог с `artifacts/legacy-plan.md`.

## Шаги

- [x] Перенести исходный legacy-план в task-centric структуру
- [x] Сохранить исходный Markdown в `artifacts/legacy-plan.md`
- [ ] При необходимости продолжить эту legacy-задачу уже в рамках `knowledge/tasks/`

## Критерии завершения

- Исходный контур задачи должен быть сохранён в knowledge-системе так, чтобы дальнейшая работа шла только из этого каталога.

## Источник legacy-плана

- текущий артефакт: `artifacts/legacy-plan.md`
- карта миграции исходного пути: `knowledge/tasks/TASK-2026-0002-plans-to-knowledge-migration/artifacts/legacy/legacy-path-map.md`
- исходный статус: `in_progress`
- исходный заголовок: `Общая дорожная карта проекта`

## Исторический контекст

### Изменения

### Текущее состояние проекта

Сейчас проект уже представляет собой рабочий Linux-native bundle с такими свойствами:

- переносимый layout с публичными entrypoint'ами в корне;
- рабочий runtime `xray + sing-box + TUN`;
- shell-скрипты запуска, остановки и диагностики;
- Python backend для текущего web UI;
- desktop launcher и интеграция с меню приложений;
- operator-managed конфиги и sanitzed tracked-шаблон `xray-tun-subvost.json`.

Слабое место текущей версии не в runtime, а в продуктовой модели:

- data/model слой уже вынесен из ручной правки tracked JSON, но UI по-прежнему остаётся временным web-слоем;
- desktop-сценарий стал намного ближе к пользовательскому, однако ещё не переведён на нативный `GTK`-интерфейс;
- consumer-oriented onboarding поверх новой модели ещё не доведён до целевого повседневного сценария.

### Что уже сделано

#### Фаза 0. Основа, layout и переносимость

Закрыта базовая инфраструктура проекта:

- `knowledge/tasks/TASK-2026-0005-project-structure-cleanup/`
- `knowledge/tasks/TASK-2026-0004-desktop-menu-entry/`
- `knowledge/tasks/TASK-2026-0003-desktop-icon-self-sync/`
- `knowledge/tasks/TASK-2026-0010-force-gui-backend-restart-on-shortcut-launch/`

Результат фазы: проект приведён к управляемому layout, получил поддерживаемые launcher'ы и предсказуемое desktop-поведение.

#### Фаза 1. Hardening runtime и installer

Закрыта техническая база для стабильной эксплуатации:

- `knowledge/tasks/TASK-2026-0007-tun-hardening-from-report/`
- `knowledge/tasks/TASK-2026-0006-review-followup-hardening/`
- `knowledge/tasks/TASK-2026-0008-xray-installer-dedup-cleanup/`
- `knowledge/tasks/TASK-2026-0015-track-sanitized-xray-config/`

Результат фазы: bundle получил диагностируемый и более безопасный старт, cleaner installer, защиту от конфликтов `xray.service` и tracked sanitized-конфиг вместо неявного локального файла.

#### Фаза 2. Routing, DNS и эксплуатационная доводка

Закрыт слой эксплуатационных правок под реальное использование:

- `knowledge/tasks/TASK-2026-0012-routing-diagnostics-for-subvost-vs-flclashx/`
- `knowledge/tasks/TASK-2026-0011-remove-global-ru-direct/`
- `knowledge/tasks/TASK-2026-0009-add-public-service-direct-exception/`
- `knowledge/tasks/TASK-2026-0013-sync-bundle-routing-fixes/`
- `knowledge/tasks/TASK-2026-0014-add-direct-exceptions-for-private-rdp-and-lan/`
- `knowledge/tasks/TASK-2026-0016-update-finland-node-from-happ/`
- `knowledge/tasks/TASK-2026-0017-apply-happ-dns-profile/`

Результат фазы: текущая policy-модель и DNS-настройки синхронизированы с рабочим сценарием, bundle пригоден для повседневного использования в своей текущей операторской форме.

#### Фаза 3. Локальная модель данных, подписки и активный узел

Закрыта первая продуктовая волна, которая убирает ручную правку `xray-tun-subvost.json` из обычного пользовательского сценария:

- `knowledge/tasks/TASK-2026-0020-import-config-links/`
- `knowledge/tasks/TASK-2026-0025-subscription-url-refresh/`
- `knowledge/tasks/TASK-2026-0021-multi-profile-node-switching/`

Результат фазы: bundle получил operator-managed локальный store в `~/.config/subvost-xray-tun/`, импорт ссылок, обновление подписок, хранение нескольких профилей и автоматическую materialization активного `Xray` runtime-конфига вне Git.

### Целевое состояние проекта

Целевой образ следующей крупной версии:

- локальный store профилей, подписок и узлов живёт вне Git;
- runtime-конфиг генерируется из локальной модели, а не редактируется вручную;
- пользователь может вставить ссылку, обновить подписку, выбрать активный узел и запустить стек без ручной правки JSON;
- текущий web UI заменён на нативный `GTK`-интерфейс для XFCE;
- существующий runtime-контур `run/stop/capture`, DNS/TUN-логика и диагностика переиспользуются, а не переписываются с нуля.

### Распределение новых планов по этапам

#### Волна 1. Данные, импорт и отказ от ручной правки JSON

Эта волна реализована и отражена в knowledge-системе следующими задачами:

- `knowledge/tasks/TASK-2026-0020-import-config-links/`
- `knowledge/tasks/TASK-2026-0025-subscription-url-refresh/`
- `knowledge/tasks/TASK-2026-0021-multi-profile-node-switching/`

Результат волны: основной текущий pain point закрыт, ручное обновление `xray-tun-subvost.json` больше не является обязательной повседневной операцией.

#### Волна 2. Native desktop UI для XFCE

Это направление остаётся следующим крупным шагом и сейчас зафиксировано как backlog-задача, потому что data/model слой уже стабилизирован, но отдельная реализационная ветка под `GTK` ещё не открыта:

- `knowledge/tasks/TASK-2026-0022-native-ui-gtk-direction/`

Зафиксированное решение:

- основной путь для UI — `GTK`;
- `Tauri` сейчас вне scope;
- если когда-либо появится отдельная задача на мультиплатформенность, она должна стартовать как отдельный `Rust`-проект.

#### Волна 3. Пользовательский UX поверх новой модели

Это направление остаётся в backlog, потому что теперь зависит не от data/model слоя, а от базового `GTK`-направления и решения по следующему desktop UX:

- `knowledge/tasks/TASK-2026-0018-consumer-ux-and-localization/`

Задача этой волны: превратить набор инженерных действий в нормальный пользовательский сценарий `добавил -> обновил -> выбрал -> запустил`.

### Что исключено из текущего scope

- `knowledge/tasks/TASK-2026-0024-qr-import-share/` — `QR` отменён как не приносящий достаточной ценности по сравнению с импортом ссылок и подписок.

### Следующий практический шаг

Следующей реализационной веткой проекта считается Волна 2:

- перевести `knowledge/tasks/TASK-2026-0022-native-ui-gtk-direction/` из backlog в рабочую реализацию или отдельный `GTK` spike;
- строить нативный desktop UI уже поверх готового store/import/subscription/profile слоя, а не поверх ручных JSON;
- после фиксации `GTK`-контракта переходить к `knowledge/tasks/TASK-2026-0018-consumer-ux-and-localization/`.

## Исторические проверки

- Проверить, что roadmap живёт в `knowledge/tasks/TASK-2026-0023-project-roadmap/` как справочный master-документ, а не как текущая активная задача.
- Проверить, что связанные направления распределены по текущим task-каталогам:
  - реализованная Волна 1 в `knowledge/tasks/TASK-2026-0020-import-config-links/`, `knowledge/tasks/TASK-2026-0025-subscription-url-refresh/` и `knowledge/tasks/TASK-2026-0021-multi-profile-node-switching/`;
  - более дальние и зависимые направления в `knowledge/tasks/TASK-2026-0022-native-ui-gtk-direction/` и `knowledge/tasks/TASK-2026-0018-consumer-ux-and-localization/`;
  - исключённая тема в `knowledge/tasks/TASK-2026-0024-qr-import-share/`.
- Проверить, что в roadmap и связанных планах нет live-конфигов, UUID, публичных ключей или приватных subscription URL.
- Прогнать `markdown-localization-guard` по изменённым Markdown-файлам.

## Исторические допущения

- Заимствуются не Windows-specific реализации чужих клиентов, а только полезные пользовательские сценарии.
- Базовый runtime-контур bundle остаётся Linux-native и продолжает опираться на текущие shell-скрипты и Python backend до появления отдельного `GTK` UI-слоя.
- Замена GUI не должна начинаться раньше, чем проект получит локальную модель ссылок, подписок, профилей и активного узла.
- После завершения Волны 1 базовый store/import/subscription/profile слой считается стабильной опорой для дальнейшего `GTK`-направления.
