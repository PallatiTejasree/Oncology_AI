"""Add the hashed recovery-PIN field used by internship account recovery."""

from sqlalchemy import text

from app.db.database import engine


def main() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_pin_hash VARCHAR(64)"
        ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_recovery_pin_hash "
            "ON users (recovery_pin_hash) WHERE recovery_pin_hash IS NOT NULL"
        ))
    print("Recovery PIN migration applied.")


if __name__ == "__main__":
    main()
