# 04. Качество кода

## Тестовое покрытие

`coverage run --source=telegram_upload -m unittest discover` → `coverage report`. Запуск выполнен на Python 3.14.3, актуальные зависимости. Тесты при этом падают (см. ниже), но coverage всё равно собран.

```
Name                                                 Stmts   Miss  Cover
------------------------------------------------------------------------
telegram_upload/__init__.py                              3      0   100%
telegram_upload/_compat.py                              24     18    25%
telegram_upload/caption_formatter.py                   259     47    82%
telegram_upload/cli.py                                  88     29    67%
telegram_upload/client/__init__.py                       2      0   100%
telegram_upload/client/progress_bar.py                  12      0   100%
telegram_upload/client/telegram_download_client.py      84     19    77%
telegram_upload/client/telegram_manager_client.py      105     17    84%
telegram_upload/client/telegram_upload_client.py       188     43    77%
telegram_upload/config.py                               18      0   100%
telegram_upload/constants.py                             5      0   100%
telegram_upload/download_files.py                      115      7    94%
telegram_upload/exceptions.py                           47      5    89%
telegram_upload/logging_config.py                       35     11    69%
telegram_upload/management.py                          170     45    74%
telegram_upload/metadata_helpers.py                     44     18    59%
telegram_upload/upload_files.py                        172     18    90%
telegram_upload/utils.py                                57     11    81%
telegram_upload/video.py                                44      5    89%
------------------------------------------------------------------------
TOTAL                                                 1472    293    80%
```

**Слабее всего покрыты:**

- `_compat.py` (25%) — `anext` и старый-`scandir`. Реально не нужны, мёртвый компат.
- `metadata_helpers.py` (59%) — обвязка над hachoir, ветки error handling не тестируются.
- `cli.py` (67%) — интерактивные виджеты prompt_toolkit, тесты на них хрупкие.
- `logging_config.py` (69%) — настройка handlers, путь с file_handler не покрыт.
- `management.py` (74%) — CLI-команды; тестируются только happy paths (см. `tests/test_management.py:30-61`).
- Оба клиента upload/download (77%) — недотестирована retry-логика и пути ошибок.

**Покрыто хорошо:**
- `download_files.py` (94%), `upload_files.py` (90%) — модели и стратегии — самая стабильная часть.
- `exceptions.py` (89%), `video.py` (89%) — мелкие модули.
- `caption_formatter.py` (82%) — sandbox-формат покрыт неплохо ([tests/test_caption_formatter.py](../tests/test_caption_formatter.py) — 415 LOC, самый большой тестовый файл).

Среднее покрытие **80%** — для CLI-проекта это нормальная планка. Пробелы — в местах, где тестировать сложно (interactive UI, network retry, telethon mocks).

## Что тестируется и как

Только `unittest` (никакого pytest), 13 тестовых файлов, ~1400 LOC.

| Тип | Где | Что |
|---|---|---|
| Unit | `tests/test_caption_formatter.py` | `CaptionFormatter`, `Duration`, `FileSize`, `FilePath` — много case-based проверок, в т.ч. безопасность sandbox'а. |
| Unit | `tests/test_download_files.py` | `JoinStrategyBase`, `UnionJoinStrategy`, `DownloadFile`, `JoinDownloadSplitFiles` — вся stratery-логика split/join. |
| Unit | `tests/test_upload_files.py` | `File.file_caption` — буквально 30 строк, очень мало. |
| Unit | `tests/test_files.py` | `get_file_attributes`, `RecursiveFiles`, `NoDirectoriesFiles`, `NoLargeFiles`, `SplitFile`, `SplitFiles` — тестирует именно файл-итераторы, **не** класс `File`. |
| Unit | `tests/test_utils.py` | `sizeof_fmt`, `scantree`. Маленький файл (38 LOC). |
| Unit | `tests/test_video.py` | `video_metadata`, `get_video_thumb` через моки subprocess. |
| Unit | `tests/test_exceptions.py`, `test_config.py` | Тривиальные. |
| Integration-ish | `tests/test_management.py` | `click.testing.CliRunner` + моки `TelegramManagerClient` — проверяет, что команды парсятся и доходят до `send_files` / `download_files`. |
| Integration-ish | `tests/test_client/test_telegram_*_client.py` | Моки Telethon (`AsyncMock`, `IsolatedAsyncioTestCase`) для проверки `send_one_file`, `_send_album_media`, `_send_media`, retry-логика. |

**Что важно**: всё мокается через `unittest.mock` и `AsyncMock`. **Реальные сетевые вызовы Telegram нигде не проверяются**. Это разумно для CI, но означает, что любой реальный регресс на стороне Telethon API → проявится только на пользователе.

**Что недотестировано:**
- Параллельная загрузка (`upload_semaphore`, `_send_file_part` с retry / reconnect).
- `parse_proxy_string` — нет ни одного теста.
- `interactive_select_*` функции в `management.py`.
- `setup_logging` — нет теста на env-переменные.
- `get_file_thumb` (полный цикл video → ffmpeg → файл).

## Запуск тестов на Python 3.14

`python -m unittest discover` → **136 тестов, 1 failure, 27 errors** (Python 3.14.3, deps из `requirements.txt`).

Группы падений:

### 1. `caption_formatter.FilePath` сломан на Python ≥3.12 — критично

23 ошибки в `tests/test_caption_formatter.py` (все методы `TestFilePath.*`):

```
AttributeError: type object 'WindowsFilePath' has no attribute '_from_parts'
  File "telegram_upload/caption_formatter.py", line 302, in __new__
    self = cls._from_parts(args)
```

В Python 3.12 `pathlib` был переделан, и приватный метод `Path._from_parts` удалён. Реализация `FilePath.__new__` ([caption_formatter.py:299-306](../telegram_upload/caption_formatter.py#L299-L306)) опирается на этот метод. **Это значит, что `--caption "{file.size} ... {file.md5}"` падает на актуальных Python.**

Та же ошибка валит ещё 2 теста в `tests/test_upload_files.py::TestFile.test_file_caption` (caption-режим зовёт `FilePath`).

### 2. `cli.py` сломан на актуальном `prompt_toolkit` — interactive mode не работает

```
AttributeError: 'IterableRadioList' object has no attribute 'container_style'
  File "telegram_upload/cli.py", line 102, in _init
    style=self.container_style,
```

В `prompt_toolkit` 3.x `_DialogList` стал атрибут `container_style`-полем уровня класса в зависимости от темы; `IterableDialogList` ([cli.py:29](../telegram_upload/cli.py#L29)) имитирует часть инициализации `_DialogList.__init__`, но не вызывает родительский конструктор → атрибут не выставляется. Видимо, прогон когда-то проходил на старом `prompt_toolkit` ≤ 3.0.36.

**Это значит, что `--interactive` режим на свежем prompt_toolkit полностью неработоспособен.**

### 3. `tests/test_caption_formatter.py::TestTestCaptionFormat` — failure

`AssertionError: 0 != 1` на `result.exit_code`. Это следствие падения `FilePath`.

### Что работает

- Все тесты на `upload_files` (за исключением `test_file_caption` с caption).
- `download_files` — все ок (94% coverage сохранился).
- `test_management` — все ок (моки скрывают реальные проблемы).
- `test_client` — все ок.
- `test_utils`, `test_video`, `test_exceptions`, `test_config` — все ок.

## Линтеры и type checking

В проекте линтеры **не настроены**, кроме декларативной заглушки `[flake8]` в `setup.cfg:17-18` (`exclude = docs`). В `Makefile:50-51`:
```
lint: ## check style with flake8
    flake8 telegram_upload tests
```
но `flake8` не указан в `requirements-dev.txt`.

Прогон `ruff check telegram_upload/` (default ruleset) — **16 errors**:

| Код | Кол-во | Что |
|---|---|---|
| F401 | 3 | Unused imports (в `_compat.py:2,9` — `sys`, `scandir`). |
| F541 | 7 | f-strings без подстановок ([upload_client.py:338,369,374,415,417](../telegram_upload/client/telegram_upload_client.py#L338) и др.). Косметика, автофиксится. |
| F821 | 6 | Undefined name `hints` — сломанные string annotations ([upload_client.py:166,174](../telegram_upload/client/telegram_upload_client.py#L166), [download_client.py:63,64,68](../telegram_upload/client/telegram_download_client.py#L63)). |

10 из 16 правятся `ruff check --fix`. Remaining 6 (F821) — нужно либо удалить `'hints.*'` annotations, либо добавить `if TYPE_CHECKING: from telethon import hints` (в Telethon 1.x стаб `hints` определён в `telethon.hints`).

`mypy` не запускался автором проекта (нет конфига, нет в deps). Прогонять `mypy --ignore-missing-imports telegram_upload` без подготовки — будет много шума из-за отсутствующих type hints на параметрах.

В коде есть `SyntaxWarning` на Python 3.12+:
```
telegram_upload/video.py:41: SyntaxWarning: "\d" is an invalid escape sequence
    matchs = re.findall("(\d{2,6})x(\d{2,6})", video_lines[0])
```
Регулярка должна быть raw-строкой `r"(\d{2,6})x(\d{2,6})"`. На 3.14 это пока warning, но в будущих версиях станет SyntaxError.

## Сложные функции (radon CC)

Прогон `radon cc -a -s telegram_upload/`. Среднее CC = **A (2.68)**, что низко. Но есть индивидуальные пики:

| Функция / метод | Файл:строка | CC | Оценка |
|---|---|---|---|
| `TelegramDownloadClient._download_file` | [download_client.py:61](../telegram_upload/client/telegram_download_client.py#L61) | **20** | C |
| `management.upload` | [management.py:149](../telegram_upload/management.py#L149) | **19** | C |
| `TelegramUploadClient.upload_file` | [upload_client.py:164](../telegram_upload/client/telegram_upload_client.py#L164) | **19** | C |
| `management.get_file_display_name` | [management.py:40](../telegram_upload/management.py#L40) | **15** | C |
| `CaptionFormatter.get_field` | [caption_formatter.py:319](../telegram_upload/caption_formatter.py#L319) | **12** | C |
| `metadata_helpers.get_video_metadata_stream` | [metadata_helpers.py:15](../telegram_upload/metadata_helpers.py#L15) | **11** | C |
| `TelegramUploadClient.send_files` | [upload_client.py:118](../telegram_upload/client/telegram_upload_client.py#L118) | **11** | C |
| `TelegramManagerClient.__init__` | [telegram_manager_client.py:96](../telegram_upload/client/telegram_manager_client.py#L96) | **10** | B |
| `JoinDownloadSplitFiles.get_iterator` | [download_files.py:186](../telegram_upload/download_files.py#L186) | **9** | B |
| `TelegramUploadClient._send_file_part` | [upload_client.py:349](../telegram_upload/client/telegram_upload_client.py#L349) | **9** | B |
| `download` (CLI) | [management.py:218](../telegram_upload/management.py#L218) | **9** | B |
| `parse_proxy_string` | [telegram_manager_client.py:71](../telegram_upload/client/telegram_manager_client.py#L71) | **8** | B |
| `UnionJoinStrategy.join_download_files` | [download_files.py:81](../telegram_upload/download_files.py#L81) | **8** | B |
| `get_video_thumb` | [video.py:46](../telegram_upload/video.py#L46) | **8** | B |
| `Duration.for_humans` | [caption_formatter.py:60](../telegram_upload/caption_formatter.py#L60) | **7** | B |
| `File.get_thumbnail` | [upload_files.py:200](../telegram_upload/upload_files.py#L200) | **7** | B |

Ничего катастрофического, но `_download_file`, `upload`, `upload_file` стоит порефакторить — они длинные и принимают по 7-9 параметров.

## Дублирование кода

- **`grouper`** реализован дважды:
  - Свой в [utils.py:17-23](../telegram_upload/utils.py#L17-L23), `def grouper(n, iterable)`.
  - Импорт `more_itertools.grouper` в [download_client.py:10](../telegram_upload/client/telegram_download_client.py#L10), `grouper(iterable, n)`.
  - Сигнатуры разные. Используют оба. Стоит выбрать один.
- **Constants для caption length** дублируются:
  - `MAX_CAPTION_LENGTH_FREE = 1024`, `MAX_CAPTION_LENGTH_PREMIUM = 2048` в [constants.py:17-18](../telegram_upload/constants.py#L17-L18).
  - `USER_MAX_CAPTION_LENGTH = 1024`, `PREMIUM_USER_MAX_CAPTION_LENGTH = 2048` в [telegram_manager_client.py:44-45](../telegram_upload/client/telegram_manager_client.py#L44-L45).
  - Реально используются вторые, первые мёртвые (с комментарием «can be moved here»).
- **`get_file_attribute`** для DocumentAttributeFilename:
  - `get_message_file_attribute(message)` в [telegram_manager_client.py:53-55](../telegram_upload/client/telegram_manager_client.py#L53-L55).
  - `DownloadFile.filename_attr` в [download_files.py:124-128](../telegram_upload/download_files.py#L124-L128).
  - Логика идентична (`next(filter(lambda x: isinstance(x, DocumentAttributeFilename), attributes), None)`).
- **`sizeof_fmt`** есть в [utils.py:26-31](../telegram_upload/utils.py#L26-L31) и **отдельно** в `FileSize.for_humans` ([caption_formatter.py:124-130](../telegram_upload/caption_formatter.py#L124-L130)). Семантика одна, реализации дрейфят (`%3.1f%s%s` vs `f"{num:3.1f} {unit}{suffix}"`).
- **Cached_property fallback** в трёх местах: [telegram_manager_client.py:35-38](../telegram_upload/client/telegram_manager_client.py#L35-L38), [download_files.py:8-11](../telegram_upload/download_files.py#L8-L11), [caption_formatter.py:27-30](../telegram_upload/caption_formatter.py#L27-L30).

## Прочие смущающие места

- **`File(FileIO)`** ([upload_files.py:159](../telegram_upload/upload_files.py#L159)) — открывает файл в `__init__`, не закрывает в нормальном пути. Тесты не проверяют, что fd не утекают.
- **`os.environ.get(..., '~/.config')` + `os.path.expanduser`** ([config.py:6-8](../telegram_upload/config.py#L6-L8)) — env-переменная читается единожды на импорте, не учитывается изменение в runtime.
- **`asyncio.get_event_loop()`** в [cli.py:61, :82](../telegram_upload/cli.py#L61) — на Python 3.12+ выдаёт `DeprecationWarning`, на 3.14 при отсутствии активного loop'а выкидывает. В контексте prompt_toolkit обычно есть loop, но это всё равно тревожное место.
- **Регулярки без `r"..."`** в `video.py:38, 41` — `SyntaxWarning` на свежих Python.
- **`exit(...)`** вместо `sys.exit(...)` ([exceptions.py:75](../telegram_upload/exceptions.py#L75)) — `exit` это `site.Quitter`, не предназначен для production.
- **`raise StopAsyncIteration`** без аргументов в [_compat.py:67](../telegram_upload/_compat.py#L67) — корректно, но бесполезный re-raise после `except`.

## CI/CD

GitHub Actions:

| Workflow | Что делает | Статус |
|---|---|---|
| `.github/workflows/test.yml` | На push: `python -m unittest discover` для py 3.7-3.11 на ubuntu-latest. Comments: `flake8` закомментирован, `coverage`/`codecov` тоже. | Работает, но матрица старая (3.7, 3.8 EOL). Без линтеров. |
| `.github/workflows/publish.yml` | На push (с тегом): `python setup.py sdist bdist_wheel`, `twine check`, публикация на PyPI. | Работает. Использует `setup.py sdist` — устаревший подход. |
| `.github/workflows/docker.yml` | На release: build + push на Docker Hub. | Зависит от секретов `DOCKER_USERNAME`/`DOCKER_PASSWORD` форка. |
| `.github/workflows/pip-rating.yml` | Раз в неделю: `Nekmo/pip-rating` action — рисует SVG-бейдж в ветку `pip-rating-badge`. | Это action автора апстрима; форку, скорее всего, не нужен. |

Все используют `actions/checkout@v2` и `actions/setup-python@v2` — устаревшие версии (актуальные v4/v5).

## Открытые вопросы

- Нужно ли восстановить `--interactive` режим (поправить `cli.py` под актуальный prompt_toolkit) или это редкий use-case, который можно отрезать?
- Стоит ли заменить `unittest` на `pytest` для упрощения?
- Какой минимальный Python таргетировать в форке (3.10? 3.11? 3.12?) — это сильно влияет на возможность вычистить весь компат-код.
- Хочется ли довести coverage до 90%+, или 80% «достаточно»?
