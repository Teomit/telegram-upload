# 03. Зависимости и их актуальность

Данные собраны через `pip index versions <pkg>` (PyPI mirror, дата проверки 2026-04-27) и веб для breaking changes. CVE проверены через `pip-audit -r requirements.txt`.

## Прямые зависимости

| Пакет | Pin | На PyPI сейчас | Δ мажоров | Статус | Комментарий |
|---|---|---|---|---|---|
| `telethon` | `>=1.24.0,<2.0.0` | **1.43.2** | 0 (внутри 1.x) | ⚠ | См. подробно ниже. v2 в разработке, не релизнут. |
| `click` | `>=8.0.0,<9.0.0` | **8.3.3** | 0 | ✅ | Совместимо. v9 не выпущен. |
| `cryptg` | `>=0.4.0,<1.0.0` | **0.6.0** | 0 | ✅ | Совместимо. C-расширение для AES-IGE; Telethon подхватывает автоматически. |
| `hachoir` | `>=3.0.0,<4.0.0` | **3.3.0** | 0 | ✅ | Совместимо. Но проект тянет name-mangled приватные атрибуты — потенциально хрупко. |
| `prompt_toolkit` | `>=3.0.0,<4.0.0` | **3.0.52** | 0 | ⚠ | В пределах диапазона. **Но**: проект использует приватный `_DialogList`, между минорными релизами это может ломаться. |
| `pysocks` | `>=1.7.1,<2.0.0` | **1.7.1** | 0 | ✅ | Версия не растёт с 2019 года. |
| `more-itertools` | `>=8.0.0,<10.0.0` | **11.0.2** | **+2** (10, 11) | ❌ | Pin отстаёт. См. ниже. |
| `packaging` | `>=21.0` | **26.2** | +5 (22-26) | ✅ | Pin без верхней границы, ставится свежее. |
| `scandir` | `python_version<'3.6'` | — | — | ☠ | Мёртвая ветка. Python 3.6+ имеет `os.scandir` встроенно. Удалить. |

## Опциональная зависимость

| Пакет | Импорт | На PyPI | Комментарий |
|---|---|---|---|
| `natsort` | `try/except ImportError` ([management.py:21-23](../telegram_upload/management.py#L21-L23)) | **8.4.0** | Используется только при `--sort`. Не указан в `requirements*.txt`. |

## Внешний бинарь (не Python)

| Утилита | Где вызывается | Как находится | Без неё |
|---|---|---|---|
| `ffmpeg` | [video.py:21-30](../telegram_upload/video.py#L21-L30) | env `FFMPEG_COMMAND` или `ffmpeg`/`ffmpeg.exe` в `PATH` | Поднимается `ThumbVideoError`, в `File.get_thumbnail` ловится и печатается в stderr — основной upload работает, но без миниатюр. |

## Dev-зависимости (`requirements-dev.txt`)

```
-r requirements.txt
bumpversion          # depricated, лучше bump2version или bump-my-version
sphinx-click         # генерация docs из click-команд
tox>=1.8             # очень старая нижняя граница (актуальные tox 4+)
codecov              # python-обёртка отозвана и удалена с PyPI ⚠
pysocks              # дублирует основную зависимость
mock; python_version < '3.6'             # мёртвая ветка
asyncmock; python_version < '3.8'        # мёртвая ветка
async-case; python_version < '3.8'       # мёртвая ветка
```

**Проблемы:**
- `codecov` (pip-пакет) [официально архивирован](https://github.com/codecov/codecov-python) — авторы рекомендуют `codecov-cli`. Пакет может пропасть с PyPI.
- `bumpversion` не обновляется с 2018 — стандартом стал `bump-my-version` или `bump2version`.
- `tox>=1.8` — нижняя граница из 2014 года; tox 4 (2022) изменил формат `tox.ini`.
- Линтеров (`flake8`, `ruff`, `mypy`) **нет в dev-deps**, хотя `setup.cfg:17-18` объявляет секцию `[flake8]` и `Makefile:50-51` пытается запустить `flake8`. То есть линтер декларирован, но не установлен — `make lint` упадёт без ручной установки.

## Telethon: подробно (главный риск)

Pin: `>=1.24.0,<2.0.0`. Установится 1.43.2.

**Текущая ситуация с библиотекой:**
- Репозиторий на GitHub архивирован 2026-02-21, активная разработка переехала на Codeberg: <https://codeberg.org/Lonami/Telethon>.
- v2 находится в работе, **публично ещё не выпущена** (на PyPI старший — 1.43.2). Это будет полная переработка с breaking changes.
- v1.x продолжает поддерживаться, но мейнтейнер замедлил темп.

**Breaking changes между 1.24 (минимум pin'а) и 1.43.2 (актуальная):**

1. **v1.31** — убрана зависимость от `imghdr` (готовность к Python 3.12, где `imghdr` удалён). При отправке `BytesIO` теперь требуется выставить `.name`. **На проект не влияет** напрямую — он отправляет через `File(FileIO)` с реальным path.
2. **v1.24** — 64-bit `user_id`/`chat_id`. Если есть код, хранящий ID в int32-колонках — сломается. **На проект не влияет**, ID не персистятся.
3. **v1.17** — формат SQLite-сессий обновлён, после апгрейда старая сессия не работает с младшим Telethon. Для пользователя проекта означает: после первого запуска свежей версии нельзя «откатить» на старую без перелогина.
4. **v1.16** — параметр `loop=` удалён. **На проект не влияет**, не используется.
5. **v1.7.1** — изменился способ скачивания PhotoSize. **На проект не влияет**, скачиваются документы.
6. **v1.6** — `iter_*` убрал параметр `_total`. **На проект не влияет**.

В версии **0.7.1** проекта уже было исправление `Issue #215: TypeError: __init__() got an unexpected keyword argument 'reply_to_msg_id'` ([HISTORY.rst:8](../HISTORY.rst#L8)) — характерный пример того, что Telethon ломает API минорными релизами.

**Скрытый риск (главный)**: проект импортирует **внутренние** имена Telethon:

| Импорт | Файл | Риск при апгрейде |
|---|---|---|
| `telethon.helpers._FileStream` | [upload_client.py:259](../telegram_upload/client/telegram_upload_client.py#L259) | Может быть переименован/удалён в любом релизе. |
| `telethon.helpers._maybe_await` | [upload_client.py:297, :388](../telegram_upload/client/telegram_upload_client.py#L297) | Аналогично. |
| `telethon.client.downloads.MIN_CHUNK_SIZE` | [download_client.py:12](../telegram_upload/client/telegram_download_client.py#L12) | Внутренняя константа. |
| `telethon.crypto.AES.encrypt_ige`/`decrypt_ige` | [upload_client.py:9](../telegram_upload/client/telegram_upload_client.py#L9), [download_client.py:13](../telegram_upload/client/telegram_download_client.py#L13) | Подкаталог `crypto`. |
| `telethon.tl.functions.upload.SaveFilePartRequest`/`SaveBigFilePartRequest` | [upload_client.py:11, :326-329](../telegram_upload/client/telegram_upload_client.py#L11) | Сгенерированные TL-схемы; редко ломаются, но возможно. |
| `telethon.tl.TLRequest` | [upload_client.py:11](../telegram_upload/client/telegram_upload_client.py#L11) | Редко меняется. |
| `telethon.network.ConnectionTcpMTProxyRandomizedIntermediate` | [telegram_manager_client.py:12](../telegram_upload/client/telegram_manager_client.py#L12) | Используется только для MTProxy. |

Плюс **скопированные** методы `upload_file` и `_download_file` — фактически вилки внутренней реализации Telethon. При любом изменении upstream-логики (например, когда они начнут поддерживать chunk size > 512 KB или добавят новые request-типы) — поведение разойдётся молча.

**Telethon v2 (когда выйдет)** — почти наверняка потребует переписать оба этих метода целиком. Закладывайтесь.

## more-itertools 10/11: что сломается

Pin: `>=8.0.0,<10.0.0`. На PyPI: 11.0.2.

Используется только в одной строке: [telegram_download_client.py:100-101](../telegram_upload/client/telegram_download_client.py#L100-L101) — `grouper(iterable, PARALLEL_DOWNLOAD_BLOCKS)`. В **версии 10.2.0** API `grouper` приведён в соответствие с itertools docs (`grouper(iterable, n, *, incomplete='fill', fillvalue=None)`). Исходный вызов проекта совместим (`(iterable, n)`).

В **11.0.0** дропнули поддержку Python 3.9 (на момент проверки 2026-04 уже EOL). Если форк ориентируется на 3.10+, можно безопасно расширить pin до `<12.0.0`.

Дополнительный нюанс: проект импортирует `more_itertools.grouper` в `download_client.py`, но в `utils.py:17-23` определён **свой собственный** `grouper(n, iterable)` со старым порядком аргументов. Этот собственный `grouper` используется в `send_files_as_album` ([upload_client.py:51](../telegram_upload/client/telegram_upload_client.py#L51)). Имеет смысл оставить только один.

## CVE / security advisories

`pip-audit -r requirements.txt` (2026-04-27) → **No known vulnerabilities found**. На момент проверки в pinned-диапазонах CVE не зарегистрировано.

Это не означает «навсегда безопасно» — стоит включить `pip-audit` в CI.

## Совместимость с актуальными версиями Python

`setup.py:43` декларирует:
```python
PYTHON_VERSIONS = ['3.7-3.9', '3.10', '3.11']
```

Реальные runtime-проверки в коде:
- `if sys.version_info < (3, 8): cached_property = property` (3 места: [telegram_manager_client.py:35-38](../telegram_upload/client/telegram_manager_client.py#L35-L38), [download_files.py:8-11](../telegram_upload/download_files.py#L8-L11), [caption_formatter.py:27-30](../telegram_upload/caption_formatter.py#L27-L30)).
- `if sys.version_info < (3, 10): from telegram_upload._compat import anext` ([download_client.py:21-22](../telegram_upload/client/telegram_download_client.py#L21-L22)).
- `python_version < '3.6'` — `scandir` ([_compat.py:7-9](../telegram_upload/_compat.py#L7-L9)).

| Python | Совместимость | Что мешает |
|---|---|---|
| 3.7 | EOL (2023-06). Декларируется, но Python 3.7 не получает security-патчей. | — |
| 3.8 | EOL (2024-10). | — |
| 3.9 | EOL (2025-10). | — |
| 3.10 | Поддерживается, тесты в CI. | — |
| 3.11 | Поддерживается, тесты в CI. | — |
| 3.12 | **Не тестируется**, но скорее всего работает. Удалён `distutils` — проект уже использует `packaging.version` ([telegram_manager_client.py:24-28](../telegram_upload/client/telegram_manager_client.py#L24-L28)) с фолбэком. Удалён `imghdr` — на этот случай Telethon 1.31+ уже подготовлен. |
| 3.13 | **Не тестируется.** Удалён `cgi`, `pipes`, `crypt` — в этом коде не используются. Тесты `unittest` и moсks работают. Должно завестись, но нужна верификация. |
| 3.14 | Не тестируется. На текущей машине именно 3.14 — потенциальная проверочная среда. Никаких известных блокеров не видно, но запускать без проверки нельзя. |

Особо для **3.12+**: `asyncio.get_event_loop()` без активного event loop в [cli.py:61, :82](../telegram_upload/cli.py#L61) выдаёт `DeprecationWarning` на 3.12 и `RuntimeError` на 3.13+ при некоторых сценариях. Этот код находится внутри key-binding callback'а prompt_toolkit, обычно работающего внутри запущенного loop'а — но при изолированном запуске может выстрелить.

## Открытые вопросы

- Готовы ли отказаться от поддержки Python 3.7–3.9 (все уже EOL) для упрощения кода (удалить `cached_property` фолбэки, `asyncmock`, `_compat.anext`)?
- Хочется ли расширить pin `more-itertools` до `<12.0.0` или вообще выкинуть, оставив свой `grouper`?
- Стоит ли уже сейчас добавить `pip-audit` в CI как обязательный шаг?
- Закладываемся ли мы на выход Telethon v2 (требует частичной переписки) или замораживаемся на v1?
