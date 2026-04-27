# 06. Куда вшиваться

Карта реальных точек расширения проекта — где безопасно врезаться, где нет.

---

## Естественные точки расширения

### 1. Stratery-семейства через `__init_subclass__`-style маппинги

Самые «чистые» точки расширения. Достаточно добавить класс и зарегистрировать его в dict.

#### a) Стратегии split-загрузки/выгрузки крупных файлов

**Где:** [telegram_upload/upload_files.py:139-156](../telegram_upload/upload_files.py#L139-L156).
- Базовый класс: `LargeFilesBase`.
- Текущие реализации: `NoLargeFiles` (raises) и `SplitFiles` (бьёт на куски).
- Регистрация: [telegram_upload/management.py:30-33](../telegram_upload/management.py#L30-L33):
  ```python
  LARGE_FILE_MODES = {'fail': NoLargeFiles, 'split': SplitFiles}
  ```
- CLI: `--large-files <mode>`. Добавление новой стратегии — один класс + один ключ в dict + один вариант в `click.Choice`.

**Пример: split с шифрованием по AES-CBC**
```python
class EncryptedSplitFiles(LargeFilesBase):
    def process_large_file(self, file):
        for split_file in SplitFiles(self.client, [file]).process_large_file(file):
            yield encrypt_wrap(split_file)  # ваш wrapper
```

#### b) Стратегии join-сборки скачанных частей

**Где:** [telegram_upload/download_files.py:28-98](../telegram_upload/download_files.py#L28-L98).
- Базовый класс: `JoinStrategyBase`.
- Текущая реализация: `UnionJoinStrategy` (склеивает `.01`, `.02` и т.п. конкатенацией).
- Регистрация: [download_files.py:96-98](../telegram_upload/download_files.py#L96-L98):
  ```python
  JOIN_STRATEGIES = [UnionJoinStrategy]
  ```
- Выбор стратегии динамический через `is_applicable(download_file)`.

**Пример: ZIP-частей (zip-split)**
```python
class ZipSplitJoinStrategy(JoinStrategyBase):
    @classmethod
    def is_applicable(cls, download_file):
        return download_file.file_name.endswith(('.zip.001', '.z01'))
    def is_part(self, download_file): ...
    def join_download_files(self):
        # вызвать 7z или zipfile с recursive=True
        ...
JOIN_STRATEGIES.insert(0, ZipSplitJoinStrategy)  # перед UnionJoinStrategy
```

Это **самая удобная** точка расширения в проекте.

#### c) Стратегии обработки директорий

**Где:** [telegram_upload/upload_files.py:119-136](../telegram_upload/upload_files.py#L119-L136).
- Базовый: `UploadFilesBase`.
- Текущие: `RecursiveFiles` / `NoDirectoriesFiles`.
- Регистрация: [management.py:26-29](../telegram_upload/management.py#L26-L29).

Например, можно добавить `'flatten'` (вытащить все файлы без сохранения структуры) или `'parallel'` (обходить параллельно).

#### d) Download split modes

**Где:** [telegram_upload/download_files.py:156-211](../telegram_upload/download_files.py#L156-L211).
- Базовый: `DownloadSplitFilesBase`.
- Текущие: `KeepDownloadSplitFiles` / `JoinDownloadSplitFiles`.
- Регистрация: [management.py:34-37](../telegram_upload/management.py#L34-L37).

### 2. Наследование `TelegramUploadClient` / `TelegramDownloadClient`

Можно подменить любой метод. Все вызовы CLI идут через `TelegramManagerClient`, который наследует оба, поэтому достаточно подсунуть свой класс в `management.upload()`.

**Точки переопределения:**

| Метод | Файл:строка | Что можно поменять |
|---|---|---|
| `send_one_file(entity, file, send_as_media, thumb, retries)` | [upload_client.py:92-116](../telegram_upload/client/telegram_upload_client.py#L92-L116) | Свой retry-policy, кастомный progress, dry-run. |
| `send_files(entity, files, ...)` | [upload_client.py:118-162](../telegram_upload/client/telegram_upload_client.py#L118-L162) | Логика после успешной загрузки (forward, delete), своя обработка thumbnail. |
| `_send_file_message(entity, file, thumb, progress)` | [upload_client.py:55-64](../telegram_upload/client/telegram_upload_client.py#L55-L64) | Подменить набор атрибутов, протолкнуть `silent=True`, `schedule_date`. |
| `_send_media(...)` | [upload_client.py:66-90](../telegram_upload/client/telegram_upload_client.py#L66-L90) | Поведение для альбомов. |
| `upload_file(...)` | [upload_client.py:164-345](../telegram_upload/client/telegram_upload_client.py#L164-L345) | Сам chunked upload. **Опасно**: код-форк Telethon. |
| `_send_file_part(request, ...)` | [upload_client.py:349-391](../telegram_upload/client/telegram_upload_client.py#L349-L391) | Логика retry/reconnect отдельной части. |
| `download_files(entity, download_files, delete_on_success)` | [download_client.py:41-59](../telegram_upload/client/telegram_download_client.py#L41-L59) | Куда сохранять, что делать после загрузки. |
| `_download_file(...)` | [download_client.py:61-127](../telegram_upload/client/telegram_download_client.py#L61-L127) | Сам chunked download. **Опасно**: код-форк Telethon. |
| `find_files(entity)` / `iter_files(entity)` | [download_client.py:29-39](../telegram_upload/client/telegram_download_client.py#L29-L39) | Фильтрация файлов в чате (по mime, по дате, по имени). |
| `start(...)` | [telegram_manager_client.py:140-151](../telegram_upload/client/telegram_manager_client.py#L140-L151) | Свой prompt для phone/code/password (например, чтение из переменных). |

**Как подсунуть свой класс в CLI:**

В `management.py` `TelegramManagerClient` импортируется из `telegram_upload.client`. Самый чистый вариант — после фикса `__init__.py` добавить параметр-фабрику или env-переменную.

Сейчас же можно просто **monkey-patch перед запуском**:
```python
import telegram_upload.management as m
class MyClient(m.TelegramManagerClient):
    def send_one_file(self, ...):
        ...  # custom
m.TelegramManagerClient = MyClient
m.upload_cli()
```

### 3. CaptionFormatter — расширение whitelist'а

**Где:** [telegram_upload/caption_formatter.py:35-40](../telegram_upload/caption_formatter.py#L35-L40):
```python
AUTHORIZED_METHODS = (Path.home,)
AUTHORIZED_STRING_METHODS = ("title", "capitalize", ...)
AUTHORIZED_DT_METHODS = ("astimezone", "ctime", ...)
```
И [caption_formatter.py:34](../telegram_upload/caption_formatter.py#L34):
```python
VALID_TYPES: Tuple[Any, ...] = (str, int, float, complex, bool, datetime.datetime, datetime.date, datetime.time)
```

Чтобы добавить переменную в caption (например, `{tags}` или `{file.exif.gps}`):
1. Расширить `FilePath`/`FileMixin` свойствами.
2. Если возвращаемый тип нестандартный — добавить в `VALID_TYPES`.
3. Если хочется вызывать метод (`{file.basename()}`) — добавить в `AUTHORIZED_STRING_METHODS`.

Любые расширения автоматически становятся доступны в `--caption`.

### 4. CLI-команды через `click`

**Как добавить новую CLI-команду:**

1. В `telegram_upload/management.py` — `@click.command()` с опциями.
2. В `setup.py:139-144` — добавить entry point:
   ```python
   "telegram-list = telegram_upload.management:list_cli"
   ```
3. Обернуть в `catch(...)` для единого обработчика ошибок.

После `pip install -e .` команда сразу доступна в shell.

### 5. Хуки через env-переменные (на этапе init)

Все runtime-параметры читаются на module-import:
- `TELEGRAM_UPLOAD_PARALLEL_UPLOAD_BLOCKS` ([upload_client.py:19](../telegram_upload/client/telegram_upload_client.py#L19))
- `TELEGRAM_UPLOAD_PARALLEL_DOWNLOAD_BLOCKS` ([download_client.py:25](../telegram_upload/client/telegram_download_client.py#L25))
- `TELEGRAM_UPLOAD_MAX_RECONNECT_RETRIES`, `TELEGRAM_UPLOAD_RECONNECT_TIMEOUT`, `TELEGRAM_UPLOAD_MIN_RECONNECT_WAIT`
- `TELEGRAM_UPLOAD_LOG_LEVEL`, `TELEGRAM_UPLOAD_LOG_FILE`
- `TELEGRAM_UPLOAD_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY`
- `TELEGRAM_UPLOAD_CONFIG_DIRECTORY` ([config.py:6](../telegram_upload/config.py#L6))
- `FFMPEG_COMMAND` ([video.py:29](../telegram_upload/video.py#L29))

Низкоуровневая, но **рабочая** точка кастомизации без изменения кода. Если хочется ещё — добавлять туда же.

---

## Где **нет** удобных точек расширения

Чтобы не тратить время на попытки.

### 1. Прогресс-бар жёстко зашит на `click.progressbar`

[telegram_upload/client/progress_bar.py:6-16](../telegram_upload/client/progress_bar.py#L6-L16):
```python
def get_progress_bar(action, file, length):
    bar = click.progressbar(label='{} "{}"'.format(action, file), length=length)
    ...
```
Нельзя извне передать свой прогресс-репортер. Вызывается в:
- `TelegramUploadClient.send_one_file` ([upload_client.py:95](../telegram_upload/client/telegram_upload_client.py#L95))
- `TelegramDownloadClient.download_files` ([download_client.py:49](../telegram_upload/client/telegram_download_client.py#L49))

**Как обойти:** monkey-patch `progress_bar.get_progress_bar` или унаследоваться от клиентов и переопределить `send_one_file`/`download_files`.

**Лучшее решение:** добавить параметр `progress_factory: Callable[[str, str, int], tuple] = get_progress_bar` в конструктор клиента.

### 2. Нет hooks/callbacks для жизненного цикла upload/download

Нет `before_upload`, `after_upload`, `on_progress`, `on_error`. Только переопределение методов через наследование (см. выше).

**Лучшее решение:** добавить набор optional-параметров `progress_callback`, `pre_send_callback`, `post_send_callback`. Уже есть один встроенный — `progress_callback` в Telethon, но он внутренний.

### 3. Thumbnail-генерация хардкодит ffmpeg

[telegram_upload/upload_files.py:81-93](../telegram_upload/upload_files.py#L81-L93):
```python
def get_file_thumb(file: str) -> Optional[str]:
    if get_file_mime(file) == 'video':
        return get_video_thumb(file)
    return None
```
Нет реестра «по mime → как делать thumb». Нет hooks.

**Лучшее решение:** ввести `ThumbnailStrategy` (см. R3 в `05-fork-readiness.md`).

### 4. `File` неотделим от `FileIO`

`File(FileIO)` ([upload_files.py:159](../telegram_upload/upload_files.py#L159)) открывает реальный путь в `__init__`. Чтобы загрузить, например, BytesIO или генератор — нужно либо подменять `File`, либо ломать иерархию. Нет «чистого» интерфейса для произвольного источника.

**Лучшее решение:** ввести `FileSource` интерфейс (см. R1 в `05-fork-readiness.md`).

### 5. Telethon торчит наружу повсюду

Прямые импорты `telethon.tl.types`, `telethon.tl.functions`, `telethon.errors` — в 7+ модулях. Нет адаптерного слоя. Чтобы поменять движок — переписывать половину проекта.

---

## Что трогать осторожно

Места, где правки могут стрельнуть в неочевидных сценариях.

### 1. Код-форк Telethon

`upload_file` ([upload_client.py:164-345](../telegram_upload/client/telegram_upload_client.py#L164-L345), 182 строки) и `_download_file` ([download_client.py:61-127](../telegram_upload/client/telegram_download_client.py#L61-L127), 67 строк) — копии методов из Telethon с патчами для параллелизма. Любое изменение должно сохранять контракт с Telethon-инфраструктурой (`SaveFilePartRequest`, `_iter_download`). Перед правкой — изучить актуальную реализацию в Telethon, иначе можно нечаянно «ухудшить» апстрим-фиксы.

Покрытие тестами — 77%, но **реального e2e на Telegram нет**. Любая правка должна тестироваться руками на реальном аккаунте с большим файлом.

### 2. `CaptionFormatter.get_field` (sandbox)

[caption_formatter.py:319-338](../telegram_upload/caption_formatter.py#L319-L338). Это защита от RCE через user input в `--caption`. Любое расслабление whitelist'а должно сопровождаться явным комментарием и тестом.

`tests/test_caption_formatter.py` (415 LOC) покрывает sandbox хорошо — все правки прогонять через тесты.

### 3. `JoinDownloadSplitFiles.get_iterator`

[download_files.py:186-211](../telegram_upload/download_files.py#L186-L211), CC=9. Логика `current_join_strategy` плюс `else`-блок после `for` — нетривиальный поток. Тесты на это есть в `tests/test_download_files.py:65+`, прогонять при каждом изменении.

### 4. `TelegramUploadClient._send_file_part` reconnect/retry

[upload_client.py:349-391](../telegram_upload/client/telegram_upload_client.py#L349-L391). Семафор + reconnect + рекурсия. Слабо покрыто тестами (только happy path). Лезть в эту функцию — без тестового аккаунта рискованно.

### 5. `metadata_helpers.get_video_metadata_stream`

[metadata_helpers.py:15-69](../telegram_upload/metadata_helpers.py#L15-L69). Использует hachoir-приватный атрибут `_MultipleMetadata__groups`. Любой апгрейд hachoir может сломать. Покрытие 59% — самое слабое после `_compat.py`.

### 6. `cli.py` интерактивные виджеты

Уже сломаны (см. `04-quality.md` C2). При фиксе нужно тестировать на актуальном prompt_toolkit — ломкая зона.

### 7. `async_to_sync` в `utils.py`

[utils.py:43-62](../telegram_upload/utils.py#L43-L62) — после фикса корректный, но при вызове из уже запущенного loop'а кидает `RuntimeError`. В CLI это нормально, но при использовании пакета как library из FastAPI-handler — упадёт. Если форк планируется как библиотека, эта функция требует переработки (использовать `asyncio.run_coroutine_threadsafe` или `nest_asyncio`).

### 8. Глобальные модульные константы

`PARALLEL_UPLOAD_BLOCKS = get_environment_integer(..., 4)` ([upload_client.py:19](../telegram_upload/client/telegram_upload_client.py#L19)) и подобные — читаются один раз при импорте. Изменить runtime'но нельзя. Если хочется per-call настройки — прокидывать через конструктор клиента.

---

## Сценарии расширения (рецепты)

### Рецепт 1: Свой прогресс-бар (в файл / WebSocket / БД)

```python
# my_progress.py
def my_get_progress_bar(action, file, length):
    class FakeBar:
        pos = 0; label = ''
        def update(self, current, _=None): print(f"{action} {file}: {current}/{length}")
        def render_finish(self): pass
    bar = FakeBar()
    def progress(current, total): bar.update(current); bar.pos = current
    return progress, bar

# main.py
from telegram_upload.client import progress_bar
progress_bar.get_progress_bar = my_get_progress_bar  # monkey-patch
from telegram_upload.management import upload_cli
upload_cli()
```

### Рецепт 2: Custom retry-policy с экспоненциальной задержкой

Унаследоваться от `TelegramUploadClient`, переопределить `send_one_file`. Прокинуть свой класс в `management.upload` (либо monkey-patch).

### Рецепт 3: Свой источник thumbnail

Переопределить `File.get_thumbnail` (наследование) либо `upload_files.get_file_thumb` (подмена). Лучше обернуть в `try/except ThumbError`, чтобы не ломать основной flow.

### Рецепт 4: Hook «после загрузки — записать в БД»

Унаследовать `TelegramUploadClient.send_files` ([upload_client.py:118](../telegram_upload/client/telegram_upload_client.py#L118)), вставить вызов своего callback'а после `messages.append(message)`.

### Рецепт 5: Загрузка с фильтрацией по содержимому (например, скан вирусов)

Обернуть итератор стратегии: создать свой `LargeFilesBase` потомок, который перед `yield` вызывает `is_safe(file)` и пропускает «грязные» файлы.

---

## Открытые вопросы

- Какие именно расширения планируются? (свой прогресс? hooks? свой движок?)
- Готов ли форк ломать публичный API (CLI-флаги, импорты), или нужно сохранять обратную совместимость?
- Будет ли пакет публиковаться на PyPI под собственным именем, или это in-house форк?
