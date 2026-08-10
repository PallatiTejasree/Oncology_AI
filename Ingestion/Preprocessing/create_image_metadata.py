"""Create the canonical image manifest from parsed PMC article metadata."""

import argparse
import json

from Ingestion.Preprocessing.medical_image_filter import process_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Build metadata without copying accepted images into processed_dataset.",
    )
    args = parser.parse_args()
    print(json.dumps(process_dataset(copy_files=not args.no_copy), indent=2))


if __name__ == "__main__":
    main()
