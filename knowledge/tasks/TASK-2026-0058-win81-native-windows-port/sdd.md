# Спецификация задачи TASK-2026-0058

## Назначение

Спецификация задаёт целевой контракт Windows 8.1 порта после ревью архивной доработки. Главная поправка к архивному решению: Windows-интерфейс должен быть нативным приложением, а не открытием локального `HTTP` GUI в браузере.

## Инварианты

| ID | Инвариант |
|----|-----------|
| `INV-1` | Windows UI не открывает браузер как основной интерфейс. |
| `INV-2` | Webview не считается нативным Windows UI для этой задачи. |
| `INV-3` | Windows UI работает через поддерживаемый core/service contract, а не через неофициальный scraping web UI. |
| `INV-4` | Runtime-действия с правами администратора выполняются только через явный UAC flow. |
| `INV-5` | Runtime-бинарники Xray/Wintun не скачиваются как неподтверждённый `latest` без pin версии и checksum. |
| `INV-6` | Windows runtime не полагается только на `sockopt.interface` как единственную защиту от routing loop. |
| `INV-7` | State, logs и пользовательские данные не требуют записи в защищённый каталог установки. |
| `INV-8` | README и все новые пользовательские тексты пишутся по-русски, английский остаётся только в машинно-значимых литералах. |
| `INV-9` | Реальный Windows 8.1 smoke является обязательным gate перед утверждением результата как готовой поставки. |

## Предлагаемая архитектура

### Слои

| Слой | Ответственность |
|------|-----------------|
| Нативный Windows shell | Окно, меню, кнопки, статусы, формы подписок и диагностики без браузера |
| Core/helper contract | JSON-команды для status, start, stop, diagnostics, subscriptions, nodes и routing |
| Python service-layer | Переиспользование существующей логики store/runtime/routing/parser |
| Контроллер Windows runtime | `Xray`, `Wintun`, подтверждение прав администратора, `netsh`, `route`, `taskkill`, диагностика |
| Build/release tooling | Установка зависимостей, сборка, pin/checksum runtime assets, package layout |

### Рекомендуемый UI-стек для обсуждения

Рекомендуемый вариант: `.NET Framework 4.8 + Windows Forms` как отдельный shell поверх Python core/helper.

Причины:

- Windows 8.1 поддерживает `.NET Framework 4.8`;
- `Windows Forms` даёт настоящие Windows-контролы без браузера;
- сборка может идти через стандартный Windows toolchain;
- UAC, process execution и file dialogs естественны для Windows;
- Python-логику можно сохранить в helper-е и не переписывать весь runtime на C#.

Недостатки:

- появляется второй язык и отдельный проект;
- нужен чёткий JSON-контракт между UI и Python helper;
- installer/build README должен объяснять `.NET` и build tools.

Резервные варианты:

- `Python + tkinter`: быстрый fallback с минимальными зависимостями, но слабее по UX;
- `PySide2 / Qt5`: сильнее визуально, но тяжелее для Win8.1 packaging;
- `PowerShell + Windows Forms`: только для preflight/install scripts, не для основного UI.

## Контракт core/helper

Нативный UI не должен импортировать приватные Python-модули напрямую. Для Windows shell нужен стабильный helper interface:

```text
subvost-core.exe status --json
subvost-core.exe start --json
subvost-core.exe stop --json
subvost-core.exe diagnostics --json
subvost-core.exe subscriptions list --json
subvost-core.exe subscriptions add --url <url> --json
subvost-core.exe nodes activate --profile-id <id> --node-id <id> --json
```

Фактические имена команд можно уточнить при реализации, но контракт обязан быть:

- машинно-читаемым;
- стабильным для UI;
- покрытым unit-тестами;
- безопасным к ошибкам UAC и runtime-команд;
- локализованным в пользовательских сообщениях.

## Укрепление runtime

Windows runtime должен закрыть риски ревью:

- перед добавлением default route определить исходный gateway и внешний interface;
- добавить host route к proxy endpoint через исходный gateway до перехвата default route;
- после старта проверить, что Xray жив, `SubvostTun` создан именно текущим запуском или валидно переиспользован, route table соответствует ожиданию;
- при ошибке откатить route и попытаться остановить Xray;
- diagnostics должны собирать `route print`, `netsh interface ipv4 show interfaces`, `ipconfig /all`, `tasklist`, Xray version и state file;
- state/logs хранить в `%LOCALAPPDATA%\subvost-xray-tun`, а не рядом с `.exe`;
- вывод системных команд читать с `errors=replace` и сохранять return code.

## Контракт сборки и поставки

Скрипты Windows должны дать два режима:

- `install-win81-build-deps.ps1`: проверка или установка build-зависимостей, насколько это возможно без скрытых действий;
- `build-win81-release.ps1`: сборка release package из зафиксированных версий и локальных или скачанных runtime assets.

Минимальные свойства:

- preflight выводит версии Python, PowerShell, `.NET`, PyInstaller, Xray asset и Wintun;
- build не выбирает неподтверждённый asset молча;
- checksum проверяется до упаковки;
- результат содержит manifest с версиями и SHA256;
- `-Offline` режим принимает локальные архивы и не ходит в сеть;
- `-Clean` явно показывает, какие build-каталоги будут очищены.

## Пользовательский README

Windows README должен быть отдельным документом для пользователя, а не implementation note. Минимальные разделы:

- для кого этот комплект;
- что будет изменяться в системе;
- что скачать заранее;
- как открыть PowerShell;
- как проверить зависимости;
- как собрать;
- как запустить;
- как импортировать подписку и выбрать узел;
- как подключиться и отключиться;
- что делать, если пропал интернет;
- где лежат логи;
- как отправить диагностику без секретов.

## Gate готовности

Задачу нельзя закрывать как готовую Windows-поставку без evidence:

```text
build host: Windows 8.1 x64 build 9600
python version:
dotnet version:
xray version:
wintun version:
build command:
package path:
xray run -test:
ui launch:
uac start:
subvosttun present:
route print before:
route print after start:
route print after stop:
diagnostics path:
manual recovery checked:
```

Если живого Windows 8.1 хоста нет, результат может быть только `готово к Windows smoke`, но не `готовая поставка`.
