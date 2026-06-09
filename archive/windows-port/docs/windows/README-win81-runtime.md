# Запуск Windows 8.1

## Что делает подключение

При старте Windows helper берёт активный Xray-конфиг из пользовательского каталога, готовит Windows-вариант конфига и запускает `runtime\xray.exe`.

Перед запуском он добавляет отдельный host route до IP-адреса proxy endpoint через текущий обычный gateway. Это нужно, чтобы сам Xray не попытался подключиться к серверу через поднятый `TUN` и не попал в routing loop.

## Где лежат изменяемые файлы

Изменяемые файлы не пишутся рядом с `.exe`. По умолчанию используются пути внутри:

```text
%LOCALAPPDATA%\subvost-xray-tun\
```

Там находятся:

- `store.json`;
- `generated-xray-config.json`;
- `active-runtime-xray-config.json`;
- `windows-runtime-state.json`;
- `logs\`.

## Какие сетевые команды выполняются

Пример route-команд:

```text
route ADD <proxy-ip> MASK 255.255.255.255 <gateway> METRIC 1
route DELETE <proxy-ip> MASK 255.255.255.255
```

При штатной остановке служебный модуль выполняет сохранённые `route DELETE` команды и останавливает процесс `xray.exe` через `taskkill`.

## Как восстановить сеть вручную

1. Открой PowerShell или `cmd` от администратора.
2. Посмотри файл:

```text
%LOCALAPPDATA%\subvost-xray-tun\windows-runtime-state.json
```

3. Выполни команды из поля `route_delete_commands`.
4. Если `xray.exe` ещё запущен, выполни:

```text
taskkill /IM xray.exe /T /F
```

5. Проверь маршруты:

```text
route print
ipconfig /all
```

## Диагностика

Кнопка `Диагностика` сохраняет JSON-отчёт в:

```text
%LOCALAPPDATA%\subvost-xray-tun\logs\diagnostics\
```

В отчёт входят:

- текущий state runtime;
- вывод `route print`;
- вывод `netsh interface show interface`;
- вывод `ipconfig /all`;
- вывод `tasklist` по `xray.exe`;
- готовые recovery-команды для удаления host routes и остановки процесса.
