# AGENTS.md

## Knowledge layer журнал
- Основной bat-пайплайн `commands/rebuild_zettelkasten_all.bat` дописывает append-only журнал операций в markdown-файл `13_llm_indexes/log.md` (внутри configured VAULT).
- Формат записи: дата/время, каталог, режим, шаг, статус (`success` или `error`).
- Для записи используется скрипт `append_log.py`.
