PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.PHONY: install install-dev migrate runserver format lint test celery

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/production.txt

install-dev:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/local.txt

migrate:
	$(PYTHON) manage.py migrate

runserver:
	$(PYTHON) manage.py runserver 0.0.0.0:8000

celery:
	$(PYTHON) -m celery -A config worker -l info

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest
