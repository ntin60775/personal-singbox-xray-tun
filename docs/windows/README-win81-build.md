# Сборка Windows 8.1

## Кому нужен этот документ

Этот документ нужен тому, кто собирает Windows-комплект из исходников. Если нужен уже готовый архив приложения, используй готовую папку `dist\SubvostXrayTun\` после успешной сборки или отдельный release-архив, когда он будет опубликован.

## Что понадобится

- компьютер с Windows 8.1 x64;
- интерпретатор `Python 3.11 x64`;
- `.NET Framework 4.8`;
- `MSBuild` из Visual Studio Build Tools или совместимых build tools для `.NET Framework`;
- Доступ в интернет для скачивания `Xray`, `Wintun` и Python-зависимостей или заранее скачанные архивы.
- PowerShell, запущенный из каталога проекта.

## Проверить зависимости

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\install-win81-build-deps.ps1
```

Скрипт проверит версию Python, разрядность Python, `.NET Framework 4.8`, наличие `MSBuild`, создаст `.venv-win81-x64` и поставит Python-зависимости сборки.

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

## Собрать приложение

```powershell
powershell -ExecutionPolicy Bypass -File .\build\windows\build-win81-release.ps1
```

Скрипт выполнит четыре шага:

- подготовит runtime-ресурсы;
- соберёт служебный модуль `subvost-core.exe` через PyInstaller;
- соберёт нативное окно `SubvostXrayTun.exe` через `MSBuild`;
- сложит переносимый комплект в `dist\SubvostXrayTun\`.

## Что требует живой проверки

Скрипт собирает полный Windows-комплект: `SubvostXrayTun.exe`, `subvost-core.exe`, `xray.exe`, `wintun.dll`, geodata и пользовательскую документацию.

Автотесты в Linux проверяют сборочный контракт, helper-контракт и Windows runtime-controller, но не доказывают живой запуск на Windows 8.1. Перед утверждением поставки нужен smoke на реальной Windows 8.1 по протоколу:

```text
docs\windows\win81-smoke-protocol.md
```

## Где смотреть результат

```text
dist\SubvostXrayTun\runtime\
dist\SubvostXrayTun\tools\subvost-core.exe
dist\SubvostXrayTun\SubvostXrayTun.exe
dist\SubvostXrayTun\xray-tun-subvost.json
dist\SubvostXrayTun\README.md
dist\SubvostXrayTun\docs\README-win81-runtime.md
dist\SubvostXrayTun\docs\win81-smoke-protocol.md
dist\SubvostXrayTun\subvost-win81-build-manifest.json
runtime\
```

Каталог `runtime\` в корне нужен для локальной проверки. Каталог `dist\SubvostXrayTun\` станет основой будущего переносимого пакета.

## Runtime и восстановление сети

Сетевые изменения и ручное восстановление описаны отдельно:

```text
docs\windows\README-win81-runtime.md
```
