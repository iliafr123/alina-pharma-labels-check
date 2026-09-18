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

## Тесты и деплой

Регрессионный набор обязан пройти **перед каждым деплоем в прод**:

```bash
bash scripts/predeploy.sh      # или make predeploy
```

- backend — `pytest` (SQLite, без Redis/S3/ключей провайдеров);
- frontend — `vitest` + `tsc -b && vite build`.

Ненулевой код возврата означает «не деплоить». То же самое выполняется в GitHub
Actions на каждый push в `master` и каждый pull request
(`.github/workflows/ci.yml`). Railway разворачивает `master` автоматически.

## Контроль ошибок и качества

- **Ошибки.** Каждый сбой приводится к типизированной ошибке с кодом, причиной
  по-русски и подсказкой; видна пользователю на экране проверки и администратору
  в **Администрирование → Ошибки**.
- **Качество макета.** Перед запуском проверки макет оценивается на пригодность
  для OCR (разрешение, резкость, контраст); при недостаточном качестве проверка
  не запускается, а пользователю объясняется, что прислать вместо этого.
- **Балансы.** **Администрирование → Балансы** — остаток у провайдеров в рублях
  по курсу ЦБ (там, где провайдер вообще отдаёт баланс по API).

Подробности, коды ошибок и калибровка порогов качества:
[docs/ERRORS_AND_QUALITY.md](docs/ERRORS_AND_QUALITY.md).

## Роли

| Роль | Возможности |
|------|-------------|
| `admin` | Все функции + пользователи + API-ключи + хранилище |
| `specialist` | Загрузка, проверки, результаты, журнал, справочники |

© 2026 ООО «АЛИНА ФАРМА»
