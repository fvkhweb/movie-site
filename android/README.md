# «Что посмотреть?» — Android-приложение

Нативная версия сайта [movie-site](https://fvkhweb.github.io/movie-site/) на Kotlin + Jetpack Compose.
Данные (каталог, актёры, подборки) приложение берёт с GitHub Pages, постеры кэширует на устройстве.

## Что уже есть

- **Главная** — выбор редакции, популярное, «На слуху сейчас», «Скоро в кино», жанры.
- **Каталог** — поиск по названию и актёрам, фильтры (жанр, год, рейтинг, исключение жанра),
  7 сортировок, «Случайный фильм», бесконечная прокрутка.
- **Жанры** — индекс жанров с количеством фильмов.
- **Подборки** — коллекции из `data/collections.json` с нумерованными постерами.
- **Избранное** — сохраняется на устройстве (DataStore), доступно офлайн.
- **Страница фильма** — кадр/бэкдроп, постер, рейтинги TMDB и Кинопоиска, жанры, страны,
  описание, факты, актёры, похожие фильмы, трейлер (YouTube), «поделиться».
- **Страница актёра** — фото и фильмография из каталога.
- **Офлайн** — при старте показывается локальный снимок данных, затем фоном подтягивается свежий;
  постеры и фото кэшируются на 400 МБ.

## Сборка

Требуется Android Studio (или JDK 17 + Android SDK с платформой 35).

```bash
cd android
./gradlew assembleDebug
```

APK: `android/app/build/outputs/apk/debug/app-debug.apk`.

Или в Android Studio: **Open** → папка `android` → Run ▶.

## Release и автообновление

Release-сборка подписывается ключом из `android/keystore.properties` (в git не попадает,
путь к файлу и пароли — там же). Без этого файла release соберётся debug-ключом.

Версия хранится в `android/version.properties`.

Выпуск обновления одной командой:

```powershell
cd android
.\release.ps1 -VersionCode 3 -VersionName 1.1.0 -Notes "Что нового 1","Что нового 2"
```

Скрипт собирает release-APK, кладёт его и `app/latest.json` в корень репозитория,
коммитит и пушит. GitHub Pages раздаёт файлы:

- `https://fvkhweb.github.io/movie-site/app/latest.json`
- `https://fvkhweb.github.io/movie-site/app/WhatToWatch-<версия>.apk`

Приложение при запуске (не чаще раза в 6 часов) сравнивает `versionCode` из манифеста
со своим и показывает диалог «Вышла обнова». Дальше — скачивание с прогрессом, проверка
SHA-256 и подписи APK, запуск системного установщика.

Первый раз на телефоне нужно разрешить установку из этого приложения (Android откроет
нужный экран сам) и подтвердить «Всё равно установить» в Play Protect.

Проверка релиза:

```powershell
.\check-release.ps1 -Remote
```

Правила для людей и ИИ-агентов — в `../AGENTS.md`.

## Сборка для RuStore

Отдельная сборка без автообновления через GitHub:

```powershell
./gradlew assembleRustore
```

APK: `android/app/build/outputs/apk/rustore/app-rustore.apk` — его загружают в
консоль RuStore. В этой версии нет `REQUEST_INSTALL_PACKAGES` и `FileProvider`,
а клиент автообновления отключён (`BuildConfig.AUTOUPDATE_ENABLED = false`).
Версия, `applicationId` и подпись совпадают с обычным релизом.

Версия в RuStore не должна отставать от версии на GitHub: при каждом релизе
загружай в магазин сборку с теми же `versionCode` и `versionName`.

## Как это устроено

```text
GitHub Pages (data/*.json + posters/*.jpg)
        │  OkHttp (дисковый HTTP-кэш 64 МБ)
        ▼
CatalogRepository ──► StateFlow<CatalogState> ──► MainViewModel ──► Compose-экраны
        │                                   │
   файловый снимок                    DataStore (избранное)
   (filesDir/catalog)                 Coil (кэш картинок 400 МБ)
```

- `data/` — модели, загрузка и кэширование каталога, избранное, адреса картинок.
- `ui/screens/` — экраны: главная, каталог, жанры, подборки, избранное, фильм, актёр.
- `ui/components/` — карточки, кнопки, чипсы, изображения с fallback-цепочкой.
- `ui/theme/` — цвета и шрифты сайта (Unbounded / Manrope / DM Mono).

Данные обновляются на сайте ежедневно через GitHub Actions — приложение подхватывает
изменения само, выпускать новую версию не нужно.

## Настройки, которые стоит поменять перед публикацией

| Что | Где |
|:--|:--|
| `applicationId` (`ru.fvkhweb.movies`) | `app/build.gradle.kts` |
| Название приложения | `app/src/main/res/values/strings.xml` |
| Иконка | `app/src/main/res/drawable-nodpi/ic_launcher_foreground.png` |
| Версия | `versionCode` / `versionName` в `version.properties` |
| Адрес данных | `Media.BASE` в `data/Media.kt` |
| Адрес манифеста обновлений | `AppUpdater.MANIFEST_URL` в `data/update/AppUpdater.kt` |

## Ограничения

- Трейлеры открываются в YouTube — из РФ он может работать нестабильно.
- Фото актёров и кадры идут через бесплатные зеркала TMDB (`wsrv.nl`, `imagetmdb.com`),
  постеры — с домена сайта.
- Минимальная версия Android — 8.0 (API 26).
