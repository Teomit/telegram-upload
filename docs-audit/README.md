# Аудит репозитория `telegram-upload`

Глубокое разбирательство форка [`Nekmo/telegram-upload`](https://github.com/Nekmo/telegram-upload) — Python-CLI для загрузки/скачивания файлов через personal Telegram account (Telethon, MTProto). Цель аудита — подготовить почву для дальнейшей доработки в форке.

## Оглавление

| # | Документ | Кратко |
|---|---|---|
| 0 | [00-overview.md](00-overview.md) | Карта проекта: назначение, точки входа (`telegram-upload`/`telegram-download` через `entry_points`), дерево директорий, ключевые внешние зависимости (Telethon, click, hachoir, prompt_toolkit и др.), граф межмодульных зависимостей в виде Mermaid-диаграммы. |
| 1 | [01-architecture.md](01-architecture.md) | Архитектурные слои (CLI → domain → client → infrastructure), sequence-диаграмма потока upload, разбор сильных сторон (Strategy, retry, MI-фасад) и слабых (`click.echo` в client-слое, `File(FileIO)` god-объект, хардкод магических чисел, скопированные методы Telethon). Что именно мешает расширяемости. |
| 2 | [02-patterns.md](02-patterns.md) | Применённые GoF-паттерны (Strategy/Iterator/Decorator/Facade/Mixin/Template Method/Sandbox/Factory/Cached Property), Python-идиомы (async/await, контекст-менеджеры, typing — где работает, где broken `'hints.*'` annotations), стиль обработки ошибок, антипаттерны (длинные функции, дублирование `grouper`/констант, мёртвый компат-код). |
| 3 | [03-dependencies.md](03-dependencies.md) | Каждая прямая зависимость: pinned-версия vs актуальная PyPI на 2026-04-27, breaking changes (особенно Telethon 1.24→1.43, переезд на Codeberg, готовящаяся v2), CVE-проверка (`pip-audit` — clean), совместимость Python 3.12/3.13/3.14. Главный риск — приватные импорты из Telethon, hachoir, prompt_toolkit. |
| 4 | [04-quality.md](04-quality.md) | Coverage = 80% (запущено на Py 3.14). Из 136 тестов **28 падают** на актуальной среде: `caption_formatter.FilePath` сломан на Python ≥3.12 (`_from_parts` удалён), `--interactive` сломан на актуальном prompt_toolkit (`container_style`). `ruff check` — 16 ошибок. Топ-10 функций с CC ≥7 (`upload_file` CC=19, `_download_file` CC=20). Дублирование кода. |
| 5 | [05-fork-readiness.md](05-fork-readiness.md) | **Самый важный файл для форка.** Список с приоритетами и оценками S/M/L: 🔥 Критичное (7 пунктов — то, что сломано прямо сейчас), ⚠ Важное (10 пунктов — приватные API, скопированный Telethon, длинные функции, типы), 💡 Желательное (12 пунктов — pyproject.toml, ruff/pre-commit, pytest, mypy, удаление мёртвого компат-кода), 🤔 На подумать (6 архитектурных рефакторингов). Плюс рекомендованный порядок работ. |
| 6 | [06-extension-points.md](06-extension-points.md) | Карта точек расширения: (1) Strategy-семейства с регистрацией в dict — самые удобные, (2) наследование клиентов с таблицей переопределяемых методов, (3) расширение `CaptionFormatter` whitelist, (4) добавление CLI-команд, (5) env-переменные. Где **нет** удобных hook'ов: progress-bar, lifecycle callbacks, thumbnail-генератор, абстракция над Telegram. Что трогать осторожно: код-форк Telethon, sandbox CaptionFormatter, retry/reconnect в `_send_file_part`. Готовые рецепты: свой прогресс-бар, retry-policy, hook-после-загрузки. |

## TL;DR

- Версия проекта: **0.7.1** (август 2023, апстрим заброшен).
- Кодовая база: ~**2000 LOC** в 18 модулях, тесты ~1400 LOC (coverage 80%).
- На свежей среде (Python 3.12+, актуальные deps) **критично сломано:** `--caption` с `{file.*}` (pathlib API), `--interactive` (prompt_toolkit API). Всё остальное (upload, download, split, join, proxy, album, thumbs) — работает.
- **Ключевой риск долгосрочной поддержки:** проект ныряет в **приватные API** трёх библиотек (Telethon `_FileStream`/`_maybe_await`, hachoir `_MultipleMetadata__groups`, prompt_toolkit `_DialogList`) и содержит **скопированные методы Telethon** для параллельной загрузки. Любой апгрейд этих библиотек может тихо сломать.
- **Архитектура** — обычная для Python CLI 2018-2023 годов: setup.py + Makefile, unittest, без линтеров в CI, без type-check, click + Telethon. Не плохо, но не современно.
- **Готовность к форку:** хорошая. Точки расширения через Strategy чистые, MI-фасад тестируем. Стоит начинать с пакета фиксов 🔥-приоритета (Python 3.12+, current deps, ruff baseline) — после этого база годная для дальнейшей разработки.

## Что не вошло в аудит

- Нет глубокого ревью документации в `docs/` (Sphinx). Беглый осмотр показал стандартный setup; усохшая документация не критична для форка.
- Не запускались реальные сетевые тесты против Telegram — это требует api_id/api_hash и аккаунта.
- Не проверялся Docker-образ на сборку — `Dockerfile` тривиален, но `python:3.9.7` базовый образ устарел.
- Не профилировалась производительность реальной загрузки — есть `docs/upload_benchmark.py`, но запуск требует Telegram-аккаунта.

## Открытые вопросы (сводка)

Каждый документ заканчивается своими вопросами. Самые крупные:

- **Минимальный Python для форка** (3.10? 3.11? 3.12?) — определит, можно ли вычистить весь компат-код.
- **Готовность ломать публичный API** — позволит перейти на pyproject.toml, переименовать пакет, сменить CLI-флаги.
- **Закладываемся на Telethon v2** или замораживаемся на v1? — определяет, есть ли смысл вкладываться в адаптерный слой над Telethon.
- **Какие расширения планируются** (свой движок? новый источник файлов? hooks для интеграции с другой системой?) — определяет, какие архитектурные рефакторинги из R1-R6 действительно нужны.
