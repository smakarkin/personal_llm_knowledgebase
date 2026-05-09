# GUI V2 (Workbench) для управления Knowledge Base

Это первый каркас desktop-приложения на **PySide6** поверх существующих Python-скриптов.

## Что добавлено в V2 Workbench layer
- Экран **Settings** с сохранением рабочих настроек (пути, startup page, режимы).
- Локальная persistence в `gui_app_data/workbench_state.json`:
  - последний экран,
  - последние trace-запросы,
  - последние rebuild-сценарии,
  - pinned/recent артефакты и действия.
- Dashboard теперь показывает блок Workbench: последние запуски, pinned actions/files, недавние артефакты.
- Для Rebuild добавлен единый progress/log widget (статус + live log + copy/open лог-файл).
- Архитектурно вынесен `WorkbenchStateStore` в отдельный сервис.

## Что уже есть (MVP + V2)
- Единый стиль кнопок и статусных элементов.
- Dashboard с заметным блоком **«Рекомендуемый следующий шаг»** и диагностикой.
- Pipeline Map с цветовой индикацией статусов этапов (`OK`, `Требует внимания`, `Устарело`, `Не запускалось`).
- InBox с понятной маркировкой заметок «Готово к переносу» (ручной перенос в Obsidian).
- Rebuild с подтверждением перед запуском сценария.
- Trace и Health с удобной preview-area и логом.
- Нижний статус-бар с последним действием.
- Меню «Файл → Открыть vault root».
- Более безопасная обработка отсутствующих optional-скриптов.

## Установка
Из корня репозитория:

```bash
python -m venv .venv
source .venv/bin/activate  # для Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Запуск
Из корня репозитория:

```bash
python -m gui_app.main
```

## Структура экранов
- **Dashboard** — текущее состояние слоёв, таймстемпы, рекомендации следующего шага.
- **Pipeline Map** — карта этапов ingest→classify→collections→concepts→index с подсветкой.
- **InBox** — список заметок входящих и готовность к ручному переносу.
- **Rebuild** — запуск готовых сценариев (primary/candidate/full) с логом.
- **Trace** — semantic trace-поиск и предпросмотр отчётов.
- **Health** — запуск lint и обзор категорий проблем + полный текст отчёта.
- **Sources / Logs** — заглушки на уровне MVP.
- **Settings** — настройки workbench и запуск по preferred page.

## Конфиг и локальное состояние
По умолчанию приложение читает `gui_app/config.local.json`, а если его нет — `gui_app/config.json`.

Поля:
- `vault_path` — путь к Obsidian-хранилищу (где лежат InBox/Zettelkasten/LLM-слои).
- `scripts_path` — путь к папке с backend-скриптами.
- `inbox_folder` — имя папки входящих в vault (например, `__Inbox`).

Пример:
```json
{
  "vault_path": "../my_obsidian_vault",
  "scripts_path": "..",
  "inbox_folder": "__Inbox"
}
```

Рекомендуется создать `gui_app/config.local.json` со своими путями и не коммитить его.

Локальное состояние GUI хранится в:
- `gui_app_data/workbench_state.json`

## Known limitations
- Пока нет cloud sync/аккаунтов и совместного состояния между устройствами.
- Progress/log widget полноценно подключён в Rebuild; для Trace/Health используется текущий UI-лог и будет унифицирован в следующем шаге.
- История/pinned-объекты сохраняются локально JSON-файлом без БД.
