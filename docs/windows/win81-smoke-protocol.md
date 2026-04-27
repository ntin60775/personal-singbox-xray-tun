# Smoke-протокол Windows 8.1

## Статус

На дату `2026-04-27` live smoke на реальной Windows 8.1 из текущей Linux-среды не выполнялся. Этот документ фиксирует точный протокол проверки.

## Машина

Заполни перед проверкой:

```text
Windows edition:
Windows build:
Архитектура:
.NET Framework Release:
Python:
MSBuild:
Путь к проекту или готовому комплекту:
```

## Проверка сборки

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\install-win81-build-deps.ps1
powershell -ExecutionPolicy Bypass -File .\build\windows\build-win81-release.ps1
```

Ожидаемый результат:

```text
dist\SubvostXrayTun\SubvostXrayTun.exe
dist\SubvostXrayTun\tools\subvost-core.exe
dist\SubvostXrayTun\runtime\xray.exe
dist\SubvostXrayTun\runtime\wintun.dll
dist\SubvostXrayTun\README.md
```

## Проверка UI

1. Запусти `dist\SubvostXrayTun\SubvostXrayTun.exe`.
2. Убедись, что открылось обычное Windows-окно.
3. Убедись, что браузер не открылся.
4. Нажми `Обновить`.
5. Добавь тестовую подписку.
6. Выбери узел и нажми `Выбрать узел`.

## Проверка подключения

Перед стартом сохрани:

```text
route print
ipconfig /all
tasklist /FI "IMAGENAME eq xray.exe"
```

Затем нажми `Подключиться`.

Ожидаемый результат:

- появился процесс `xray.exe`;
- появился адаптер `SubvostTun`;
- в `route print` есть host route до IP proxy endpoint через исходный gateway;
- интернет работает;
- сам Xray не уходит в routing loop через `SubvostTun`.

## Проверка остановки

Нажми `Отключиться`.

Ожидаемый результат:

- процесс `xray.exe` остановлен;
- host route до proxy endpoint удалён;
- сеть работает через обычный gateway;
- `route print` не содержит лишний route, сохранённый в `windows-runtime-state.json`.

## Проверка аварийного восстановления

1. Запусти подключение.
2. Заверши `SubvostXrayTun.exe` через диспетчер задач.
3. Выполни recovery-команды из:

```text
%LOCALAPPDATA%\subvost-xray-tun\windows-runtime-state.json
```

4. Выполни:

```text
taskkill /IM xray.exe /T /F
route print
ipconfig /all
```

Ожидаемый результат: сеть восстановлена вручную.

## Диагностика

Нажми `Диагностика` и проверь, что создан файл:

```text
%LOCALAPPDATA%\subvost-xray-tun\logs\diagnostics\subvost-win81-diagnostic-*.json
```

Внутри должны быть:

- `route_print`;
- `netsh_interfaces`;
- `ipconfig`;
- `tasklist_xray`;
- `recovery.route_delete_commands`.

## Итог проверки

Заполни после smoke:

```text
Дата:
Проверяющий:
Сборка прошла: да/нет
UI запустился: да/нет
Подключение прошло: да/нет
Остановка прошла: да/нет
Recovery прошёл: да/нет
Диагностика создана: да/нет
Открытые замечания:
```
