.PHONY: db-up migrate test-unit test-int test-reg test lint verify
db-up:; ./scripts/dev-db.sh
migrate: db-up; cd backend && ENVIRONMENT=$${ENVIRONMENT:-dev} alembic upgrade head
test-unit:; cd backend && python3 -m pytest tests/unit -q
test-int: migrate; cd backend && python3 -m pytest tests/integration -q
test-reg: migrate; cd backend && python3 -m pytest tests/regression -q
test: migrate; cd backend && python3 -m pytest -q
lint:; cd backend && ruff check src tests && PYTHONPATH=src lint-imports
verify: lint test
