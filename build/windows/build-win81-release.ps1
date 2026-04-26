[CmdletBinding()]
param(
  [string]$PythonExe = "python",
  [string]$AssetManifest = "",
  [string]$XrayZip = "",
  [string]$WintunZip = "",
  [switch]$Offline,
  [switch]$SkipPipInstall,
  [switch]$StageRuntimeOnly,
  [switch]$Clean
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
if (-not $AssetManifest) {
  $AssetManifest = Join-Path $ScriptDir "runtime-assets.win81.json"
}

$BuildRoot = Join-Path $Root ".build\win81-x64"
$DownloadDir = Join-Path $BuildRoot "downloads"
$ExtractDir = Join-Path $BuildRoot "extract"
$DistRoot = Join-Path $Root "dist\SubvostXrayTun"
$DistRuntime = Join-Path $DistRoot "runtime"
$DistTools = Join-Path $DistRoot "tools"
$RuntimeDir = Join-Path $Root "runtime"
$ManifestOut = Join-Path $DistRoot "subvost-win81-build-manifest.json"
$XrayTemplate = Join-Path $Root "xray-tun-subvost.json"
$DepsScript = Join-Path $ScriptDir "install-win81-build-deps.ps1"
$VenvPython = Join-Path $Root ".venv-win81-x64\Scripts\python.exe"
$HelperSpecFile = Join-Path $Root "SubvostCore.win81.spec"
$WinFormsProject = Join-Path $Root "windows\SubvostXrayTun.WinForms\SubvostXrayTun.WinForms.csproj"
$WinFormsOutput = Join-Path $Root "windows\SubvostXrayTun.WinForms\bin\Release\SubvostXrayTun.exe"
$UiExe = Join-Path $DistRoot "SubvostXrayTun.exe"
$HelperExe = Join-Path $DistTools "subvost-core.exe"

function Write-Step {
  param([string]$Message)
  Write-Host "[win81-build] $Message"
}

function Fail {
  param([string]$Message)
  throw "[win81-build] $Message"
}

function New-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Assert-File {
  param([string]$Path, [string]$Message)
  if (-not (Test-Path $Path -PathType Leaf)) {
    Fail $Message
  }
}

function Read-JsonFile {
  param([string]$Path)
  Assert-File $Path "Не найден manifest: $Path"
  return Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json
}

function Get-Sha256 {
  param([string]$Path)
  if (Get-Command Get-FileHash -ErrorAction SilentlyContinue) {
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
  }
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash($stream)
    return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
  }
  finally {
    $stream.Dispose()
  }
}

function Assert-Sha256 {
  param([string]$Path, [string]$Expected)
  $actual = Get-Sha256 $Path
  if ($actual -ne $Expected.ToLowerInvariant()) {
    Fail "Ошибка SHA256: $Path expected=$Expected actual=$actual"
  }
  Write-Step "SHA256 OK: $Path"
}

function Download-File {
  param([string]$Url, [string]$OutFile)
  if ($Offline) {
    Fail "Offline-режим запрещает скачивание: $Url"
  }
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Write-Step "Скачиваю: $Url"
  Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

function Resolve-AssetZip {
  param($Asset, [string]$OverridePath)
  $target = Join-Path $DownloadDir $Asset.asset
  if ($OverridePath) {
    Assert-File $OverridePath "Локальный архив не найден: $OverridePath"
    Copy-Item -Force -Path $OverridePath -Destination $target
  }
  elseif (Test-Path $target -PathType Leaf) {
    Write-Step "Использую уже скачанный архив: $target"
  }
  else {
    Download-File -Url $Asset.url -OutFile $target
  }
  Assert-Sha256 -Path $target -Expected $Asset.sha256
  return $target
}

function Expand-ZipWithPython {
  param([string]$ZipPath, [string]$Destination)
  New-Directory $Destination
  & $PythonExe -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" $ZipPath $Destination
  if ($LASTEXITCODE -ne 0) {
    Fail "Не удалось распаковать архив: $ZipPath"
  }
}

function Copy-FirstMatch {
  param([string]$RootDir, [string]$Filter, [string]$Destination)
  $item = Get-ChildItem -Path $RootDir -Recurse -Filter $Filter | Select-Object -First 1
  if ($null -eq $item) {
    Fail "Не найден файл $Filter в $RootDir"
  }
  Copy-Item -Force -Path $item.FullName -Destination $Destination
  return $item.FullName
}

function Copy-WintunDll {
  param([string]$RootDir, [string]$ArchHint, [string]$Destination)
  $dll = Get-ChildItem -Path $RootDir -Recurse -Filter "wintun.dll" |
    Where-Object { $_.FullName -match $ArchHint } |
    Select-Object -First 1
  if ($null -eq $dll) {
    Fail "Не найден wintun.dll для архитектуры $ArchHint в $RootDir"
  }
  Copy-Item -Force -Path $dll.FullName -Destination $Destination
  return $dll.FullName
}

function Find-MSBuild {
  $candidates = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2017\BuildTools\MSBuild\15.0\Bin\MSBuild.exe",
    "${env:ProgramFiles(x86)}\MSBuild\14.0\Bin\MSBuild.exe",
    "${env:WINDIR}\Microsoft.NET\Framework64\v4.0.30319\MSBuild.exe",
    "${env:WINDIR}\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe"
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate -PathType Leaf)) {
      return $candidate
    }
  }
  $command = Get-Command MSBuild.exe -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Path
  }
  return ""
}

function Write-BuildManifest {
  param($Manifest, [string]$XrayZipPath, [string]$WintunZipPath)
  $payload = [ordered]@{
    schema = 1
    generatedAt = (Get-Date).ToUniversalTime().ToString("s") + "Z"
    target = $Manifest.target
    sourceRoot = $Root
    xray = [ordered]@{
      version = $Manifest.xray.version
      asset = $Manifest.xray.asset
      url = $Manifest.xray.url
      sha256 = $Manifest.xray.sha256
      localArchive = $XrayZipPath
    }
    wintun = [ordered]@{
      version = $Manifest.wintun.version
      asset = $Manifest.wintun.asset
      url = $Manifest.wintun.url
      sha256 = $Manifest.wintun.sha256
      localArchive = $WintunZipPath
    }
    output = [ordered]@{
      distRoot = $DistRoot
      runtimeDir = $DistRuntime
      toolsDir = $DistTools
      uiExe = $UiExe
      helperExe = $HelperExe
      xrayTemplate = (Join-Path $DistRoot "xray-tun-subvost.json")
      runtimeOnly = [bool]$StageRuntimeOnly
    }
  }
  New-Directory $DistRoot
  $payload | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $ManifestOut
  Write-Step "Manifest: $ManifestOut"
}

if ($Clean) {
  Write-Step "Очищаю build-output: $BuildRoot, $DistRoot"
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildRoot, $DistRoot
}

$manifest = Read-JsonFile $AssetManifest
New-Directory $DownloadDir
New-Directory $ExtractDir
New-Directory $DistRuntime
New-Directory $DistTools
New-Directory $RuntimeDir

$xrayZipPath = Resolve-AssetZip -Asset $manifest.xray -OverridePath $XrayZip
$wintunZipPath = Resolve-AssetZip -Asset $manifest.wintun -OverridePath $WintunZip

$xrayExtract = Join-Path $ExtractDir "xray"
$wintunExtract = Join-Path $ExtractDir "wintun"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $xrayExtract, $wintunExtract
Expand-ZipWithPython -ZipPath $xrayZipPath -Destination $xrayExtract
Expand-ZipWithPython -ZipPath $wintunZipPath -Destination $wintunExtract

Copy-FirstMatch -RootDir $xrayExtract -Filter "xray.exe" -Destination (Join-Path $DistRuntime "xray.exe") | Out-Null
Copy-FirstMatch -RootDir $xrayExtract -Filter "geoip.dat" -Destination (Join-Path $DistRuntime "geoip.dat") | Out-Null
Copy-FirstMatch -RootDir $xrayExtract -Filter "geosite.dat" -Destination (Join-Path $DistRuntime "geosite.dat") | Out-Null
Copy-WintunDll -RootDir $wintunExtract -ArchHint $manifest.wintun.dllArchHint -Destination (Join-Path $DistRuntime "wintun.dll") | Out-Null

Assert-File $XrayTemplate "Не найден шаблон Xray: $XrayTemplate"
Copy-Item -Force -Path $XrayTemplate -Destination (Join-Path $DistRoot "xray-tun-subvost.json")
Copy-Item -Force -Path (Join-Path $DistRuntime "*") -Destination $RuntimeDir
Write-BuildManifest -Manifest $manifest -XrayZipPath $xrayZipPath -WintunZipPath $wintunZipPath

if ($StageRuntimeOnly) {
  Write-Step "Runtime-ресурсы подготовлены. UI и служебный модуль пропущены по флагу -StageRuntimeOnly."
  exit 0
}

Assert-File $DepsScript "Не найден preflight/install script: $DepsScript"
& $DepsScript -PythonExe $PythonExe -SkipPipInstall:$SkipPipInstall
if ($LASTEXITCODE -ne 0) {
  Fail "Проверка или установка зависимостей завершилась ошибкой."
}

Assert-File $HelperSpecFile "Не найден PyInstaller spec служебного модуля: $HelperSpecFile"
Assert-File $VenvPython "Не найден python в venv: $VenvPython"
Assert-File $WinFormsProject "Не найден WinForms project: $WinFormsProject"

$HelperBuildDir = Join-Path $BuildRoot "helper-dist"
& $VenvPython -m PyInstaller --clean --workpath (Join-Path $BuildRoot "pyinstaller") --distpath $HelperBuildDir $HelperSpecFile
if ($LASTEXITCODE -ne 0) {
  Fail "PyInstaller завершился ошибкой."
}
Assert-File (Join-Path $HelperBuildDir "subvost-core.exe") "PyInstaller не создал subvost-core.exe"
Copy-Item -Force -Path (Join-Path $HelperBuildDir "subvost-core.exe") -Destination $HelperExe

$msbuild = Find-MSBuild
if (-not $msbuild) {
  Fail "MSBuild не найден. Запусти preflight и установи Visual Studio Build Tools."
}
& $msbuild $WinFormsProject /p:Configuration=Release /p:Platform=AnyCPU /m
if ($LASTEXITCODE -ne 0) {
  Fail "MSBuild завершился ошибкой."
}
Assert-File $WinFormsOutput "WinForms exe не найден: $WinFormsOutput"
Copy-Item -Force -Path $WinFormsOutput -Destination $UiExe
Write-BuildManifest -Manifest $manifest -XrayZipPath $xrayZipPath -WintunZipPath $wintunZipPath

Write-Step "Готово: $DistRoot"
