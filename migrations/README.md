# Database Migrations Framework

This directory contains database schema migration scripts powered by **Alembic**.

## Commands

- Generate migration:
  ```bash
  alembic revision --autogenerate -m "description_of_changes"
  ```

- Apply migrations:
  ```bash
  alembic upgrade head
  ```

- Rollback one migration:
  ```bash
  alembic downgrade -1
  ```

