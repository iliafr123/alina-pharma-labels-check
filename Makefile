.PHONY: dev init logs test test-backend test-frontend predeploy shell-backend

dev:
	docker compose up --build

init:
	docker compose exec backend python scripts/init_db.py

logs:
	docker compose logs -f

# Full regression gate - must pass before deploying to production.
predeploy:
	bash scripts/predeploy.sh

test: predeploy

test-backend:
	cd backend && python -m pytest

test-frontend:
	cd frontend && npm test

shell-backend:
	docker compose exec backend bash
