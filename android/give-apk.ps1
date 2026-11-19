# Отдать человеку APK актуального релиза.
#
#   .\give-apk.ps1                  # копия в C:\Users\<юзер>\Downloads
#   .\give-apk.ps1 -Dir D:\Куда-то  # копия в указанную папку
#
# Скрипт берёт файл ТОЛЬКО из movie-site/app/ (единственный каталог релизов),
# сверяет его с latest.json и отпечатком подписи и копирует под понятным именем.
# Debug-сборки из app/build/outputs/ не используются никогда.

param(
    [string]$Dir = (Join-Path $env:USERPROFILE "Downloads")
)

$ErrorActionPreference = "Stop"

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$androidDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $androidDir
$appDir = Join-Path $repoDir "app"
$manifestPath = Join-Path $appDir "latest.json"

if (-not (Test-Path $manifestPath)) {
    Write-Host "Нет app/latest.json — сначала выпусти релиз через release.ps1" -ForegroundColor Red
    exit 1
}

$m = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$apkName = "WhatToWatch-$($m.versionName).apk"
$apkPath = Join-Path $appDir $apkName

if (-not (Test-Path $apkPath)) {
    Write-Host "В app/ нет $apkName — релиз неполный" -ForegroundColor Red
    exit 1
}

# Проверка согласованности: версия, размер, SHA-256, подпись.
& (Join-Path $androidDir "check-release.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Релиз не прошёл проверку — отдавать его людям нельзя" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$target = Join-Path $Dir $apkName
Copy-Item $apkPath $target -Force

$size = [math]::Round((Get-Item $target).Length / 1MB, 2)
Write-Host "APK:     $target ($size МБ)" -ForegroundColor Green
Write-Host "Версия:  $($m.versionName) (versionCode $($m.versionCode))" -ForegroundColor Green
Write-Host "Ссылка:  $($m.apkUrl)" -ForegroundColor Green
Write-Host ""
Write-Host "Напоминание: подпись release-ключа. Если на телефоне стоит сборка" -ForegroundColor Yellow
Write-Host "с другим ключом (debug), её нужно сначала удалить." -ForegroundColor Yellow
