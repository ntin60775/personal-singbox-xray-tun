[CmdletBinding()]
param(
  [string]$PythonExe = "python",
  [switch]$SkipPipInstall
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$AssetManifest = Join-Path $ScriptDir "runtime-assets.win81.json"
$RequirementsFile = Join-Path $ScriptDir "python-build-requirements.txt"
$VenvDir = Join-Path $Root ".venv-win81-x64"
$WinFormsProject = Join-Path $Root "windows\SubvostXrayTun.WinForms\SubvostXrayTun.WinForms.csproj"

function Write-Step {
  param([string]$Message)
  Write-Host "[win81-preflight] $Message"
}

function Fail {
  param([string]$Message)
  throw "[win81-preflight] $Message"
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

function Get-PythonJson {
  param([string]$Expression)
  $code = "import json,platform,sys; print(json.dumps($Expression))"
  $raw = & $PythonExe -c $code
  if ($LASTEXITCODE -ne 0) {
    Fail "Python не запустился через '$PythonExe'. Установи Python x64 и повтори preflight."
  }
  return $raw | ConvertFrom-Json
}

function Assert-Python {
  param($Manifest)
  $version = Get-PythonJson "[sys.version_info.major, sys.version_info.minor, sys.version_info.micro]"
  $arch = Get-PythonJson "platform.architecture()[0]"
  $versionText = "$($version[0]).$($version[1]).$($version[2])"
  Write-Step "Python: $versionText, arch=$arch"

  if ([int]$version[0] -ne [int]$Manifest.python.maximumMajor) {
    Fail "Нужен Python $($Manifest.python.maximumMajor).x, найден $versionText."
  }
  if ([int]$version[1] -lt 11) {
    Fail "Нужен Python $($Manifest.python.minimumVersion)+ x64 для Windows 8.1, найден $versionText."
  }
  if ($arch -ne $Manifest.python.requiredArch) {
    Fail "Нужен Python $($Manifest.python.requiredArch), найден $arch."
  }
}

function Assert-DotNet48 {
  $releaseKeyPath = "HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
  $release = 0
  if (Test-Path $releaseKeyPath) {
    $props = Get-ItemProperty $releaseKeyPath
    if ($props.Release) {
      $release = [int]$props.Release
    }
  }
  Write-Step ".NET Framework Release=$release"
  if ($release -lt 528040) {
    Fail "Нужен .NET Framework 4.8. Установи его и повтори preflight."
  }
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

function Assert-WinFormsToolchain {
  Assert-File $WinFormsProject "Не найден WinForms project: $WinFormsProject"
  $projectText = Get-Content -Raw -Encoding UTF8 $WinFormsProject
  if ($projectText -notmatch "<TargetFrameworkVersion>v4\.8</TargetFrameworkVersion>") {
    Fail "WinForms project должен таргетить .NET Framework 4.8."
  }
  if ($projectText -notmatch "<OutputType>WinExe</OutputType>") {
    Fail "WinForms project должен собираться как WinExe."
  }
  $msbuild = Find-MSBuild
  if (-not $msbuild) {
    Fail "MSBuild не найден. Установи Visual Studio Build Tools или .NET Framework build tools."
  }
  Write-Step "MSBuild: $msbuild"
}

function New-Directory {
  param([string]$Path)
  if (-not (Test-Path $Path -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Ensure-Venv {
  if (-not (Test-Path $VenvDir -PathType Container)) {
    Write-Step "Создаю venv: $VenvDir"
    & $PythonExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
      Fail "Не удалось создать venv: $VenvDir"
    }
  }
  $venvPython = Join-Path $VenvDir "Scripts\python.exe"
  Assert-File $venvPython "В venv не найден python.exe: $venvPython"
  return $venvPython
}

function Install-PythonBuildDeps {
  param([string]$VenvPython)
  if ($SkipPipInstall) {
    Write-Step "pip install пропущен по флагу -SkipPipInstall"
    return
  }
  Assert-File $RequirementsFile "Не найден файл Python-зависимостей: $RequirementsFile"
  Write-Step "Обновляю pip"
  & $VenvPython -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) {
    Fail "pip upgrade завершился ошибкой."
  }
  Write-Step "Ставлю зависимости сборки из $RequirementsFile"
  & $VenvPython -m pip install --requirement $RequirementsFile
  if ($LASTEXITCODE -ne 0) {
    Fail "pip install зависимостей сборки завершился ошибкой."
  }
}

$manifest = Read-JsonFile $AssetManifest
Write-Step "Цель: $($manifest.target)"
Write-Step "PowerShell: $($PSVersionTable.PSVersion)"
Assert-Python $manifest
Assert-DotNet48
Assert-WinFormsToolchain
$venvPython = Ensure-Venv
Install-PythonBuildDeps $venvPython
Write-Step "Готово. Venv: $VenvDir"
