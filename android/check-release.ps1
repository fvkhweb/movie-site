# Проверка согласованности релиза.
#
#   .\check-release.ps1            # локально
#   .\check-release.ps1 -Remote    # плюс то, что реально отдаёт GitHub Pages
#
# Код возврата 0 — всё хорошо, 1 — есть ошибки (пушить нельзя).

param([switch]$Remote)

$ErrorActionPreference = "Stop"

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$androidDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $androidDir
$appDir = Join-Path $repoDir "app"
$manifestPath = Join-Path $appDir "latest.json"
$packageName = "ru.fvkhweb.movies"
$baseUrl = "https://fvkhweb.github.io/movie-site/app/"

$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Error([string]$text) { $script:errors.Add($text) }
function Add-Warning([string]$text) { $script:warnings.Add($text) }

if (-not (Test-Path $manifestPath)) {
    Write-Host "Нет app/latest.json — сначала выпусти релиз через release.ps1" -ForegroundColor Red
    exit 1
}

# --- манифест ---
try {
    $m = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
} catch {
    Write-Host "app/latest.json — невалидный JSON: $_" -ForegroundColor Red
    exit 1
}

foreach ($field in @("versionCode", "versionName", "apkUrl", "sha256", "size", "publishedAt")) {
    $value = $m.$field
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        Add-Error "latest.json: пустое или отсутствующее поле '$field'"
    }
}

if ([int]$m.versionCode -le 0) { Add-Error "latest.json: versionCode должен быть > 0" }
if ($m.sha256 -notmatch '^[0-9a-f]{64}$') {
    Add-Error "latest.json: sha256 должен быть 64 hex-символа в нижнем регистре"
}
if ($m.notes -isnot [array]) {
    Add-Error "latest.json: notes должен быть массивом строк (даже если строка одна)"
}

$apkUrl = [string]$m.apkUrl
if (-not $apkUrl.StartsWith($baseUrl)) {
    Add-Error "latest.json: apkUrl должен начинаться с $baseUrl"
}
$apkName = Split-Path $apkUrl -Leaf
$expectedName = "WhatToWatch-$($m.versionName).apk"
if ($apkName -ne $expectedName) {
    Add-Error "latest.json: имя APK '$apkName' не совпадает с версией (ожидается '$expectedName')"
}

# --- APK ---
$apkPath = Join-Path $appDir $apkName
if (-not (Test-Path $apkPath)) {
    Add-Error "в app/ нет файла $apkName"
} else {
    $length = (Get-Item $apkPath).Length
    if ([long]$m.size -ne $length) {
        Add-Error "size в latest.json ($($m.size)) не совпадает с файлом ($length)"
    }
    $hash = (Get-FileHash $apkPath -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne [string]$m.sha256) {
        Add-Error "sha256 не совпадает: в манифесте $($m.sha256), у файла $hash"
    }

    $apkFiles = @(Get-ChildItem $appDir -Filter "WhatToWatch-*.apk")
    if ($apkFiles.Count -gt 1) {
        Add-Warning "в app/ лежит несколько APK — должна остаться только последняя версия"
    }

    # --- версия в приложении ---
    $btRoot = Join-Path $env:LOCALAPPDATA "Android\Sdk\build-tools"
    $bt = if (Test-Path $btRoot) {
        Get-ChildItem $btRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
    } else { $null }

    if ($null -eq $bt) {
        Add-Warning "не найден Android build-tools — проверка APK (пакет, версия, подпись) пропущена"
    } else {
        $aapt = Join-Path $bt.FullName "aapt2.exe"
        if (Test-Path $aapt) {
            $badging = & $aapt dump badging $apkPath 2>$null
            $packageLine = $badging | Select-String "^package:" | Select-Object -First 1
            if ($packageLine) {
                $line = $packageLine.ToString()
                if ($line -match "name='([^']+)'" -and $matches[1] -ne $packageName) {
                    Add-Error "APK: packageName '$($matches[1])' вместо '$packageName'"
                }
                if ($line -match "versionCode='(\d+)'" -and [int]$matches[1] -ne [int]$m.versionCode) {
                    Add-Error "APK: versionCode $($matches[1]) != latest.json $($m.versionCode)"
                }
                if ($line -match "versionName='([^']*)'" -and $matches[1] -ne [string]$m.versionName) {
                    Add-Error "APK: versionName '$($matches[1])' != latest.json '$($m.versionName)'"
                }
            } else {
                Add-Warning "aapt2 не смог прочитать манифест APK"
            }
        } else {
            Add-Warning "aapt2 не найден — проверка пакета и версии пропущена"
        }

        $apksigner = Join-Path $bt.FullName "apksigner.bat"
        $fingerprintPath = Join-Path $androidDir "signing-fingerprint.txt"
        if ((Test-Path $apksigner) -and (Test-Path $fingerprintPath)) {
            $expected = (Get-Content $fingerprintPath -Raw).Trim().Replace(":", "").ToLower()
            $certs = & $apksigner verify --print-certs $apkPath 2>$null
            $digestLine = $certs | Select-String "SHA-256 digest:" | Select-Object -First 1
            if ($digestLine) {
                $actual = ($digestLine.ToString() -replace "^.*SHA-256 digest:\s*", "").Trim().Replace(":", "").ToLower()
                if ($actual -ne $expected) {
                    Add-Error "APK подписан другим ключом ($actual) — обновления не установятся!"
                }
            } else {
                Add-Error "APK не подписан"
            }
        } else {
            Add-Warning "apksigner или signing-fingerprint.txt не найдены — проверка подписи пропущена"
        }
    }
}

# --- version.properties ---
$propsPath = Join-Path $androidDir "version.properties"
$props = @{}
if (Test-Path $propsPath) {
    Get-Content $propsPath -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([^#=]+?)\s*=\s*(.*)$') { $props[$matches[1]] = $matches[2].Trim() }
    }
    if ([int]$props["versionCode"] -ne [int]$m.versionCode) {
        Add-Error "version.properties: versionCode $($props['versionCode']) != latest.json $($m.versionCode)"
    }
    if ($props["versionName"] -ne [string]$m.versionName) {
        Add-Error "version.properties: versionName '$($props['versionName'])' != latest.json '$($m.versionName)'"
    }
} else {
    Add-Error "нет android/version.properties"
}

# --- GitHub Pages ---
if ($Remote) {
    try {
        $remoteManifest = Invoke-RestMethod -Uri ($baseUrl + "latest.json?t=" + [DateTimeOffset]::Now.ToUnixTimeSeconds()) -TimeoutSec 30
        if ([int]$remoteManifest.versionCode -ne [int]$m.versionCode) {
            Add-Error "Pages отдаёт versionCode $($remoteManifest.versionCode), а в репозитории $($m.versionCode) — деплой не дошёл"
        }
        if ([string]$remoteManifest.sha256 -ne [string]$m.sha256) {
            Add-Error "Pages отдаёт другой sha256 — деплой не дошёл или файл подменён"
        }
    } catch {
        Add-Error "не удалось получить latest.json с GitHub Pages: $($_.Exception.Message)"
    }
}

# --- посторонние APK и манифесты ---
$stray = @(
    Get-ChildItem $repoDir -Recurse -File -Include *.apk, latest.json, update.json, version.json -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch "\\app\\" -and
            $_.FullName -notmatch "\\build\\" -and
            $_.FullName -notmatch "\\\.gradle\\" -and
            $_.FullName -notmatch "\\\.git\\"
        }
)
if ($stray.Count -gt 0) {
    Add-Warning ("APK/манифесты вне app/: " + (($stray | ForEach-Object { $_.FullName.Substring($repoDir.Length + 1) }) -join ", "))
}

# --- итог ---
foreach ($warning in $warnings) { Write-Host "ПРЕДУПРЕЖДЕНИЕ: $warning" -ForegroundColor Yellow }
foreach ($errorText in $errors) { Write-Host "ОШИБКА: $errorText" -ForegroundColor Red }

if ($errors.Count -gt 0) {
    Write-Host "Проверка не пройдена: $($errors.Count) ошиб." -ForegroundColor Red
    exit 1
}

Write-Host "OK: релиз $($m.versionName) (versionCode $($m.versionCode)) согласован" -ForegroundColor Green
exit 0
