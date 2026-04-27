# 00. Карта проекта

## Назначение

`telegram-upload` — CLI-утилита, которая использует **personal Telegram account** (через MTProto, библиотека Telethon), чтобы загружать и скачивать файлы через Telegram. Не путать с Bot API (где есть лимит 50 МБ): пользователь авторизуется как обычный аккаунт, и тогда лимит — 2 ГиБ для бесплатных и 4 ГиБ для Premium. Telegram-чат превращается в персональное «облако».

В отличие от обёрток вокруг Bot API, проект упирается в нестандартные нюансы протокола: ручная нарезка файла на чанки, параллельная загрузка частей, ручной retry при `FloodWaitError` и `RPCError`, верификация размера документа после загрузки и т.д. Это и есть основное содержимое проекта.

Версия в коде: [telegram_upload/__init__.py:7](../telegram_upload/__init__.py#L7) — `__version__ = '0.7.1'`. Последний релиз апстрима — август 2023.

## Точки входа

`setup.py` ([setup.py:139-144](../setup.py#L139-L144)) объявляет два console_scripts:

```python
"telegram-upload = telegram_upload.management:upload_cli"
"telegram-download = telegram_upload.management:download_cli"
```

Обе команды — обёртки `catch(...)` ([telegram_upload/management.py:250-251](../telegram_upload/management.py#L250-L251)) над click-командами `upload` и `download` из того же модуля. `catch` ловит `TelegramUploadError`, печатает stderr и завершает процесс с `error_code` исключения ([telegram_upload/exceptions.py:65-76](../telegram_upload/exceptions.py#L65-L76)).

В `Dockerfile:15` запуск идёт напрямую через модуль:
```dockerfile
ENTRYPOINT ["/usr/local/bin/python", "/app/telegram_upload/management.py"]
```
То есть в Docker ту же `management.py` вызывают как `python management.py upload <args>` или `download <args>`. Раздвоение CLI обработано в `__main__`-блоке ([telegram_upload/management.py:254-271](../telegram_upload/management.py#L254-L271)).

## Дерево директорий

```
telegram-upload/
├── telegram_upload/                    # основной пакет (прод-код, ~2000 LOC)
│   ├── __init__.py                     # __version__
│   ├── _compat.py                      # бэкпорт scandir, anext (для Python <3.10)
│   ├── caption_formatter.py            # шаблонизатор подписей (FilePath, Duration, FileSize, ...)
│   ├── cli.py                          # интерактивный TUI поверх prompt_toolkit
│   ├── client/
│   │   ├── __init__.py                 # реэкспорт TelegramManagerClient
│   │   ├── progress_bar.py             # прогресс-бар click
│   │   ├── telegram_download_client.py # скачивание (chunked, parallel)
│   │   ├── telegram_manager_client.py  # фасад: чтение config, proxy, auth
│   │   └── telegram_upload_client.py   # загрузка (chunked, parallel, retry)
│   ├── config.py                       # ~/.config/telegram-upload.json
│   ├── constants.py                    # магические числа, вынесенные в один модуль
│   ├── download_files.py               # модель DownloadFile + стратегии join (split-файлы)
│   ├── exceptions.py                   # иерархия исключений + decorator catch
│   ├── logging_config.py               # setup_logging(), DEFAULT_LOG_FORMAT
│   ├── management.py                   # CLI-команды click (upload/download)
│   ├── metadata_helpers.py             # безопасные обёртки над hachoir
│   ├── upload_files.py                 # модели File, SplitFile + iterator-стратегии
│   ├── utils.py                        # async/sync helpers, sizeof_fmt, scantree
│   └── video.py                        # ffmpeg, hachoir, генерация thumb
├── tests/                              # unit-тесты на unittest, 13 файлов, ~1400 LOC
│   ├── _compat.py                      # бэкпорт patch для старых Python
│   ├── test_*.py                       # по одному на каждый prod-модуль (не все)
│   └── test_client/                    # тесты на классы клиента
├── docs/                               # Sphinx-документация (RST), бенчмарки, conf.py
├── .github/workflows/                  # 4 workflow: tests, publish, docker, pip-rating
├── Dockerfile                          # python:3.9.7 base, два volume (/config, /files)
├── Makefile                            # стандартный cookiecutter, lint/test/coverage/docs
├── tox.ini                             # py37-py310 + pep8 env
├── setup.py / setup.cfg                # legacy сборка через setuptools
├── requirements.txt / -dev.txt         # прямые зависимости с верхними границами
├── .bumpversion.cfg                    # bump2version
├── .codeclimate.yml                    # минималистичный (просто Python: true)
└── travis_pypi_setup.py                # архаизм, Travis давно заменён GitHub Actions
```

## Ключевые внешние зависимости

| Пакет | Версия (pin) | Роль в архитектуре |
|---|---|---|
| `telethon` | `>=1.24.0,<2.0.0` | Сам клиент Telegram MTProto. От него наследуются `TelegramUploadClient`/`TelegramDownloadClient` ([telegram_upload/client/telegram_upload_client.py:27](../telegram_upload/client/telegram_upload_client.py#L27)). Из неё же импортируется внутренний `helpers._FileStream`, `crypto.AES`, `tl.functions.upload.SaveBigFilePartRequest` — это уже **близко к границе публичного API**. |
| `click` | `>=8.0.0,<9.0.0` | CLI-парсер ([telegram_upload/management.py:115](../telegram_upload/management.py#L115)), interactive prompts ([telegram_upload/config.py:13-17](../telegram_upload/config.py#L13-L17)), progress bar ([telegram_upload/client/progress_bar.py:7](../telegram_upload/client/progress_bar.py#L7)). |
| `cryptg` | `>=0.4.0,<1.0.0` | Опциональная C-обёртка над AES-IGE/IGE-256 — Telethon её автоматически подхватывает для ускорения шифрования (∼5x на больших файлах). Используется не напрямую. |
| `hachoir` | `>=3.0.0,<4.0.0` | Извлечение метаданных видео (длительность, ширина, высота). См. [telegram_upload/video.py:7-8](../telegram_upload/video.py#L7-L8), [telegram_upload/metadata_helpers.py](../telegram_upload/metadata_helpers.py), [telegram_upload/caption_formatter.py:139-185](../telegram_upload/caption_formatter.py#L139-L185). |
| `prompt_toolkit` | `>=3.0.0,<4.0.0` | Интерактивный TUI (`--interactive`): чекбокс-листы, скролл, мышь. Хитрый момент — наследуется от **внутреннего** `_DialogList` ([telegram_upload/cli.py:10](../telegram_upload/cli.py#L10)), это тоже выход за публичный API. |
| `pysocks` | `>=1.7.1,<2.0.0` | Парсинг proxy-строк типа `socks5://user:pass@host:port`. Импортируется лениво ([telegram_upload/client/telegram_manager_client.py:80](../telegram_upload/client/telegram_manager_client.py#L80)). |
| `more-itertools` | `>=8.0.0,<10.0.0` | `grouper` для нарезки на чанки ([telegram_upload/client/telegram_download_client.py:10](../telegram_upload/client/telegram_download_client.py#L10)). Свой собственный `grouper` тоже есть ([telegram_upload/utils.py:17](../telegram_upload/utils.py#L17)) — дублирование. |
| `packaging` | `>=21.0` | Замена устаревшего `distutils.version` для сравнения версий Telethon ([telegram_upload/client/telegram_manager_client.py:24-28](../telegram_upload/client/telegram_manager_client.py#L24-L28)). |
| `natsort` | (опционально) | Импорт `try/except ImportError` ([telegram_upload/management.py:21-23](../telegram_upload/management.py#L21-L23)) — сортировка `--sort` файлов в естественном порядке. |
| `ffmpeg` | (внешний бинарь) | Не Python-зависимость. Используется через `subprocess.Popen` ([telegram_upload/video.py:21-30](../telegram_upload/video.py#L21-L30)) для генерации миниатюр. Без `ffmpeg` отваливается генерация thumbnails, но код продолжает работать. |
| `scandir` | (Python<3.6 only) | Бэкпорт ([telegram_upload/_compat.py:7-9](../telegram_upload/_compat.py#L7-L9)) — мёртвая ветка, поддерживаемые Python давно содержат `os.scandir`. |
| `cryptg`, `pysocks` | — | См. выше |

Dev: `bumpversion`, `sphinx-click`, `tox>=1.8`, `codecov`, `mock`, `asyncmock`, `async-case` (последние три — для Python<3.8). Линтеров в dev-deps нет (есть только пустая секция `[flake8]` в `setup.cfg:17`).

## Граф зависимостей между модулями проекта

```mermaid
graph TD
    management[management.py<br/>CLI entry]
    cli[cli.py<br/>interactive TUI]
    config[config.py]
    excs[exceptions.py]
    logcfg[logging_config.py]
    utils[utils.py]
    constants[constants.py]
    compat[_compat.py]
    upload_files[upload_files.py<br/>File, SplitFiles]
    download_files[download_files.py<br/>DownloadFile, JoinStrategy]
    captionfmt[caption_formatter.py<br/>FilePath, Formatter]
    metahelpers[metadata_helpers.py]
    video[video.py<br/>ffmpeg + hachoir]

    subgraph client_pkg [client/]
        manager[telegram_manager_client.py<br/>TelegramManagerClient]
        upload_client[telegram_upload_client.py<br/>TelegramUploadClient]
        download_client[telegram_download_client.py<br/>TelegramDownloadClient]
        progressbar[progress_bar.py]
    end

    management --> cli
    management --> manager
    management --> config
    management --> upload_files
    management --> download_files
    management --> excs
    management --> logcfg
    management --> utils

    cli --> utils

    manager --> upload_client
    manager --> download_client
    manager --> excs
    manager --> config

    upload_client --> progressbar
    upload_client --> excs
    upload_client --> upload_files
    upload_client --> utils

    download_client --> progressbar
    download_client --> excs
    download_client --> utils
    download_client --> compat

    upload_files --> captionfmt
    upload_files --> constants
    upload_files --> excs
    upload_files --> metahelpers
    upload_files --> utils
    upload_files --> video

    captionfmt --> constants
    captionfmt --> metahelpers
    captionfmt --> video

    excs --> config
    utils --> compat
    utils --> excs
```

Граф **почти без циклов**, но есть один важный обратный край: `exceptions.py` импортирует `config.prompt_config` ([telegram_upload/exceptions.py:8](../telegram_upload/exceptions.py#L8)), потому что `catch` рекурсивно перевызывает CLI после повторного ввода API-ключей. Это рабочее, но нетипичное решение — обычно exceptions-модуль не должен дёргать побочные эффекты.

## Открытые вопросы

- Планируется ли поддержка Bot API параллельно с user-аккаунтом, или останется только MTProto?
- Нужна ли совместимость с уже сохранёнными `.session`-файлами при возможных мажорных апгрейдах Telethon?
- Какие платформы важны для запуска (Linux/macOS/Windows/Docker)? `setup.py:32-42` декларирует только Linux, но `video.py:30` явно ветвится на Windows (`ffmpeg.exe`).
