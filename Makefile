.PHONY: dev init logs test shell-backend

dev:
	docker compose up --build

init:
	docker compose exec backend python scripts/init_db.py

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest tests/ -v

shell-backend:
	docker compose exec backend bash
