import argparse
import os
import csv
import requests
import tarfile
from pathlib import Path

try:
    from .cancer_types import CANCER_TYPES
except ImportError:  # Support direct script execution.
    from cancer_types import CANCER_TYPES


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OA_FILE_LIST = Path(
    os.environ.get("PMC_OA_FILE_LIST", BASE_DIR / "oa_file_list.csv")
).expanduser().resolve()

DOWNLOAD_ROOT = BASE_DIR / "downloads"

ARTICLES_PER_CANCER = 5

EUROPE_PMC_SEARCH = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ============================================================
# LOAD OA PACKAGE INDEX
# ============================================================

def load_package_index(oa_file_list=OA_FILE_LIST):

    print("=" * 80)
    print("Loading OA Package Index...")
    print("=" * 80)

    package_index = {}

    oa_file_list = Path(oa_file_list)
    if not oa_file_list.exists():
        raise FileNotFoundError(
            f"PMC OA package index not found: {oa_file_list}. "
            "Pass --oa-file-list or set PMC_OA_FILE_LIST."
        )

    with open(
        oa_file_list,
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for row in reader:

            if len(row) < 3:
                continue

            package_path = row[0].strip()
            pmcid = row[2].strip()

            package_index[pmcid] = package_path

    print(f"Loaded {len(package_index):,} package entries.\n")

    return package_index


# ============================================================
# SEARCH EUROPE PMC
# ============================================================

def search_articles(cancer):

    query = f'({cancer}) AND OPEN_ACCESS:y AND SRC:PMC'

    params = {
        "query": query,
        "format": "json",
        "pageSize": 30
    }

    response = requests.get(
        EUROPE_PMC_SEARCH,
        params=params,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    return data.get("resultList", {}).get("result", [])


# ============================================================
# CREATE CANCER FOLDER
# ============================================================

def create_cancer_folder(cancer, download_root=DOWNLOAD_ROOT):

    folder = os.path.join(
        download_root,
        cancer.replace(" ", "_")
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    return folder


# ============================================================
# GET PACKAGE URL
# ============================================================

def get_package_url(
    pmcid,
    package_index
):

    if pmcid not in package_index:
        return None

    package_path = package_index[pmcid]

    return (
        "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/"
        + package_path
    )
# ============================================================
# DOWNLOAD PACKAGE
# ============================================================

def download_package(package_url, output_file):

    if os.path.exists(output_file):
        print("Already Downloaded")
        return True

    try:

        response = requests.get(
            package_url,
            headers=HEADERS,
            stream=True,
            timeout=120
        )

        if response.status_code != 200:
            print("Download Failed")
            return False

        with open(output_file, "wb") as f:

            for chunk in response.iter_content(1024 * 1024):

                if chunk:
                    f.write(chunk)

        return True

    except Exception as e:

        print(e)

        return False


# ============================================================
# EXTRACT PACKAGE
# ============================================================

def extract_package(package_file, extract_folder):

    try:

        destination = Path(extract_folder).resolve()
        destination.mkdir(parents=True, exist_ok=True)

        with tarfile.open(package_file, "r:gz") as tar:
            for member in tar.getmembers():
                target = (destination / member.name).resolve()
                if destination != target and destination not in target.parents:
                    raise ValueError(f"Unsafe archive member: {member.name}")
                if member.issym() or member.islnk():
                    raise ValueError(f"Archive links are not allowed: {member.name}")
            tar.extractall(destination)

        return True

    except Exception as e:

        print(e)

        return False


# ============================================================
# MAIN
# ============================================================

def main(oa_file_list=OA_FILE_LIST):

    package_index = load_package_index(oa_file_list)

    print("=" * 80)
    print("Starting Downloads...")
    print("=" * 80)

    for cancer in CANCER_TYPES:

        print("\n")
        print("=" * 80)
        print(cancer.upper())
        print("=" * 80)

        cancer_folder = create_cancer_folder(cancer)

        articles = search_articles(cancer)

        downloaded = 0

        for article in articles:

            if downloaded >= ARTICLES_PER_CANCER:
                break

            pmcid = article.get("pmcid")

            if not pmcid:
                continue

            package_url = get_package_url(
                pmcid,
                package_index
            )

            if package_url is None:
                continue

            article_folder = os.path.join(
                cancer_folder,
                pmcid
            )

            os.makedirs(
                article_folder,
                exist_ok=True
            )

            tar_file = os.path.join(
                article_folder,
                f"{pmcid}.tar.gz"
            )

            print("\n----------------------------------------")
            print("Cancer :", cancer)
            print("PMCID  :", pmcid)
            print("Title  :", article.get("title"))

            success = download_package(
                package_url,
                tar_file
            )

            if not success:
                continue
            success = extract_package(
                tar_file,
                article_folder
                )
            if not success:
                continue
            os.remove(tar_file)
            result = verify_article(
                article_folder
                )
            # Require XML to count as a successful download
            
            if len(result["xml"]) == 0:
                print("Skipping package because XML is missing.")
                continue
            downloaded += 1
            print(f"Completed {downloaded}/{ARTICLES_PER_CANCER}")

        print(f"\nFinished {cancer}")

    print("\n")
    print("=" * 80)
    print("ALL DOWNLOADS COMPLETE")
    print("=" * 80)

# ============================================================
# VERIFY DOWNLOADED ARTICLE
# ============================================================

def verify_article(article_folder):

    xml_files = []
    pdf_files = []
    image_files = []

    image_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
        ".gif",
        ".bmp",
        ".webp"
    )

    for root, dirs, files in os.walk(article_folder):

        for file in files:

            lower = file.lower()

            if lower.endswith(".nxml") or lower.endswith(".xml"):
                xml_files.append(
                    os.path.join(root, file)
                )

            elif lower.endswith(".pdf"):
                pdf_files.append(
                    os.path.join(root, file)
                )

            elif lower.endswith(image_extensions):
                image_files.append(
                    os.path.join(root, file)
                )

    print("\nVerification")
    print("------------------------------")
    print(f"XML Files    : {len(xml_files)}")
    print(f"PDF Files    : {len(pdf_files)}")
    print(f"Images       : {len(image_files)}")

    if xml_files:
        print("✓ XML Found")
    else:
        print("✗ XML Missing")

    if pdf_files:
        print("✓ PDF Found")
    else:
        print("⚠ PDF Not Included")

    if image_files:
        print("✓ Figures Found")
    else:
        print("⚠ No Figures")

    return {
        "xml": xml_files,
        "pdf": pdf_files,
        "images": image_files
    }

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(description="Download open-access PMC oncology packages.")
    argument_parser.add_argument(
        "--oa-file-list",
        default=OA_FILE_LIST,
        type=Path,
        help="Path to the NCBI oa_file_list.csv index.",
    )
    arguments = argument_parser.parse_args()
    main(arguments.oa_file_list)
