# Карточка задачи TASK-2026-0058

## Паспорт

| Поле | Значение |
|------|----------|
| ID задачи | `TASK-2026-0058` |
| Parent ID | `—` |
| Уровень вложенности | `0` |
| Ключ в путях | `TASK-2026-0058` |
| Технический ключ для новых именуемых сущностей | `win81-native-windows-port` |
| Краткое имя | `win81-native-windows-port` |
| Статус | `в работе` |
| Приоритет | `высокий` |
| Ответственный | `Codex` |
| Ветка | `task/task-2026-0058-win81-native-windows-port` |
| Дата создания | `2026-04-27` |
| Дата обновления | `2026-04-27` |

## Цель

Довести Windows 8.1 x64 порт до состояния, которое можно отдавать пользователю как понятный и проверенный комплект: готовые скрипты установки зависимостей и сборки, воспроизводимая поставка, подробный русский `README` и нативный Windows UI вместо запуска интерфейса в браузере.

## Границы

### Входит

- repo-first интеграция удачных решений из архива `personal-singbox-xray-tun-win81-port.zip` без слепого переноса всего checkout-а;
- сборочная цепочка Windows 8.1 x64 с явными preflight-проверками, pin-ами версий и проверкой контрольных сумм runtime-бинарников;
- готовый Windows bundle или чёткий release-package маршрут, где пользователь понимает, что именно запускать;
- нативный Windows UI без браузера и без webview как основного presentation-слоя;
- укрепление Windows runtime:
  - безопасная маршрутизация без loop-а Xray через собственный `TUN`;
  - управляемые пути state/logs в пользовательском профиле;
  - устойчивое декодирование вывода `netsh`, `route`, `ipconfig`, `taskkill` и `PowerShell`;
  - проверка stale `Wintun` adapter после старта;
- русскоязычная документация уровня начинающего пользователя:
  - что скачать;
  - куда распаковать;
  - как установить зависимости;
  - как собрать;
  - как запустить;
  - как подключиться;
  - как вернуть сеть при проблеме;
  - где взять диагностический лог;
- реальная проверка на Windows 8.1 x64 build 9600 или явный статус `не проверено на живой Windows 8.1` до прохождения такого smoke.

### Не входит

- поддержка Windows 7, Windows 10/11 как отдельных целевых платформ;
- перевод Linux `GTK4` UI на Windows;
- сохранение браузерного UI как основного Windows-интерфейса;
- публикация GitHub Release, tag или финального внешнего архива без отдельной команды пользователя;
- импорт приватных runtime-секретов, живых подписок или рабочих endpoint-ов в Git;
- изменение Linux runtime-поведения вне общих модулей, необходимых для аккуратной кросс-платформенной архитектуры.

## Контекст

- источник постановки: ревью архива `/home/prog7/MyWorkspace/20-Personal/PetProjects/personal-singbox-xray-tun-win81-port.zip`;
- результат ревью: архив является developer prototype, а не готовой Windows-поставкой;
- ключевое уточнение пользователя: на Windows нужен нативный Windows UI, не браузер;
- текущий проект уже имеет общий Python service-layer и нативный Linux `GTK4` опыт, но Windows UI должен проектироваться отдельно под возможности Windows 8.1;
- Windows 8.1 требует осторожного выбора UI-стека, build toolchain, `UCRT`, runtime-бинарников Xray/Wintun и recovery-сценариев для сети.

## Декомпозиция

| ID | Статус | Каталог | Краткое описание |
|----|--------|---------|------------------|
| `TASK-2026-0058.1` | `завершена` | `subtasks/TASK-2026-0058.1-win81-release-package-and-build-chain/` | Сборочная цепочка, preflight, зависимости, pin/checksum runtime-бинарников и release-package layout |
| `TASK-2026-0058.2` | `готова к работе` | `subtasks/TASK-2026-0058.2-native-windows-ui-shell/` | Нативный Windows UI без браузера: выбор стека, shell-контракт и первый рабочий vertical slice |
| `TASK-2026-0058.3` | `готова к работе` | `subtasks/TASK-2026-0058.3-windows-runtime-routing-hardening/` | Hardening Windows runtime: маршруты, state/log paths, кодировки, stale adapter и recovery |
| `TASK-2026-0058.4` | `черновик` | `subtasks/TASK-2026-0058.4-win81-verification-and-user-docs/` | Живой Windows 8.1 smoke, beginner README, troubleshooting и handoff-комплект |

## Затронутые области

| Область | Что меняется |
|---------|--------------|
| Код / сервисы | Windows runtime controller, общий service-layer, возможный отдельный Windows core CLI для нативного UI |
| Конфигурация / схема данных / именуемые сущности | Windows template, runtime asset manifest, build manifest, state/log paths |
| Интерфейсы / формы / страницы | Новый нативный Windows shell вместо открытия браузера |
| Интеграции / обмены | Xray, Wintun, `netsh`, `route`, `taskkill`, UAC, PowerShell |
| Документация | Windows README, build/run инструкции, recovery и smoke-протокол |

## Связанные материалы

- основной каталог задачи: `knowledge/tasks/TASK-2026-0058-win81-native-windows-port/`
- файл плана: `plan.md`
- архитектурная спецификация: `sdd.md`
- исходный архив ревью: `/home/prog7/MyWorkspace/20-Personal/PetProjects/personal-singbox-xray-tun-win81-port.zip`
- связанный Linux native UI опыт: `knowledge/tasks/TASK-2026-0053-gtk4-native-ui-spike/`
- текущий общий service-layer: `gui/subvost_app_service.py`
- текущий web backend: `gui/gui_server.py`
- текущий Windows-кандидат из архива: `gui/subvost_windows_runtime.py`, `gui/windows_launcher.py`, `SubvostXrayTun.win81.spec`, `build/windows/build-win81-x64.ps1`

## Текущий этап

Подзадача `TASK-2026-0058.1` реализована и прошла локальные проверки. Windows UI-стек согласован: `.NET Framework 4.8 + Windows Forms` как нативная оболочка, Python остаётся core/helper слоем с JSON-командами.

## Стратегия проверки

### Покрывается кодом или тестами

- синтаксис Python и PowerShell;
- unit-тесты для выбора Windows template, путей, service-layer и runtime-команд;
- тесты генерации Windows runtime config без Linux-only `sockopt.mark`;
- тесты build manifest, pin/checksum policy и запрета silent fallback на неподтверждённый asset;
- локализационный guard по созданным task/docs/UI-текстам;
- `git diff --check`.

### Остаётся на ручную проверку

- сборка Windows `.exe` на Windows-хосте;
- запуск нативного UI на Windows 8.1;
- ручной запуск и остановка с подтверждением прав администратора;
- создание `SubvostTun`;
- `route print`, `netsh`, DNS и recovery после аварийной остановки;
- проверка, что beginner README реально достаточен для сборки и запуска с чистой машины.

## Критерии готовности

- Windows UI не открывает браузер и не использует webview как основной интерфейс;
- build scripts ставят или проверяют зависимости и собирают комплект воспроизводимо;
- runtime-бинарники Xray/Wintun имеют pin версий, checksum и provenance;
- пакет содержит понятный entrypoint для пользователя;
- Windows runtime не создаёт routing loop и имеет документированный recovery;
- state/logs не пишутся в защищённый каталог установки;
- русский `README` проходит локализационный guard и понятен без знания проекта;
- есть сырой лог реального Windows 8.1 smoke или задача явно остаётся незавершённой.

## Итог

Заполняется при закрытии задачи после реализации, проверки и решения по release-package.
