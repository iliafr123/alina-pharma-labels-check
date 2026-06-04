# Alina Pharma Labels Check

Система автоматизированной проверки макетов этикеток БАД, спортивного питания и бакалейной продукции для ООО «АЛИНА ФАРМА».

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11 + FastAPI + Celery |
| Frontend | React 18 + Vite + Tailwind CSS |
| База данных | PostgreSQL 15 |
| Очередь | Redis 7 + Celery |
| Хранилище | Selectel Object Storage (S3) |
| AI / OCR | Yandex Vision, ABBYY, OpenAI, Gemini, Claude, Grok |

## Быстрый старт

**Требования:** Docker, Docker Compose

```bash
git clone https://github.com/iliafr123/alina-pharma-labels-check.git
cd alina-pharma-labels-check
cp .env.example .env
# Отредактировать .env — добавить API-ключи и S3-доступ
docker compose up --build
# В отдельном терминале:
docker compose exec backend python scripts/init_db.py
```

- **Frontend:** http://localhost:5173
- **API Swagger:** http://localhost:8000/docs
- **Celery Flower:** http://localhost:5555
- Логин: `admin@alina-pharma.ru` / `Admin123!`

## Пайплайн проверки

1. OCR — извлечение текста (Yandex Vision / ABBYY / LLM Vision)
2. Орфография — с отраслевым словарём (LLM)
3. Сверка с ПЭН — толерантное сравнение с эталоном (LLM)
4. Нормативный чек-лист — ТР ТС 022/2011, МР 2.3.1.0253-21 (LLM + Vision)
5. Отчёт — аннотированный PDF + экспорт Excel/Word

## Роли

| Роль | Возможности |
|------|-------------|
| `admin` | Все функции + пользователи + API-ключи + хранилище |
| `specialist` | Загрузка, проверки, результаты, журнал, справочники |

© 2026 ООО «АЛИНА ФАРМА»
