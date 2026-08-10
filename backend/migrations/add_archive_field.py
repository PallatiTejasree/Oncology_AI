"""Add soft-archive support to analysis sessions."""

from sqlalchemy import text
from app.db.database import engine


def main() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE upload_sessions ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_upload_sessions_user_archived ON upload_sessions (user_id, archived_at)"))
    print("Archive migration applied successfully.")


if __name__ == "__main__":
    main()
