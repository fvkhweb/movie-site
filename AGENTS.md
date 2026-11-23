# AGENTS.md — правила для людей и ИИ-агентов

Единственный источник правды о том, как в этом репозитории собираются, версионируются
и раздаются обновления Android-приложения. Читай целиком перед изменениями.
Если правило мешает — обнови этот файл, а не обходи его.

## Что это за проект

- `movie-site/` — статический сайт «Что посмотреть?» (HTML/CSS/JS + JSON-данные).
  Живёт на GitHub Pages: https://fvkhweb.github.io/movie-site/
- `movie-site/android/` — нативное Android-приложение (Kotlin + Jetpack Compose),
  повторяет сайт 1:1: тёмная тема, сетка 2/4/5 колонок, шрифты сайта.
- `movie-site/data/*.json` и `movie-site/posters/*.jpg` — данные. Их ежедневно
  обновляет GitHub Actions коммитом `update movies`. Руками не трогать.

## Железные правила

1. **Только нативное приложение.** Никаких PWA, WebView, «сайта в обёртке».
2. **Один каталог релизов: `movie-site/app/`.** Не создавай `releases/`, `dist/`,
   `downloads/`, `update.json`, `version.json`, `app-v2/` и подобное.
   Если нашёл такой — перенеси в `app/` и удали.
3. **Один источник версии: `android/version.properties`.** Не дублируй номер версии
   в других файлах.
4. **Один способ публикации: `android/release.ps1`.** Он сам собирает, подписывает,
   кладёт APK и `latest.json` в `app/`, коммитит и пушит.
5. **`applicationId` (`ru.fvkhweb.movies`) и ключ подписи менять нельзя.**
   Другая подпись = приложение не установится поверх, все обновления сломаются.
6. **Keystore и `keystore.properties` — вне git.** Никогда не коммить и не выкладывай.
7. **`app/latest.json` руками не редактируется** — только `release.ps1`.
8. **Людям отдаём только `app/WhatToWatch-<версия>.apk` или ссылку с Pages.**
   Debug-сборки (`app-debug.apk`) — только для локального теста, не для раздачи.
9. **APK человеку отдаётся командой `android/give-apk.ps1`.** Она берёт файл
   только из `app/`, проверяет его и копирует в `Downloads`. Путь
   `android/app/build/outputs/apk/...` — это временные файлы Gradle, а не раздача:
   оттуда ничего не отдаём и никому не называем.

## Карта репозитория

| Путь | Что внутри |
|:--|:--|
| `app/` | **Релизы**: `latest.json` + один APK. Раздаётся GitHub Pages |
| `android/version.properties` | Версия: `versionCode` / `versionName` |
| `android/release.ps1` | Сборка и публикация релиза |
| `android/check-release.ps1` | Проверка согласованности релиза |
| `android/give-apk.ps1` | Выдать человеку APK актуального релиза (копия в Downloads) |
| `android/keystore.properties` | Путь и пароли к ключу (в git не попадает) |
| `android/signing-fingerprint.txt` | SHA-256 сертификата подписи |
| `android/app/src/rustore/AndroidManifest.xml` | Манифест сборки для RuStore (без установки APK) |
| `android/app/src/main/java/ru/fvkhweb/movies/data/update/` | Клиент автообновления |
| `android/app/src/main/java/ru/fvkhweb/movies/ui/UpdateDialog.kt` | Диалог «вышла обнова» |
| `android/README.md` | Сборка, архитектура, ограничения |
| `index.html`, `app.js`, `style.css` | Сайт |
| `data/`, `posters/` | Данные сайта и приложения |

## Как выпустить обновление

```powershell
cd movie-site\android
.\release.ps1 -VersionCode 3 -VersionName 1.1.0 -Notes "Фильтр по странам","Плашка «скоро в кино»"
```

Что делает скрипт:

1. `git pull --rebase` — подтягивает свежие данные сайта.
2. Проверяет, что `versionCode` больше уже опубликованного (защита от отката).
3. Пишет версию в `version.properties`, собирает `assembleRelease`, подписывает ключом.
4. Копирует APK в `app/WhatToWatch-<версия>.apk`, удаляет предыдущий APK.
5. Генерирует `app/latest.json` (версия, ссылка, SHA-256, размер, заметки).
6. Коммитит `Релиз X.Y.Z (N)`, делает `pull --rebase`, пушит.
7. Ждёт, пока GitHub Pages отдаст новую версию.

Флаги: `-Force` — разрешить тот же/меньший `versionCode` (только для перепубликации),
`-NoPush` — собрать и положить файлы без коммита.

## Версия для RuStore

Отдельный build type без автообновления через GitHub:

```powershell
cd movie-site\android
.\gradlew.bat assembleRustore
```

Чем отличается от обычной release-сборки:

- нет разрешения `REQUEST_INSTALL_PACKAGES` и `FileProvider` (манифест
  `app/src/rustore/AndroidManifest.xml`);
- `BuildConfig.AUTOUPDATE_ENABLED = false`: проверка `latest.json`, скачивание и
  установка APK не запускаются, R8 вырезает код обновления;
- версия, `applicationId` и ключ подписи те же, что у обычной release-сборки,
  поэтому магазинная версия ставится поверх и наоборот.

APK для загрузки в консоль RuStore: `android/app/build/outputs/apk/rustore/app-rustore.apk`.
Это артефакт для магазина, людям его не раздаём.

`release.ps1` RuStore-сборку не публикует — загрузка в консоль RuStore вручную.
В RuStore нельзя отставать от версии на GitHub: при каждом релизе загружай туда
сборку с тем же `versionName` / `versionCode` из `version.properties`.

## Как отдать APK человеку

```powershell
cd movie-site\android
.\give-apk.ps1              # копия в C:\Users\<юзер>\Downloads
.\give-apk.ps1 -Dir D:\tmp  # копия в другую папку
```

Скрипт берёт **только** `app/WhatToWatch-<версия>.apk`, сверяет его с `latest.json`
и `signing-fingerprint.txt`, и копирует с тем же именем. Если проверка не прошла —
ничего не копирует.

**Нельзя** отдавать `android/app/build/outputs/apk/debug/app-debug.apk` и любые файлы
из `build/`: это промежуточные сборки Gradle. Debug-версия подписана другим ключом
(в системе видна как `1.0.1-debug`), она не обновится до release и не встанет поверх
установленного приложения.

## Контракт `app/latest.json`

```json
{
  "versionCode": 3,
  "versionName": "1.1.0",
  "apkUrl": "https://fvkhweb.github.io/movie-site/app/WhatToWatch-1.1.0.apk",
  "sha256": "64 hex-символа в нижнем регистре",
  "size": 2738505,
  "notes": ["строка 1", "строка 2"],
  "publishedAt": "2026-11-19T18:56:16Z"
}
```

- Приложение читает манифест с `Cache-Control: no-cache` и суффиксом `?t=<время>`.
- **Неизвестные поля игнорируются** — добавлять новые можно свободно.
- **Удалять и переименовывать поля нельзя**: старые версии приложения их ждут.
- `versionCode` сравнивается с `BuildConfig.VERSION_CODE`; обновление предлагается
  только если серверный больше.
- `sha256` проверяется после скачивания; подпись APK сверяется с установленной.

## Предупреждения антивируса — это нормально

Приложение просит `REQUEST_INSTALL_PACKAGES`, качает APK и запускает установщик.
Для Play Protect и сторонних антивирусов это шаблон «дроппера», поэтому при установке
и обновлении они показывают «Harmful app blocked» / «Опасно».

- Это **ложное срабатывание**: перед установкой проверяются SHA-256 файла и совпадение
  подписи с уже установленным приложением, чужой APK не установится.
- Не «лечится» правкой кода, кроме отказа от автоустановки (тогда установка идёт
  через браузер и разрешение не нужно).
- Пользователю: «More details» → «Install anyway», либо добавить приложение
  в исключения антивируса.
- **Не предлагай** убрать автообновление «ради антивируса» без явной просьбы:
  это осознанное решение владельца проекта.

## Проверка перед пушем и после

```powershell
cd movie-site\android
.\check-release.ps1          # локальная согласованность
.\check-release.ps1 -Remote  # ещё и то, что реально отдаёт GitHub Pages
```

Скрипт проверяет: JSON валиден, все поля на месте, APK существует, размер и SHA-256
совпадают, `version.properties` совпадает с манифестом, пакет/версия/подпись APK
правильные. Код возврата ≠ 0 — релиз битый, пушить нельзя.

## Сборка и тесты

```powershell
cd movie-site\android
.\gradlew.bat assembleDebug      # быстрая сборка для эмулятора
.\gradlew.bat assembleRelease    # то, что уходит людям
```

Debug-сборка имеет `versionName` с суффиксом `-debug` и подписана debug-ключом.
Она годится только для эмулятора/локального теста: ставится через
`adb install -r app\build\outputs\apk\debug\app-debug.apk`, людям не передаётся.

- JDK 17, Android SDK 35, AGP 8.7.3, Gradle 8.9, Kotlin 2.0.21.
- Путь с кириллицей требует `android.overridePathCheck=true` (уже в `gradle.properties`).
- Не перезаписывай UTF-8 Kotlin-файлы через PowerShell `Get-Content/Set-Content` —
  только через редактор с UTF-8.
- PowerShell-скрипты сохраняй **в UTF-8 с BOM**, иначе русский текст ломает парсер.

Эмулятор:

```powershell
$sdk = "$env:LOCALAPPDATA\Android\Sdk"
& "$sdk\emulator\emulator.exe" -avd "Medium_Phone_API_37.0" -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect
& "$sdk\platform-tools\adb.exe" install -r app\build\outputs\apk\debug\app-debug.apk
```

Координаты для тапов брать из `adb shell uiautomator dump` (реальные пиксели 1080×2400),
а не из скриншотов — они масштабируются.

## Что нельзя ломать

- **Формат данных.** `data/*.json` читают и сайт, и приложение. Новые поля — можно,
  удаление/переименование — только синхронно в обеих сторонах.
- **Офлайн-режим.** Приложение стартует из снимка в `filesDir/catalog` и догружает сеть.
- **Дизайн 1:1.** Тёмная тема, сетка 2/4/5, шрифты сайта, плашки на постерах.
- **Избранное** хранится в DataStore и должно переживать обновления.

## Если добавляешь новую систему обновлений

1. Замени старую, не оставляй две работающие параллельно.
2. Обнови: этот файл, `app/README.md`, контракт `latest.json`, `check-release.ps1`.
3. Проверь полный цикл на эмуляторе: установленная старая версия → публикация новой →
   диалог → скачивание → проверка подписи → установка.
4. Только после этого сообщай пользователю, что обновления работают.
