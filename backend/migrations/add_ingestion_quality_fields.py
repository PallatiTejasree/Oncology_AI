"""Store calibrated ingestion-quality scores and their component reasons."""

from sqlalchemy import text

from app.db.database import engine


STATEMENTS = (
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION",
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS quality_reasons_json TEXT",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION",
    "ALTER TABLE medical_images ADD COLUMN IF NOT EXISTS quality_reasons_json TEXT",
)


def main() -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))
    print("Ingestion-quality migration applied successfully.")


if __name__ == "__main__":
    main()
