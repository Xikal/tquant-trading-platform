SHELL := /bin/bash

.PHONY: frontend-build native-build native-sync backend-compile version-sync version-check qa ui-smoke prod-preflight runtime-snapshot public-up public-down docker-sqlite-up docker-sqlite-down docker-mysql-up docker-mysql-down

frontend-build:
	cd frontend && npm run build

native-build:
	cd frontend && npm run build:native

native-sync:
	cd frontend && npm run cap:sync

backend-compile:
	cd backend && .venv/bin/python -m compileall app

version-sync:
	./scripts/version_sync.py

version-check:
	./scripts/version_sync.py --check

qa:
	./scripts/qa_smoke.sh

ui-smoke:
	./scripts/ui_smoke.sh

prod-preflight:
	./scripts/prod_preflight.sh

runtime-snapshot:
	./scripts/runtime_snapshot.sh

public-up:
	./scripts/run_public_app.sh

public-down:
	./scripts/stop_public_app.sh

docker-sqlite-up:
	docker compose -f docker-compose.sqlite.yml up -d --build

docker-sqlite-down:
	docker compose -f docker-compose.sqlite.yml down

docker-mysql-up:
	docker compose -f docker-compose.mysql.yml up -d --build

docker-mysql-down:
	docker compose -f docker-compose.mysql.yml down
