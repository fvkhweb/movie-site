# Каталог релизов приложения

**Это единственное место, откуда раздаются обновления Android-приложения.**
GitHub Pages отдаёт файлы по адресам:

- `https://fvkhweb.github.io/movie-site/app/latest.json` — манифест версии
- `https://fvkhweb.github.io/movie-site/app/WhatToWatch-<версия>.apk` — сам APK

## Правила

- Здесь всегда **один** APK — последняя версия. Старые удаляются при публикации.
- `latest.json` **генерируется** скриптом `android/release.ps1`. Руками не править.
- Не создавай рядом других манифестов (`update.json`, `version.json`, `releases/`) —
  приложение знает только про `latest.json`.
- Формат манифеста и порядок выпуска описаны в `../AGENTS.md`.

## Как отдать APK человеку

Не копируй файлы из `android/app/build/outputs/` — там промежуточные сборки Gradle,
в том числе debug-версия с другим ключом подписи. Правильно:

```powershell
cd ..\android
.\give-apk.ps1
```

Скрипт возьмёт APK отсюда, проверит версию/размер/подпись и положит копию
в `Downloads` с именем `WhatToWatch-<версия>.apk`.


## Проверка

```powershell
cd ..\android
.\check-release.ps1 -Remote
```
