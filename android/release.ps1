# Сборка и публикация релиза WhatToWatch.
#
#   .\release.ps1 -VersionCode 3 -VersionName 1.0.2 -Notes "Что нового 1","Что нового 2"
#
# Скрипт собирает release-APK, кладёт его и latest.json в movie-site/app/,
# коммитит и пушит. GitHub Pages сразу раздаёт новую версию, приложение
# на телефоне видит её при следующем запуске.

param(
    [int]$VersionCode,
    [string]$VersionName,
    [string[]]$Notes = @(),
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

$androidDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $androidDir
$appDir = Join-Path $repoDir "app"
$propsPath = Join-Path $androidDir "version.properties"
$utf8 = New-Object System.Text.UTF8Encoding($false)

# --- версия ---
$props = @{}
Get-Content $propsPath -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)$') { $props[$matches[1]] = $matches[2].Trim() }
}
$code = if ($VersionCode -gt 0) { $VersionCode } else { [int]$props["versionCode"] }
$name = if ($VersionName) { $VersionName } else { $props["versionName"] }

[System.IO.File]::WriteAllText($propsPath, "versionCode=$code`nversionName=$name`n", $utf8)
Write-Host "Версия: $name (versionCode $code)" -ForegroundColor Cyan

# --- сборка ---
Push-Location $androidDir
try {
    & .\gradlew.bat assembleRelease --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Сборка завершилась с ошибкой" }
} finally {
    Pop-Location
}

# --- публикация файлов ---
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
$apkName = "WhatToWatch-$name.apk"
$apkPath = Join-Path $appDir $apkName
Copy-Item (Join-Path $androidDir "app\build\outputs\apk\release\app-release.apk") $apkPath -Force

Get-ChildItem $appDir -Filter "WhatToWatch-*.apk" |
    Where-Object { $_.Name -ne $apkName } |
    Remove-Item -Force

$hash = (Get-FileHash $apkPath -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $apkPath).Length

$manifest = [ordered]@{
    versionCode = $code
    versionName = $name
    apkUrl      = "https://fvkhweb.github.io/movie-site/app/$apkName"
    sha256      = $hash
    size        = $size
    notes       = @($Notes)
    publishedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}
$json = $manifest | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $appDir "latest.json"), $json, $utf8)

Write-Host "APK:    $apkPath ($([math]::Round($size / 1MB, 2)) МБ)" -ForegroundColor Green
Write-Host "SHA256: $hash" -ForegroundColor Green

# --- git ---
if ($NoPush) {
    Write-Host "NoPush: коммит и пуш пропущены" -ForegroundColor Yellow
    return
}

Push-Location $repoDir
try {
    # git пишет предупреждения в stderr — не даём PowerShell превратить их в исключение
    $ErrorActionPreference = "Continue"
    git add app android
    if ($LASTEXITCODE -ne 0) { throw "git add не удался" }
    git commit -m "Релиз $name ($code)"
    if ($LASTEXITCODE -ne 0) { throw "Нечего коммитить или git недоступен" }
    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "Пуш не удался" }
} finally {
    Pop-Location
}

Write-Host "Готово: https://fvkhweb.github.io/movie-site/app/latest.json" -ForegroundColor Green
