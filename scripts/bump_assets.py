"""Версии ассетов по sha256: index.html (?v=) и DATA_VERSION в app.js.

Запуск из корня репозитория: python scripts/bump_assets.py
Идемпотентен: повторный запуск ничего не меняет.

DATA_VERSION лежит внутри app.js, поэтому его хеш считается от текста,
где строка версии заменена плейсхолдером. Иначе скрипт менял бы сам себя.
"""

import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app.js")
INDEX = os.path.join(ROOT, "index.html")
MOVIES = os.path.join(ROOT, "data", "movies.json")
STYLE = os.path.join(ROOT, "style.css")
FONTS = os.path.join(ROOT, "fonts", "fonts.css")

DATA_LINE = re.compile(r'(const DATA_VERSION = ")[^"]*(")')


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_if_changed(path, old, new):
    if old == new:
        return False
    with open(path, "wb") as f:
        f.write(new.encode("utf-8"))
    return True


def digest(data):
    return hashlib.sha256(data).hexdigest()[:8]


def set_version(source, name, value):
    pattern = re.compile(rf"({re.escape(name)}\?v=)[^\"'\s>]+")
    return pattern.sub(lambda m: m.group(1) + value, source)


def main():
    app_before = read_bytes(APP).decode("utf-8")
    # Версия в app.js не должна влиять на его же хеш
    app_hash = digest(DATA_LINE.sub('const DATA_VERSION = "__VERSION__"', app_before).encode("utf-8"))
    data_hash = digest(read_bytes(MOVIES))
    style_hash = digest(read_bytes(STYLE))
    fonts_hash = digest(read_bytes(FONTS))

    app_after = DATA_LINE.sub(lambda m: m.group(1) + data_hash + m.group(2), app_before)

    index_before = read_bytes(INDEX).decode("utf-8")
    index_after = index_before
    for name, value in (
        ("app.js", app_hash),
        ("style.css", style_hash),
        ("fonts/fonts.css", fonts_hash),
        ("data/movies.json", data_hash),
    ):
        index_after = set_version(index_after, name, value)

    changed = write_if_changed(APP, app_before, app_after)
    changed = write_if_changed(INDEX, index_before, index_after) or changed
    print(
        f"app.js {app_hash}, style.css {style_hash}, fonts.css {fonts_hash}, "
        f"data {data_hash}; обновлено файлов: {int(changed)}"
    )


if __name__ == "__main__":
    main()
