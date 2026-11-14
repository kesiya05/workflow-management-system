# Workflow Management System

Request and approval workflow API with roles, status transitions and an audit trail.

## What it does

- Token auth with roles
- Request lifecycle with allowed transitions only
- Requirements, user stories, diagrams and test cases in `docs/`

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for the interactive API docs. With Docker: `docker compose up` (uses PostgreSQL). The default database is a local SQLite file, so it works with no setup.

## Tests

```bash
ruff check . && pytest
```

## Notes

Intended as a clean reference design, not a hosted product.

MIT licensed. Built by Kesiya Ann Sony.
