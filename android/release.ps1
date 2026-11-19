# Сборка и публикация релиза WhatToWatch.
#
#   .\release.ps1 -VersionCode 3 -VersionName 1.1.0 -Notes "Что нового 1","Что нового 2"
#
# Единственный способ выпустить обновление. Скрипт собирает release-APK,
# кладёт его и latest.json в movie-site/app/, коммитит и пушит.
# Подробности и правила — в ../AGENTS.md.

param(
    [int]$VersionCode,
    [string]$VersionName,
    [string[]]$Notes = @(),
    [switch]$Force,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$androidDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $androidDir
$appDir = Join-Path $repoDir "app"
$propsPath = Join-Path $androidDir "version.properties"
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Invoke-Git([string[]]$arguments) {
    # git пишет предупреждения в stderr — не даём PowerShell превратить их в исключение
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & git @arguments
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    return $code
}

# --- 1. Свежий репозиторий (данные сайта обновляет бот) ---
Push-Location $repoDir
try {
    $pull = Invoke-Git @("pull", "--rebase", "origin", "main")
    if ($pull -ne 0) { throw "git pull --rebase не удался — разберись с рабочей копией" }
} finally {
    Pop-Location
}

# --- 2. Версия ---
$props = @{}
Get-Content $propsPath -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)$') { $props[$matches[1]] = $matches[2].Trim() }
}
$code = if ($VersionCode -gt 0) { $VersionCode } else { [int]$props["versionCode"] }
$name = if ($VersionName) { $VersionName } else { $props["versionName"] }

$publishedPath = Join-Path $appDir "latest.json"
if ((Test-Path $publishedPath) -and -not $Force) {
    $published = [System.IO.File]::ReadAllText($publishedPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($code -le [int]$published.versionCode) {
        throw "Уже опубликована версия $($published.versionName) (versionCode $($published.versionCode)). " +
              "Нужен versionCode больше — или -Force, если это осознанная перепубликация."
    }
}

[System.IO.File]::WriteAllText($propsPath, "versionCode=$code`nversionName=$name`n", $utf8)
Write-Host "Версия: $name (versionCode $code)" -ForegroundColor Cyan

# --- 3. Сборка ---
Push-Location $androidDir
try {
    & .\gradlew.bat assembleRelease --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Сборка завершилась с ошибкой" }
} finally {
    Pop-Location
}

# --- 4. Публикация файлов ---
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

# --- 5. Проверка перед пушем ---
& (Join-Path $androidDir "check-release.ps1")
if ($LASTEXITCODE -ne 0) { throw "check-release.ps1 нашёл проблемы — релиз не публикуем" }

if ($NoPush) {
    Write-Host "NoPush: коммит и пуш пропущены" -ForegroundColor Yellow
    return
}

# --- 6. Коммит и пуш (с повтором при гонке с ботом) ---
Push-Location $repoDir
try {
    if ((Invoke-Git @("add", "app", "android")) -ne 0) { throw "git add не удался" }
    if ((Invoke-Git @("commit", "-m", "Релиз $name ($code)")) -ne 0) {
        throw "Нечего коммитить или git недоступен"
    }

    $pushed = $false
    for ($attempt = 1; $attempt -le 3 -and -not $pushed; $attempt++) {
        if ((Invoke-Git @("pull", "--rebase", "origin", "main")) -ne 0) {
            throw "git pull --rebase не удался"
        }
        if ((Invoke-Git @("push", "origin", "main")) -eq 0) {
            $pushed = $true
        } else {
            Write-Host "Пуш отклонён (кто-то успел раньше), попытка $attempt из 3…" -ForegroundColor Yellow
            Start-Sleep -Seconds 3
        }
    }
    if (-not $pushed) { throw "Пуш не удался после 3 попыток" }
} finally {
    Pop-Location
}

# --- 7. Ждём, пока GitHub Pages отдаст новую версию ---
$base = "https://fvkhweb.github.io/movie-site/app/latest.json"
$live = $false
for ($i = 1; $i -le 12 -and -not $live; $i++) {
    Start-Sleep -Seconds 15
    try {
        $remote = Invoke-RestMethod -Uri ("$base?t=" + [DateTimeOffset]::Now.ToUnixTimeSeconds()) -TimeoutSec 20
        if ([int]$remote.versionCode -eq $code) { $live = $true }
    } catch {
        # Pages ещё собирается — это нормально
    }
}

if ($live) {
    Write-Host "Готово: https://fvkhweb.github.io/movie-site/app/latest.json" -ForegroundColor Green
} else {
    Write-Host "Запушено, но Pages пока не отдаёт версию $code — проверь через минуту:" -ForegroundColor Yellow
    Write-Host "  .\check-release.ps1 -Remote" -ForegroundColor Yellow
}
