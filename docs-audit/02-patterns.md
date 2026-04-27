# 02. Паттерны и идиомы

## Реально применённые паттерны проектирования

### 1. Strategy (стратегии итерирования и обработки)

Самый распространённый паттерн в проекте. Базовый класс задаёт интерфейс `get_iterator()`, потомки реализуют конкретную стратегию.

- Обработка директорий: `UploadFilesBase` → `RecursiveFiles` / `NoDirectoriesFiles` ([telegram_upload/upload_files.py:96-136](../telegram_upload/upload_files.py#L96-L136)).
- Обработка крупных файлов: `LargeFilesBase` → `NoLargeFiles` / `SplitFiles` ([telegram_upload/upload_files.py:139-156](../telegram_upload/upload_files.py#L139-L156), [:262-272](../telegram_upload/upload_files.py#L262-L272)).
- Скачивание split-файлов: `DownloadSplitFilesBase` → `KeepDownloadSplitFiles` / `JoinDownloadSplitFiles` ([telegram_upload/download_files.py:156-211](../telegram_upload/download_files.py#L156-L211)).
- Стратегии join'а split-файлов: `JoinStrategyBase` → `UnionJoinStrategy` ([telegram_upload/download_files.py:28-94](../telegram_upload/download_files.py#L28-L94)).

Связка со Strategy — **dict-маппинги в `management.py`** ([telegram_upload/management.py:26-37](../telegram_upload/management.py#L26-L37)):
```python
DIRECTORY_MODES = {'fail': NoDirectoriesFiles, 'recursive': RecursiveFiles}
LARGE_FILE_MODES = {'fail': NoLargeFiles, 'split': SplitFiles}
DOWNLOAD_SPLIT_FILE_MODES = {'keep': KeepDownloadSplitFiles, 'join': JoinDownloadSplitFiles}
```
Это эквивалент Factory с lookup'ом по строковому ключу из CLI.

### 2. Iterator

Каждый из `*FilesBase` реализует `__iter__` / `__next__` руками ([upload_files.py:109-116](../telegram_upload/upload_files.py#L109-L116), [download_files.py:165-174](../telegram_upload/download_files.py#L165-L174)). Внутри — обычный `yield`-генератор `get_iterator()`.

Решение немного избыточное: класс с состоянием хранит `_iterator`, но это используется только для отложенной материализации. Можно было бы заменить функциями-генераторами, не теряя функционала.

### 3. Decorator (Python decorator + GoF Decorator)

- `catch(fn)` ([telegram_upload/exceptions.py:65-76](../telegram_upload/exceptions.py#L65-L76)) — типичный Python-декоратор. Оборачивает CLI-команды, ловит `TelegramUploadError`, печатает stderr и выходит. Для `InvalidApiFileError` — рекурсивно вызывает себя после `prompt_config`.
- `MutuallyExclusiveOption(click.Option)` ([telegram_upload/management.py:83-112](../telegram_upload/management.py#L83-L112)) — кастомный `click.Option`, который проверяет несовместимые опции (`--no-thumbnail` и `--thumbnail-file`).

### 4. Facade

`TelegramManagerClient` ([telegram_upload/client/telegram_manager_client.py:95-171](../telegram_upload/client/telegram_manager_client.py#L95-L171)) — фасад над двумя клиентами через множественное наследование (`TelegramUploadClient, TelegramDownloadClient`). С точки зрения CLI он выглядит как единый клиент с методами `send_files`, `download_files`, `iter_files`, `iter_dialogs`, `find_files`, `start`.

### 5. Mixin (через MI)

Сами `TelegramUploadClient` и `TelegramDownloadClient` написаны как миксины — оба наследуют `telethon.TelegramClient` и добавляют свой набор методов. `TelegramManagerClient` соединяет их в diamond-наследовании. MRO разрешается без проблем, потому что миксины не пересекаются по имени.

### 6. Template Method

- `UploadFilesBase.__iter__` фиксирует «скелет» итерирования; конкретный `get_iterator` должен переопределить потомок ([upload_files.py:106-116](../telegram_upload/upload_files.py#L106-L116)).
- `LargeFilesBase.get_iterator` диспетчирует на `process_large_file()` / `process_normal_file()` ([upload_files.py:139-151](../telegram_upload/upload_files.py#L139-L151)).
- `JoinStrategyBase` ([download_files.py:28-52](../telegram_upload/download_files.py#L28-L52)) — `join_download_files`, `is_part`, `is_applicable` определяет потомок, общая бухгалтерия в базе.

### 7. Sandbox / Whitelist (для шаблонизатора)

`CaptionFormatter.get_field` ([caption_formatter.py:319-338](../telegram_upload/caption_formatter.py#L319-L338)) делает строгую проверку: атрибут не должен начинаться с `_`, метод должен быть в одном из whitelist'ов (`AUTHORIZED_METHODS`, `AUTHORIZED_STRING_METHODS`, `AUTHORIZED_DT_METHODS`), результат — только из `VALID_TYPES`. Это защита от того, чтобы пользователь в `--caption "{file.read}"` не выпрыгнул из песочницы. Нормальный осмысленный Sandbox-паттерн.

### 8. Factory function

`get_join_strategy(download_file)` ([download_files.py:101-109](../telegram_upload/download_files.py#L101-L109)) — простая фабрика: проходит по списку стратегий, возвращает первую `is_applicable`.

### 9. Cached Property

`@cached_property` используется в `TelegramManagerClient.me` ([telegram_manager_client.py:153-155](../telegram_upload/client/telegram_manager_client.py#L153-L155)), `DownloadFile.filename_attr`/`file_name` ([download_files.py:124-133](../telegram_upload/download_files.py#L124-L133)), `FilePath.video_metadata`/`size`/`media`/`mimetype`/`suffixes` (десяток мест в [caption_formatter.py:144-287](../telegram_upload/caption_formatter.py#L144-L287)).

С компат-фолбэком на обычный `property` для Python<3.8 — но Python 3.8+ обязателен по runtime-проверкам, так что фолбэк уже мёртвый.

## Идиомы Python

### async/await

Активно используется внутри клиентов:
- `async def upload_file`, `async def _send_file_part`, `async def _download_file`, `async def _send_media`, `async def reconnect`, `async def _send_album_media`.
- Параллелизм через `asyncio.Semaphore` (`upload_semaphore`, [telegram_upload_client.py:32](../telegram_upload/client/telegram_upload_client.py#L32)) и `asyncio.Lock` (`reconnecting_lock`, [:31](../telegram_upload/client/telegram_upload_client.py#L31)).
- Создание задач: `self.loop.create_task(...)`, ожидание — `asyncio.wait([... for task in asyncio.all_tasks() if ...])` ([telegram_upload_client.py:332-339](../telegram_upload/client/telegram_upload_client.py#L332-L339)). **Поиск задач по имени** — нетипично, но рабочее решение.
- Конвертер async↔sync: `async_to_sync` ([utils.py:43-62](../telegram_upload/utils.py#L43-L62)) — с проверкой на уже запущенный loop через `asyncio.get_running_loop()` и подъёмом `RuntimeError`. Сейчас (после фикса) корректный.
- `aislice` ([utils.py:65-73](../telegram_upload/utils.py#L65-L73)) и `amap` ([utils.py:76-78](../telegram_upload/utils.py#L76-L78)) — собственные async-аналоги `itertools.islice` и `map`.

### Контекст-менеджеры

- `with open(config_file, 'r', encoding='utf-8') as f:` ([telegram_manager_client.py:101](../telegram_upload/client/telegram_manager_client.py#L101)).
- `async with helpers._FileStream(file, file_size=file_size) as stream:` ([telegram_upload_client.py:259](../telegram_upload/client/telegram_upload_client.py#L259)) — async context manager Telethon.
- В `download_files.py:89` — `with open(self.get_base_name(...), "wb") as new_file:`.

Но в `File(FileIO)` ([upload_files.py:159-220](../telegram_upload/upload_files.py#L159-L220)) контекст-менеджер не используется: `File.__init__` открывает дескриптор, и закрытие происходит только при сборке мусора либо в тестах вручную через `file0.close()`.

### Дескрипторы / метаклассы

Не используются. Никаких `__get__`/`__set__`/`type(...)`-конструкций.

### dataclass

**Не используются.** Хотя `DownloadFile` и `File` — отличные кандидаты на `@dataclass`, проект написан в pre-dataclass-стиле (Python 3.6 вышел в 2016).

### typing

Использование умеренное и непоследовательное:

- `Union`, `Optional`, `List`, `Iterable`, `Iterator`, `Sequence`, `Tuple`, `TypeVar`, `Mapping`, `BinaryIO`, `Any` — встречаются.
- Forward references: `'TelegramManagerClient'`, `'File'`, `'DownloadFile'`, `'JoinStrategyBase'` ([upload_files.py:25-27](../telegram_upload/upload_files.py#L25-L27)).
- Неопределённые импорты: `'hints.FileLike'`, `'hints.OutFileLike'`, `'hints.ProgressCallback'` — это **сломанные string annotations**, унаследованные от Telethon-кода. `hints` нигде не импортирован → ruff F821 в 6 местах ([upload_client.py:166,174](../telegram_upload/client/telegram_upload_client.py#L166), [download_client.py:63,64,68](../telegram_upload/client/telegram_download_client.py#L63)). Stringified, поэтому в runtime не падает — но `mypy --strict` сразу зашьётся.
- В `caption_formatter.py:22-24` костыль для `LiteralString`: `try: from typing import LiteralString except ImportError: LiteralString = str`. Аналогично для `cached_property` (`if sys.version_info < (3, 8)` в нескольких местах).

### Прочее

- **f-strings** повсеместно (Python 3.6+).
- **`itertools.islice`** в `grouper` ([utils.py:17-23](../telegram_upload/utils.py#L17-L23)).
- **`functools` cached_property** — выше.
- **PathLib (`pathlib.Path`)** — в `caption_formatter.FilePath`, через `FileMixin(PosixPath/WindowsPath)`. Неординарное наследование от `Path` через `__new__` ([caption_formatter.py:298-314](../telegram_upload/caption_formatter.py#L298-L314)).

## Стиль обработки ошибок

### Иерархия исключений

[telegram_upload/exceptions.py](../telegram_upload/exceptions.py) определяет одну корневую `TelegramUploadError` с полями `body`, `error_code`, `extra_body`. От неё:

- `MissingFileError` (default code=1)
- `InvalidApiFileError` (code=1, доп. поле `config_file`) — особый: триггерит повторный prompt
- `TelegramInvalidFile` (code=3)
- `TelegramUploadNoSpaceError` (code=28)
- `TelegramUploadDataLoss` (code=29)
- `TelegramProxyError` (code=30)
- `TelegramEnvironmentError` (code=31)

Также отдельно — `ThumbError` / `ThumbVideoError` (без `error_code`, не подцепляются `catch`).

### Где ловятся

- На самой верхней границе CLI: `catch(fn)` ([exceptions.py:65-76](../telegram_upload/exceptions.py#L65-L76)) перехватывает `InvalidApiFileError` для повторного prompt'а и любую `TelegramUploadError` для печати + `exit(error_code)`. Соответственно `upload_cli`, `download_cli` обёрнуты ([management.py:250-251](../telegram_upload/management.py#L250-L251)).
- Точечные `try/except` в [telegram_manager_client.py:100-121](../telegram_upload/client/telegram_manager_client.py#L100-L121) — превращают `FileNotFoundError`/`json.JSONDecodeError`/`PermissionError`/`OSError` в осмысленные `TelegramUploadError`.
- В `upload_files.File.get_thumbnail` ([upload_files.py:202-206](../telegram_upload/upload_files.py#L202-L206)) — ловят `ThumbError` и просто печатают в stderr, не пробрасывая.
- В `parse_proxy_string` ([telegram_manager_client.py:79-82](../telegram_upload/client/telegram_manager_client.py#L79-L82)) — `try: import socks except ImportError`, превращается в `TelegramProxyError`.

### Голых `except:` нет

`grep -E '^\s*except\s*:'` по `telegram_upload/` — пусто. Все `except` хотя бы указывают тип. Это плюс.

### Антипаттерны

- **Recursion для retry**: `send_one_file` рекурсивно вызывает себя при `FloodWaitError`/`RPCError` ([upload_client.py:106-115](../telegram_upload/client/telegram_upload_client.py#L106-L115)). При большом числе ретраев это будет бесполезно расти стек. Лучше `for _ in range(retries)`.
- **`exit(...)` вместо `sys.exit(...)` или `click.exceptions.Exit`** ([exceptions.py:75](../telegram_upload/exceptions.py#L75)) — `exit` — это `site.Quitter`, не предназначен для production.
- **`bare RuntimeError`** ([upload_client.py:390](../telegram_upload/client/telegram_upload_client.py#L390)): `raise RuntimeError('Failed to upload file part {}.'.format(part_index))` — обходит всю иерархию `TelegramUploadError` и `catch` его не поймает.

## Логирование

`logging_config.setup_logging()` ([logging_config.py:17-89](../telegram_upload/logging_config.py#L17-L89)):
- Уровень из аргумента или env `TELEGRAM_UPLOAD_LOG_LEVEL`.
- Файл из аргумента или env `TELEGRAM_UPLOAD_LOG_FILE`.
- Формат `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`.
- Очищает существующие handlers (`logger.handlers.clear()`) перед добавлением — ОК.
- Отключает propagation (`logger.propagate = False`).

Но реально через `logger.debug/info` пишут только пара мест: [management.py:158](../telegram_upload/management.py#L158), [management.py:227](../telegram_upload/management.py#L227), [caption_formatter.py:336](../telegram_upload/caption_formatter.py#L336), [metadata_helpers.py:44,47,63,66](../telegram_upload/metadata_helpers.py#L44), [telegram_manager_client.py:21,27](../telegram_upload/client/telegram_manager_client.py#L21). В большинстве хот-плейсов вместо logging'а — `click.echo(..., err=True)`. Это смешение пользовательского UI и логов, которое усложняет встраивание в скрипты.

## Конфигурация

- JSON-файл (`api_id`, `api_hash`, опц. `session`) — `~/.config/telegram-upload.json`.
- Env-переменные:
  - `TELEGRAM_UPLOAD_CONFIG_DIRECTORY` ([config.py:6](../telegram_upload/config.py#L6))
  - `TELEGRAM_UPLOAD_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` ([telegram_manager_client.py:46-50](../telegram_upload/client/telegram_manager_client.py#L46-L50))
  - `TELEGRAM_UPLOAD_PARALLEL_UPLOAD_BLOCKS`, `TELEGRAM_UPLOAD_PARALLEL_DOWNLOAD_BLOCKS`
  - `TELEGRAM_UPLOAD_MAX_RECONNECT_RETRIES`, `TELEGRAM_UPLOAD_RECONNECT_TIMEOUT`, `TELEGRAM_UPLOAD_MIN_RECONNECT_WAIT`
  - `TELEGRAM_UPLOAD_LOG_LEVEL`, `TELEGRAM_UPLOAD_LOG_FILE`
  - `FFMPEG_COMMAND` ([video.py:29](../telegram_upload/video.py#L29))
- CLI-флаги — все через `click.option`.

## CLI-парсинг

`click.command` + `click.option`/`click.argument` ([management.py:115-148, :203-217](../telegram_upload/management.py#L115)). Нестандартное расширение — `MutuallyExclusiveOption` (см. выше).

## Антипаттерны и code smells

| # | Smell | Где | Что не так |
|---|---|---|---|
| 1 | God-object у фасада | `TelegramManagerClient` ([telegram_manager_client.py:95](../telegram_upload/client/telegram_manager_client.py#L95)) | Отвечает за чтение JSON, парсинг proxy, авторизацию, MTProxy, размер файлов, длину captions. |
| 2 | Длинные функции | `management.upload` (CC=19), `upload_file` (CC=19), `_download_file` (CC=20), `get_file_display_name` (CC=15) | См. цифры radon. |
| 3 | Дублирование кода | `grouper` в `utils.py:17-23` и тот же `grouper` импортируется из `more_itertools` в [download_client.py:10](../telegram_upload/client/telegram_download_client.py#L10) | Один используют, другой не используют — нужно выбрать один. |
| 4 | Дублирование констант | `MAX_CAPTION_LENGTH_FREE` в `constants.py:17` vs `USER_MAX_CAPTION_LENGTH` в `telegram_manager_client.py:44` | Идентичные значения, разные имена. |
| 5 | UI в инфраструктуре | `click.echo(...)` внутри `client/`-модулей | См. слой «Архитектура». |
| 6 | Глобальная env-конфигурация на уровне модуля | `PARALLEL_UPLOAD_BLOCKS = get_environment_integer(...)` ([upload_client.py:19](../telegram_upload/client/telegram_upload_client.py#L19)) | Невозможно переопределить runtime. |
| 7 | Скопированный сторонний код | `upload_file`, `_download_file` — копии Telethon-методов с патчами | Усложняет апгрейд Telethon. |
| 8 | Доступ к `_private` атрибутам сторонних либ | hachoir name-mangled, `prompt_toolkit._DialogList`, `helpers._FileStream`, `helpers._maybe_await` | Хрупко. |
| 9 | Мёртвые ветки совместимости | `try: from os import scandir except ImportError: from scandir import scandir` ([_compat.py:6-9](../telegram_upload/_compat.py#L6-L9)); `if sys.version_info < (3, 8): cached_property = property` (3 места); `requirements-dev.txt:7-8` (`mock`, `asyncmock`, `async-case` для py<3.8) | Поддерживаемые ныне Python — 3.9+. |
| 10 | Сломанные string annotations | `'hints.FileLike'`, `'hints.ProgressCallback'` ([upload_client.py:166-174](../telegram_upload/client/telegram_upload_client.py#L166), [download_client.py:63-72](../telegram_upload/client/telegram_download_client.py#L63)) | `hints` нигде не импортирован, ruff F821 ×6. |
| 11 | f-string без подстановок | 7 мест (ruff F541) — например, `[upload_client.py:338,369,374,415,417]` | Косметический шум, легко чинится автофиксом. |
| 12 | Циклы импорта на грани | `exceptions.py` импортирует `config.prompt_config` ([exceptions.py:8](../telegram_upload/exceptions.py#L8)), а `config.py` использует `click` | Работает, но непривычно. |
| 13 | Архаичная сборка | `setup.py` + `setup.cfg`, `Makefile` с `python setup.py test` ([Makefile:55](../Makefile#L55)) и `python setup.py sdist upload` ([:78](../Makefile#L78)) | `setup.py upload` поддержки PyPI нет с 2018. CI его не использует, но в Makefile он лежит. |
| 14 | Потенциальное некорректное закрытие файлов | `File(FileIO)` без `__exit__`-закрытия в путях ошибок | Возможна утечка fd при ошибке после `__init__`. |
| 15 | Непрозрачный side-effect в `File.file_caption` | `file_caption` это `@property`, но при каждом вызове строит `CaptionFormatter` заново и читает `datetime.datetime.now()` ([upload_files.py:188-198](../telegram_upload/upload_files.py#L188-L198)) | Каждый вызов даст разное время, но семантически это property. |

## Открытые вопросы

- Стоит ли переходить на `dataclass`/`pydantic` для domain-объектов (`File`, `DownloadFile`)?
- Нужна ли строгая typing-проверка (`mypy --strict`) или достаточно best-effort?
- Готовы ли отказаться от копий `upload_file`/`_download_file` и сделать pull request в Telethon (или искать альтернативу)?
