from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

metadata_path = BASE_DIR / "processed_dataset" / "image_metadata.csv"

df = pd.read_csv(metadata_path)

# Add review_status only if it doesn't exist
if "review_status" not in df.columns:
    df["review_status"] = "pending"
    print("Added review_status column.")
else:
    print("review_status column already exists.")

df.to_csv(metadata_path, index=False)

print(f"Saved: {metadata_path}")
print(f"Total records: {len(df)}")