# Сборка Windows 8.1

## Кому нужен этот документ

Этот документ нужен тому, кто собирает Windows-комплект из исходников. Если нужен уже готовый архив приложения, дождись пакета поставки после завершения `TASK-2026-0058`.

## Что понадобится

- компьютер с Windows 8.1 x64;
- интерпретатор `Python 3.11 x64`;
- `.NET Framework 4.8`.
- Доступ в интернет для скачивания `Xray`, `Wintun` и Python-зависимостей или заранее скачанные архивы.
- PowerShell, запущенный из каталога проекта.

## Проверить зависимости

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\install-win81-build-deps.ps1
```

Скрипт проверит версию Python, разрядность Python, `.NET Framework 4.8`, создаст `.venv-win81-x64` и поставит Python-зависимости сборки.

## Собрать runtime-ресурсы

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\build-win81-release.ps1 -StageRuntimeOnly
```

Скрипт скачает строго зафиксированные архивы, проверит `SHA256`, распакует `xray.exe`, `geoip.dat`, `geosite.dat`, `wintun.dll` и создаст manifest сборки.

## Сборка без доступа к сети

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\build-win81-release.ps1 `
  -Offline `
  -StageRuntimeOnly `
  -XrayZip C:\Temp\Xray-win7-64.zip `
  -WintunZip C:\Temp\wintun-0.14.1.zip
```

Даже в режиме без сети контрольные суммы проверяются. Если архив отличается от ожидаемого, сборка остановится.

## Что сейчас не делает этот этап

`TASK-2026-0058.1` готовит сборочную цепочку и runtime-ресурсы. Финальный `.exe` с нативным Windows UI появится в следующей подзадаче, где будет реализована Windows-оболочка.

## Где смотреть результат

```text
dist\SubvostXrayTun\runtime\
dist\SubvostXrayTun\subvost-win81-build-manifest.json
runtime\
```

Каталог `runtime\` в корне нужен для локальной проверки. Каталог `dist\SubvostXrayTun\` станет основой будущего переносимого пакета.
