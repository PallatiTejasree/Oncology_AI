from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

images_root = BASE_DIR / "processed_dataset" / "medical_images"

# Find all image files recursively
image_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

image_files = []

for file in images_root.rglob("*"):
    if file.is_file() and file.suffix.lower() in image_extensions:
        image_files.append(file)

image_files = sorted(image_files)

print(f"Total images found: {len(image_files)}")

sample = image_files[:50]

records = []

for img in sample:
    records.append({
        "pmcid": img.parent.name,
        "image_name": img.name,
        "image_path": str(img.relative_to(images_root)),
        "review_status": "pending",
        "comment": ""
    })

df = pd.DataFrame(records)

output = BASE_DIR / "processed_dataset" / "manual_review.csv"
df.to_csv(output, index=False)

print(f"\nCreated: {output}")
print(f"Images to review: {len(df)}")