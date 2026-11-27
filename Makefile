.PHONY: install-backend install-frontend dev-backend dev-frontend test lint

install-backend:
	cd backend && uv venv --allow-existing && uv pip install -e ".[dev]"

install-backend-adapters:
	cd backend && uv pip install -e ".[adapters,dev]"

install-frontend:
	cd frontend && npm install

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

test:
	cd backend && .venv/bin/pytest -v

lint:
	cd backend && .venv/bin/ruff check app tests
	cd frontend && npm run build
