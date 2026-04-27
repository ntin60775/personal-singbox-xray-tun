# Subvost Xray Tun для Windows 8.1

## Что это

Это приложение под Windows 8.1 x64. Оно открывает обычное Windows-окно, не браузер. Внутри используется `Xray` и сетевой адаптер `Wintun`.

## Что должно быть в готовой папке

После сборки или распаковки готового комплекта должна быть такая папка:

```text
SubvostXrayTun\
  SubvostXrayTun.exe
  README.md
  xray-tun-subvost.json
  runtime\
    xray.exe
    wintun.dll
    geoip.dat
    geosite.dat
  tools\
    subvost-core.exe
  docs\
    README-win81-runtime.md
```

Главный файл для запуска:

```text
SubvostXrayTun.exe
```

## Что нужно установить один раз

На компьютере с Windows 8.1 x64 нужны:

- `.NET Framework 4.8`;
- права администратора для подключения;
- доступ к интернету;
- готовая ссылка подписки или отдельная proxy-ссылка.

Если ты сам собираешь приложение из исходников, дополнительно нужны:

- `Python 3.11 x64`;
- `MSBuild` из Visual Studio Build Tools.

## Как собрать из исходников

Открой PowerShell в папке проекта и выполни:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\install-win81-build-deps.ps1
powershell -ExecutionPolicy Bypass -File .\build\windows\build-win81-release.ps1
```

Результат появится здесь:

```text
dist\SubvostXrayTun\
```

Если интернет на build-машине недоступен, заранее скачай архивы `Xray-win7-64.zip` и `wintun-0.14.1.zip`, затем используй:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\build-win81-release.ps1 `
  -Offline `
  -XrayZip C:\Temp\Xray-win7-64.zip `
  -WintunZip C:\Temp\wintun-0.14.1.zip
```

## Как запустить готовое приложение

1. Распакуй папку `SubvostXrayTun` в удобное место, например:

```text
C:\SubvostXrayTun\
```

2. Запусти:

```text
C:\SubvostXrayTun\SubvostXrayTun.exe
```

3. Нажми `Добавить`, вставь ссылку подписки и дождись списка узлов.
4. Выбери узел в таблице.
5. Нажми `Выбрать узел`.
6. Нажми `Подключиться`.

При старте Windows может попросить права администратора. Это нормально: приложению нужно управлять маршрутом до proxy-сервера и сетевым адаптером.

## Где лежат настройки и логи

Приложение не должно писать изменяемые файлы рядом с `.exe`. Основное место:

```text
%LOCALAPPDATA%\subvost-xray-tun\
```

Там лежат:

- подписки и выбранный узел;
- активный Xray-конфиг;
- state подключения;
- логи;
- диагностика.

## Если пропал интернет

1. Закрой приложение.
2. Открой PowerShell или `cmd` от администратора.
3. Останови `xray.exe`:

```text
taskkill /IM xray.exe /T /F
```

4. Открой файл:

```text
%LOCALAPPDATA%\subvost-xray-tun\windows-runtime-state.json
```

5. Найди поле `route_delete_commands` и выполни команды оттуда.
6. Проверь сеть:

```text
route print
ipconfig /all
```

Если файл `windows-runtime-state.json` отсутствует, нажми в приложении `Диагностика` и посмотри свежий отчёт в:

```text
%LOCALAPPDATA%\subvost-xray-tun\logs\diagnostics\
```

## Что ещё нужно проверить на живой Windows 8.1

В текущем репозитории есть локальные тесты сборочной логики, helper-а и runtime-controller-а. Но живой запуск на Windows 8.1 должен быть выполнен отдельно по smoke-протоколу:

```text
docs\windows\win81-smoke-protocol.md
```

Пока этот smoke не выполнен, комплект нельзя честно считать полностью проверенным на реальной Windows 8.1.
