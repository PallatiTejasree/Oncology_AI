# Database migrations

Alembic owns the PostgreSQL schema. FastAPI must not create or alter tables at
startup.

For an existing database that already contains these tables, adopt the
baseline once with `alembic stamp head`. For an empty database, use
`alembic upgrade head`.

After changing a SQLAlchemy model, create and review a migration with:

    alembic revision --autogenerate -m "describe the schema change"
    alembic upgrade head
