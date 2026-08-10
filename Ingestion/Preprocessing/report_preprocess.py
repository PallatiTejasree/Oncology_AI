import os
import pandas as pd

# =====================================================
# Paths
# =====================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPORTS_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "reports",
    "TCGA_Reports.csv",
)

CANCER_TYPE_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "reports",
    "tcga_metadata",
    "tcga_patient_to_cancer_type.csv",
)

OUTPUT_DIR = os.path.join(BASE_DIR, "datasets", "processed")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    "clean_reports.csv",
)

# =====================================================
# Load Datasets
# =====================================================

print("=" * 60)
print("Loading TCGA Report Dataset...")
print("=" * 60)

reports_df = pd.read_csv(REPORTS_PATH)

print(f"Total Reports : {len(reports_df):,}")
print(f"Columns       : {list(reports_df.columns)}")

print("\n")

print("=" * 60)
print("Loading Cancer Type Mapping...")
print("=" * 60)

cancer_df = pd.read_csv(CANCER_TYPE_PATH)

print(f"Total Patients : {len(cancer_df):,}")
print(f"Columns        : {list(cancer_df.columns)}")

print("\n")

print("=" * 60)
print("Preview - Reports")
print("=" * 60)

print(reports_df.head())

print("\n")

print("=" * 60)
print("Preview - Cancer Types")
print("=" * 60)

print(cancer_df.head())
# =====================================================
# Check Missing Values
# =====================================================

print("\n" + "=" * 60)
print("Checking Missing Values")
print("=" * 60)

print(reports_df.isnull().sum())
print()

# =====================================================
# Remove Empty Reports
# =====================================================

reports_df = reports_df.dropna(subset=["text"])

reports_df["text"] = reports_df["text"].astype(str)

reports_df = reports_df[
    reports_df["text"].str.strip() != ""
].reset_index(drop=True)

print(f"Reports after cleaning : {len(reports_df):,}")

# =====================================================
# Basic Text Cleaning
# =====================================================

reports_df["text"] = (
    reports_df["text"]
    .str.replace("\n", " ", regex=False)
    .str.replace("\r", " ", regex=False)
    .str.replace("\t", " ", regex=False)
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)

print("\nSample Clean Report\n")
print(reports_df.loc[0, "text"][:700])

# =====================================================
# Extract Patient ID
# =====================================================

reports_df["patient_id"] = (
    reports_df["patient_filename"]
        .str.split(".", regex=False)
        .str[0]
)

print("\nPatient IDs Extracted")

print(reports_df[["patient_filename", "patient_id"]].head())
# =====================================================
# Merge Reports with Cancer Type Mapping
# =====================================================

print("\n" + "=" * 60)
print("Merging Cancer Types")
print("=" * 60)

merged_df = reports_df.merge(
    cancer_df,
    on="patient_id",
    how="left"
)

matched = merged_df["cancer_type"].notna().sum()

print(f"Matched Reports : {matched:,}")
print(f"Unmatched Reports : {len(merged_df) - matched:,}")

# =====================================================
# Assign Report IDs
# =====================================================

merged_df.insert(
    0,
    "report_id",
    range(1, len(merged_df) + 1)
)

# =====================================================
# Select Required Columns
# =====================================================

clean_reports = merged_df[
    [
        "report_id",
        "patient_id",
        "cancer_type",
        "text"
    ]
].rename(
    columns={
        "text": "report"
    }
)

# =====================================================
# Save Clean Dataset
# =====================================================

clean_reports.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\n" + "=" * 60)
print("Clean Report Dataset Saved")
print("=" * 60)

print(f"Location : {OUTPUT_PATH}")

print("\nDataset Shape")
print(clean_reports.shape)

print("\nPreview")

print(clean_reports.head())

print("\nCancer Type Distribution")

print(
    clean_reports["cancer_type"]
    .value_counts()
    .head(15)
)