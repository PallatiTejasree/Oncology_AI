"""Add persistent user-defined analysis titles."""

from sqlalchemy import text

from app.db.database import engine


def main() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS custom_title VARCHAR(80)"
        ))
    print("Custom analysis title migration applied successfully.")


if __name__ == "__main__":
    main()
