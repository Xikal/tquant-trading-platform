SHELL := /bin/bash

.PHONY: frontend-build native-build native-sync backend-compile version-sync version-check qa ui-smoke warning-budget full-regression full-regression-release full-regression-cloud prod-preflight runtime-snapshot rust-bench go-rust-acceptance deploy-cloud deploy-cloud-web deploy-cloud-go deploy-cloud-full deploy-cloud-fast deploy-cloud-verify public-up public-down docker-sqlite-up docker-sqlite-down docker-mysql-up docker-mysql-down

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

warning-budget:
	python scripts/warning_budget.py backend/tests

full-regression:
	python scripts/full_regression_runner.py --profile full

full-regression-release:
	python scripts/full_regression_runner.py --profile release

full-regression-cloud:
	python scripts/full_regression_runner.py --profile release --only cloud_verify --cloud-verify

prod-preflight:
	./scripts/prod_preflight.sh

runtime-snapshot:
	./scripts/runtime_snapshot.sh

rust-bench:
	cd rust/tquant-rs && cargo bench --features extension-module --bench finance

go-rust-acceptance:
	python scripts/verify_go_rust_performance_acceptance.py

deploy-cloud:
	./scripts/one_click_cloud_deploy.sh

deploy-cloud-web:
	cd frontend && npm run build
	./scripts/one_click_cloud_deploy.sh --scope frontend-hot --frontend-hot-required

deploy-cloud-go:
	./scripts/one_click_cloud_deploy.sh --scope go

deploy-cloud-full:
	./scripts/one_click_cloud_deploy.sh --scope all --full

deploy-cloud-fast:
	./scripts/one_click_cloud_deploy.sh --fast

deploy-cloud-verify:
	./scripts/one_click_cloud_deploy.sh --verify-only

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
