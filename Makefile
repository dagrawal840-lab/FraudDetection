.PHONY: install install-dev run train seed test lint format clean

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

train:
	python ml/train.py

seed:
	python scripts/seed_data.py

test:
	pytest tests/ -v

lint:
	ruff check app/ ml/ tests/
	black --check app/ ml/ tests/

format:
	ruff check --fix app/ ml/ tests/
	black app/ ml/ tests/

paysim-train:
	python ml/train_paysim.py --csv data/paysim.csv --version 3 --evaluate

paysim-ingest:
	python scripts/ingest_paysim.py --csv data/paysim.csv --sample 10000

paysim-ingest-all:
	python scripts/ingest_paysim.py --csv data/paysim.csv

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

setup: install train seed
	@echo "✓ Setup complete. Run 'make run' to start the API."

setup-paysim: install paysim-train seed
	@echo "✓ PaySim setup complete. Run 'make run' then 'make paysim-ingest'."
