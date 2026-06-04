# Деплой на Railway + Netlify

Развёртывание приложения проверки этикеток в облаке (без геоблокировки AI-провайдеров).
Архитектура: **Railway** = backend (FastAPI) + worker (Celery) + PostgreSQL + Redis. **Netlify** = frontend (React SPA).

---

## Шаг 0. Сгенерируйте два секрета (один раз)

Выполните локально и сохраните — понадобятся ниже (одинаковые для web и worker!):

```bash
# SECRET_KEY (JWT)
openssl rand -hex 32

# ENCRYPTION_KEY (шифрование API-ключей, формат Fernet)
openssl rand -base64 32 | tr '+/' '-_'
```

---

## Шаг 1. Создать проект на Railway

1. https://railway.app → **New Project** → **Deploy from GitHub repo** → выберите `iliafr123/alina-pharma-labels-check`.
2. Railway создаст первый сервис. Откройте его **Settings**:
   - **Root Directory**: `backend`
   - Build — Dockerfile подхватится автоматически (`backend/railway.json`).
   - Переименуйте сервис в `backend`.

## Шаг 2. Добавить базы

В проекте → **New** → **Database**:
- **Add PostgreSQL**
- **Add Redis**

Railway создаст переменные `Postgres.DATABASE_URL` и `Redis.REDIS_URL`.

## Шаг 3. Переменные окружения сервиса `backend`

Settings → **Variables**:

| Переменная | Значение |
|-----------|----------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `SECRET_KEY` | (из шага 0) |
| `ENCRYPTION_KEY` | (из шага 0) |
| `INITIAL_ADMIN_PASSWORD` | `Admin123!` |
| `CELERY_EAGER` | `false` |
| `CORS_ORIGINS` | (заполните после шага 6 — URL Netlify) |
| `S3_ENDPOINT_URL` | `https://s3.selectel.ru` (опц.) |
| `S3_BUCKET` / `S3_REGION` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | (опц., можно позже в админке) |

При старте контейнер сам создаст таблицы и засеет данные (admin, словарь, чек-лист) — см. CMD в `backend/Dockerfile`.

## Шаг 4. Сервис `worker` (Celery)

В проекте → **New** → **GitHub Repo** → тот же репозиторий ещё раз. Это второй сервис:
- **Root Directory**: `backend`
- **Settings → Deploy → Custom Start Command**:
  ```
  celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
  ```
- **Variables**: те же `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`, `S3_*`.
  ⚠️ `SECRET_KEY` и `ENCRYPTION_KEY` **должны совпадать** с сервисом `backend` (worker расшифровывает API-ключи тем же ключом).

## Шаг 5. Публичный домен backend

Сервис `backend` → Settings → **Networking** → **Generate Domain**.
Получите URL вида `https://backend-xxxx.up.railway.app`. Проверьте: открыть `…/docs` и `…/health`.

## Шаг 6. Frontend на Netlify

1. https://app.netlify.com → **Add new site** → **Import from GitHub** → тот же репозиторий.
2. Build settings:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/dist`
3. **Environment variables**:
   - `VITE_API_URL` = `https://backend-xxxx.up.railway.app/api/v1` (URL из шага 5)
4. Deploy. Получите URL вида `https://<site>.netlify.app`.

## Шаг 7. Связать CORS

Вернитесь в Railway → сервис `backend` → Variables →
`CORS_ORIGINS` = `https://<site>.netlify.app`
(сервис перезапустится).

## Шаг 8. Вход и ключи

1. Откройте Netlify-URL → войдите: `admin@alina-pharma.ru` / `Admin123!`
2. **Администрирование → Провайдеры AI/OCR** → вставьте ключи (Claude/OpenAI/Gemini/Grok), **Сохранить**, затем **Проверить подключение** — теперь пройдёт ✅ (Railway не в РФ, геоблока нет).
3. **Конфигурация пайплайна** → выберите режим/провайдеров → Сохранить.

---

## Примечания
- **OCR:** провайдеры с vision (Claude/GPT-4o/Gemini) делают OCR сами в «Едином LLM-режиме». Yandex Vision из-за рубежа тоже доступен.
- **Selectel-сервер:** после успешного запуска на Railway копию на `strategy-backend` (systemd `alina-backend`/`alina-worker`, nginx :8080) можно отключить — она геоблокирована и не нужна.
- **Данные:** на этикетках нет ПДн, поэтому размещение в облаке за пределами РФ допустимо.
