from pathlib import Path
import pandas as pd
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent

csv_path = BASE_DIR / "processed_dataset" / "manual_review.csv"
images_root = BASE_DIR / "processed_dataset" / "medical_images"

df = pd.read_csv(csv_path)

# Ensure text columns are strings
df["review_status"] = df["review_status"].fillna("pending").astype(str)
df["comment"] = df["comment"].fillna("").astype(str)

for index, row in df.iterrows():

    image_path = images_root / row["image_path"]

    if not image_path.exists():
        print(f"Missing: {image_path}")
        continue

    print(f"\nImage {index+1}/{len(df)}")
    print(image_path)

    img = Image.open(image_path)
    img.show()

    status = input("Approve (a) / Reject (r) / Skip (s): ").strip().lower()

    if status == "a":
        df.loc[index, "review_status"] = "approved"
    elif status == "r":
        df.loc[index, "review_status"] = "rejected"
    else:
        df.loc[index, "review_status"] = "pending"

    comment = input("Comment: ")

    df.loc[index, "comment"] = comment

    df.to_csv(csv_path, index=False)

print("\nReview completed!")