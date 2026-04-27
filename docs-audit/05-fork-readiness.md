# 05. Что чинить и улучшать в форке

Список с приоритетами. Оценки: **S** = ≤полдня, **M** = 1-3 дня, **L** = 4+ дней.

---

## 🔥 Критичное

То, что **сломано прямо сейчас** на свежем окружении (Python 3.12+ или последние версии зависимостей).

### C1. `caption_formatter.FilePath` падает на Python 3.12+ — `S`

**Симптом:** `AttributeError: type object 'WindowsFilePath' has no attribute '_from_parts'`. Любой запуск `--caption "{file.size} ..."` на Python ≥3.12 падает.

**Причина:** [caption_formatter.py:299-306](../telegram_upload/caption_formatter.py#L299-L306) переопределяет `__new__` через приватный `cls._from_parts(args)`, который удалён из `pathlib` в 3.12.

**Фикс:** заменить на `super().__new__(cls)` либо отказаться от наследования `Path`:
```python
class FilePath(FileMixin, Path):
    def __new__(cls, *args, **kwargs):
        if cls is FilePath:
            cls = WindowsFilePath if os.name == 'nt' else PosixFilePath
        return super().__new__(cls, *args, **kwargs)
```
В Python 3.12+ `Path.__new__` сам берёт нужный flavour.

**Затраты:** S. Уже есть 23 теста, которые сразу скажут «починилось».

### C2. `--interactive` режим сломан на актуальном `prompt_toolkit` — `M`

**Симптом:** `AttributeError: 'IterableRadioList' object has no attribute 'container_style'`. Любой `--interactive` падает.

**Причина:** `IterableDialogList._init` ([cli.py:35-110](../telegram_upload/cli.py#L35-L110)) подменяет `__init__` оригинального `_DialogList`, но в новом prompt_toolkit (≥3.0.40) часть атрибутов выставляется в исходном `__init__`. Также используется приватный класс `_DialogList`.

**Фикс:**
- Минимальный (S): инициализировать `container_style = "class:dialog.body"`, `default_style = "class:radio"`, `selected_style = "class:radio-selected"` и пр. — пройтись по тому, что внезапно перестало быть установленным.
- Правильный (M): выкинуть `_DialogList` целиком и собрать checkbox/radio вручную через публичные `Window` + `KeyBindings` + `FormattedTextControl` (всё это уже используется ниже в коде).

**Затраты:** S–M. Тесты покрывают (`tests/test_cli.py`).

### C3. Сломанные `'hints.*'` annotations → ruff F821 ×6 — `S`

**Симптом:** Сейчас не падает (string annotations), но любая попытка `mypy`/`pyright` сразу даст ошибки. И семантически неверно.

**Причина:** скопировано из Telethon, где есть локальный модуль `telethon.hints`. У нас — нет.

**Фикс:**
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from telethon import hints
```
В шести местах: [upload_client.py:166, :174](../telegram_upload/client/telegram_upload_client.py#L166), [download_client.py:63, :64, :68](../telegram_upload/client/telegram_download_client.py#L63).

**Затраты:** S.

### C4. Регулярки без `r"..."` → `SyntaxWarning` на 3.12+, `SyntaxError` в будущем — `S`

[video.py:38, :41](../telegram_upload/video.py#L38). Поправить на raw-strings.

**Затраты:** S.

### C5. Неактуальные версии actions в CI — `S`

`actions/checkout@v2`, `actions/setup-python@v2` (во всех 4 workflow). v2 уже выводят deprecation warnings на GitHub. Поднять до v4/v5.

**Затраты:** S.

### C6. CI-матрица ловит EOL-Python — `S`

`.github/workflows/test.yml:11` — `[3.7, 3.8, 3.9, "3.10", "3.11"]`. На сегодня все из них либо EOL, либо близки. Минимум — `[3.10, 3.11, 3.12, 3.13]`.

**Затраты:** S (но + время на фикс падений из C1, C2).

### C7. Pin `more-itertools<10.0.0` устарел — `S`

В новых средах `pip install -r requirements.txt` поставит 9.x, что уже не последняя. Вилка `>=8.0.0,<10.0.0`. Поднять до `<12.0.0` (либо вообще отказаться, у проекта есть свой `grouper`).

**Затраты:** S.

---

## ⚠ Важное

То, что не сломано прямо сейчас, но станет источником проблем в обозримом будущем (полгода-год) или содержит реальный риск.

### V1. Доступ к **приватным** API сторонних библиотек — `M`

Перечислено в `03-dependencies.md`: `helpers._FileStream`, `helpers._maybe_await`, `metadata._MultipleMetadata__groups`, `_DialogList`, `client.downloads.MIN_CHUNK_SIZE`. Любой минорный апгрейд может тихо сломать.

**Фикс:** инкапсулировать в один adapter-модуль (`telegram_upload/_telethon_internal.py`, `_hachoir_internal.py`, `_prompt_toolkit_internal.py`), там делать try/except и log warning при отсутствии. Концентрация хрупкости в одном месте.

**Затраты:** M.

### V2. Скопированные методы `upload_file`/`_download_file` Telethon — `L`

[upload_client.py:164-345](../telegram_upload/client/telegram_upload_client.py#L164-L345), [download_client.py:61-127](../telegram_upload/client/telegram_download_client.py#L61-L127). Это вилки внутренней реализации Telethon, добавляющие параллелизм. Мейнтейнить параллельно с upstream-Telethon — больно.

**Варианты:**
- **(L)** Вынести параллельную логику в чистые функции, использовать публичный `client.upload_file`/`client.download_media` и не лезть в `SaveBigFilePartRequest` напрямую. Возможно потеряем ~10-20% производительности.
- **(L)** Сделать PR в upstream Telethon для добавления `parallel_blocks` параметра.
- **(M)** Документировать, какие методы скопированы из какой версии Telethon, и при апгрейде — diff ревизионно сравнивать.

### V3. `click.echo` внутри `client/`-слоя — `M`

См. `01-architecture.md`. Сейчас — нормально, но при попытке использовать пакет как library будут лишние вылеты в stderr.

**Фикс:** заменить на `logger.info`/`logger.error` + опциональный callback. Стартовать с самых горячих мест ([upload_client.py:107, :112, :115, :369, :374, :415, :417](../telegram_upload/client/telegram_upload_client.py#L107)).

**Затраты:** M.

### V4. `TelegramManagerClient.__init__` слишком много делает — `M`

[telegram_manager_client.py:96-138](../telegram_upload/client/telegram_manager_client.py#L96-L138). Чтение и парсинг конфига, валидация, парсинг proxy — всё в одном. Вынести в `load_config(path)` и `parse_proxy(spec)` (последняя уже есть).

**Затраты:** M.

### V5. `management.upload` — длинная процедура (CC=19) — `M`

[management.py:149-200](../telegram_upload/management.py#L149-L200). Распилить на `_resolve_files(...)`, `_resolve_recipient(...)`, `_resolve_thumbnail(...)`, `_send(...)`. Плюс облегчит тестирование.

**Затраты:** M.

### V6. Type hints отсутствуют в публичном API — `M`

В большинстве функций нет аннотаций возвращаемых типов и параметров (особенно в `management.py`, `cli.py`, `client/*.py`). Если планируется использовать как библиотеку — IDE-навигация будет плохой.

**Фикс:** добавить минимальный набор аннотаций для публичных функций и методов. Можно прогнать `monkeytype` (запись типов в runtime), но проще руками.

**Затраты:** M.

### V7. Recursive retry → потенциальный stack overflow — `S`

[upload_client.py:106-115](../telegram_upload/client/telegram_upload_client.py#L106-L115). При большом числе FloodWait-ретраев стек растёт. Заменить на `for _ in range(retries)`.

**Затраты:** S.

### V8. `RuntimeError` обходит `catch` — `S`

[upload_client.py:390](../telegram_upload/client/telegram_upload_client.py#L390). `raise RuntimeError(...)` мимо иерархии `TelegramUploadError`. Заменить на отдельное доменное исключение типа `TelegramUploadPartError(TelegramUploadError)`.

**Затраты:** S.

### V9. `exit(...)` вместо `sys.exit(...)` — `S`

[exceptions.py:75](../telegram_upload/exceptions.py#L75). Замена тривиальна.

**Затраты:** S.

### V10. Дублирующийся `grouper` и константы — `S`

См. `04-quality.md`. Удалить self-grouper или избавиться от `more_itertools`. Удалить мёртвые константы из `constants.py`.

**Затраты:** S.

---

## 💡 Желательное

Современные практики, не критичные для функциональности, но окупающиеся в долгосрок.

### W1. Перейти на `pyproject.toml` (PEP 621) — `M`

Сейчас: `setup.py` (149 LOC), `setup.cfg`, `Makefile` с `python setup.py sdist` (deprecated с 2018).

**Фикс:** PEP 621 + `hatchling` или `setuptools` как build backend. Все мета-данные в один `pyproject.toml`. Удалить `setup.py`, `setup.cfg`, `Makefile`-таргеты `dist`/`release`.

**Затраты:** M. Безопасно: издаваемый wheel идентичен.

### W2. Перейти на `uv` или `hatch` для dev-окружения — `M`

`Makefile`, `tox.ini`, `requirements*.txt` — три разных способа управлять зависимостями. `uv` (или `hatch`) даёт один lock-файл и быструю установку.

**Затраты:** M.

### W3. Линтеры: `ruff` + `pre-commit` — `S`

Добавить `ruff.toml` (`select = ["E", "F", "W", "I", "B", "UP"]`), `.pre-commit-config.yaml` с `ruff check --fix`, `ruff format`. Заменить `flake8` декларации в `setup.cfg`.

**Затраты:** S.

### W4. Type checking: `mypy` или `pyright` — `M`

После W6 из «Важного» сделать запуск `mypy --strict telegram_upload/` обязательным шагом CI. Стартовать с `--no-strict` и постепенно повышать.

**Затраты:** M (после V6).

### W5. Заменить `unittest` на `pytest` — `M`

`pytest` короче (`test_x` без класса), удобные fixtures, `pytest-asyncio` упростит async-тесты вместо `IsolatedAsyncioTestCase`. Существующие тесты обычно переносятся one-to-one.

**Затраты:** M.

### W6. Добавить `pip-audit` в CI — `S`

```yaml
- run: pip install pip-audit
- run: pip-audit -r requirements.txt
```
Раз в неделю + на каждом push. Сейчас CVE нет, но вероятность появления растёт.

**Затраты:** S.

### W7. Современные docstring + Sphinx — `M`

Текущий `docs/conf.py` минимальный, `Makefile docs` собирает API-doc. Стоит:
- Добавить `myst-parser` для Markdown в Sphinx.
- Включить `intersphinx` на Telethon.
- Перевести README.rst → README.md (форки на GitHub лучше рендерят MD).

**Затраты:** M.

### W8. Заменить `bumpversion` → `bump-my-version` — `S`

Конфиг `.bumpversion.cfg` совместим с обоими.

**Затраты:** S.

### W9. Нормальное логирование вместо `click.echo(..., err=True)` — `M`

Уже частично рассмотрено в V3. Также `logger.warning` вместо click-печати. Структурированное логирование (`structlog`) — опционально.

**Затраты:** M.

### W10. Удалить мёртвые компат-ветки — `S`

Если форк начинает с Python 3.10+ (рекомендуется):
- `_compat.py` целиком (anext в 3.10+, scandir в 3.6+).
- Все `if sys.version_info < (3, 8): cached_property = property` (3 места).
- `mock`/`asyncmock`/`async-case` из `requirements-dev.txt`.
- `tests/_compat.py` (`patch`).
- В `setup.py`: `PYTHON_VERSIONS = ['3.10', '3.11', '3.12', '3.13']`.

**Затраты:** S.

### W11. Удалить `travis_pypi_setup.py` — `S`

[travis_pypi_setup.py](../travis_pypi_setup.py) — 4207 байт скрипта для Travis CI, которого в проекте давно нет. Удалить.

### W12. Docker-образ обновить базу — `S`

`Dockerfile:1` — `ARG python_version=3.9.7`. Поднять до `3.12-slim` или `3.13-slim`.

---

## 🤔 На подумать (рефакторинг архитектуры)

Из `01-architecture.md` — слабые места, которые можно адресовать, если планируется глубокое расширение.

### R1. Отделить «модель файла» от «открытого FileIO» — `L`

`File(FileIO)` — domain унаследован от низкоуровневого I/O. При попытке поддержать `URL → upload` или streaming с генератора — придётся ломать иерархию.

**Что предложить:** `FileSource` интерфейс с методами `open_stream() -> BinaryIO`, `size`, `name`, `attributes`. `LocalFileSource`, `URLFileSource`, ... — реализации. `File` становится координатором, не самим потоком.

**Затраты:** L. Эффект: открывает дорогу к новым источникам.

### R2. Hooks/callbacks в upload pipeline — `M`

Сейчас `send_one_file` — монолит. Хочется уметь вмешаться: `before_upload(file)`, `progress(current, total)`, `after_upload(message, file)`, `on_error(file, exc) -> Action`.

**Что предложить:** event-bus (как `pluggy`) или просто список callback'ов в конструкторе клиента.

**Затраты:** M.

### R3. Стратегии миниатюр и атрибутов — `M`

`get_file_thumb` ([upload_files.py:81-93](../telegram_upload/upload_files.py#L81-L93)) хардкодит ffmpeg-видео-thumbnail. Хочется уметь подменить логику на «возьми первый кадр PDF», «возьми обложку MP3», «сгенерируй превью кода».

**Что предложить:** `ThumbnailStrategy` базовый класс по аналогии с `JoinStrategyBase`. `VideoFFmpegThumbnail`, `ImageThumbnail`, `AudioCoverThumbnail` — отдельные классы. Регистрация в списке, выбор по `mime` или `is_applicable`.

**Затраты:** M.

### R4. Абстракция над Telegram-движком — `L`

Чтобы можно было поменять Telethon на Pyrogram (или Bot API). Введение интерфейса `TelegramBackend` с методами `send_file`, `download_file`, `iter_messages`, `iter_dialogs`. Нынешний код прячется за реализацию `TelethonBackend`.

**Затраты:** L. Имеет смысл только если есть реальная потребность в альтернативном backend'е.

### R5. Распилить `management.upload` на pipeline — `M`

См. V5.

### R6. Заменить класс-итераторы на функции-генераторы — `S`

`UploadFilesBase`, `DownloadSplitFilesBase` — лишний скелет. Простой generator function проще читается.

**Затраты:** S, но ломает API наследования. Сделать вместе с другими breaking changes.

---

## Рекомендованный порядок работ для форка

1. **(C1, C3, C4, C5, C6, C7, W11, W12, W10)** — один коммит, поднять Python-baseline до 3.10+, поправить все падения тестов на свежей среде. После этого CI зелёный на современных версиях.
2. **(W1)** Перейти на `pyproject.toml`. Сразу облегчает следующее.
3. **(W3, W6)** Завести ruff + pre-commit + pip-audit. Получить чистый baseline.
4. **(C2)** Поправить `--interactive`. Может занять день, потому что prompt_toolkit неприятный.
5. **(V7-V10)** Мелкие фиксы качества, идут в один PR.
6. **(V1)** Изолировать приватные API в `_internal.py`. Дальше эти места — единственные точки боли при апгрейдах.
7. **(V3, V4, V5)** Распилить толстые функции, развести UI и client.
8. **(V6, W4)** Добавить type hints + mypy в CI.
9. **(W5, W7, W8)** pytest, docs.md, bump-my-version.
10. **(R*)** Архитектурные рефакторинги — только если действительно нужны для конкретных фич.

## Открытые вопросы

- Какой минимальный Python таргетировать в форке? (3.10? 3.11? 3.12?)
- Поддерживать ли Docker-образ?
- Нужен ли публичный PyPI-пакет (со своим именем), или это внутренний форк?
- Готовность к breaking changes публичного API (если поднимать `pyproject.toml`, переименовывать пакет, менять CLI-флаги)?
- Сохранять ли совместимость по `~/.config/telegram-upload.json` (формат конфига)?
