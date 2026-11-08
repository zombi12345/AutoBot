# AutoBot — поиск авто с уведомлениями

Telegram-бот на aiogram: пользователь задаёт критерии — бот ищет на av.by / kufar / onliner.
Есть режим «долгого поиска»: воркер 24/7 проверяет новые объявления и шлёт ссылки.

## Структура

- `app/` — код бота (aiogram)
- `app/services/parsers/` — парсеры площадок
- `app/db/` — модели и репозитории
- `worker/` — фоновый воркер долгого поиска
- `.scripts/` — все деплой- и сервисные скрипты

## Запуск (dev)

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Copy-Item .env.example .env
    # заполнить .env
    python bot_prod.py

## Деплой (Render)

- Build: `pip install -r requirements.txt`
- Start: `python bot_prod.py`
- Проверка: `GET /version` → `git_commit` совпадает с `git rev-parse HEAD`