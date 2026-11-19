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

## Проверка

```powershell
cd ..\android
.\check-release.ps1 -Remote
```
