# Storyteller

Modern Django 5.2 boilerplate configured for JWT authentication, Swagger/OpenAPI documentation, Celery, RabbitMQ, PostgreSQL, and Arvan Object Storage.

## Getting started

1. Install Python 3.14.0 with `pyenv` and activate it inside the project directory:
   ```bash
   pyenv install 3.14.0
   pyenv local 3.14.0
   ```
2. Create the local virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements/local.txt
   ```
3. Copy the sample environment file and adjust the variables:
   ```bash
   cp .env.example .env
   ```
4. Run the initial database migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Docker workflow

Build and run the stack (web, Postgres, RabbitMQ) with:

```bash
docker compose up --build
```

The API will be served at `http://localhost:8000`, Swagger UI at `http://localhost:8000/api/docs/`, and RabbitMQ management UI at `http://localhost:15672` (guest/guest).

