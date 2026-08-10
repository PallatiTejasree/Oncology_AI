import os
import time
import requests
from cancer_types import CANCER_TYPES

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search_articles(query, page_size=10):

    search_query = f'({query}) AND OPEN_ACCESS:y AND SRC:PMC'

    params = {
        "query": search_query,
        "format": "json",
        "pageSize": page_size
    }

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()

    return response.json()


# ==========================================================
# DOWNLOAD PDF
# ==========================================================

def download_pdf(pmcid, cancer_type):

    pdf_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf"

    folder = os.path.join(
        "downloads",
        "pdfs",
        cancer_type.replace(" ", "_")
    )

    os.makedirs(folder, exist_ok=True)

    output_file = os.path.join(folder, f"{pmcid}.pdf")

    if os.path.exists(output_file):
        print(f"PDF Already Exists : {pmcid}")
        return

    try:

        response = requests.get(pdf_url, stream=True, timeout=30)

        if response.status_code != 200:
            print(f"PDF Failed : {pmcid}")
            return

        with open(output_file, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        print(f"PDF Downloaded : {pmcid}")

    except Exception as e:
        print(e)


# ==========================================================
# DOWNLOAD XML
# ==========================================================

def download_xml(pmcid, cancer_type):

    xml_url = (
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/"
        f"{pmcid}/fullTextXML"
    )

    folder = os.path.join(
        "downloads",
        "xml",
        cancer_type.replace(" ", "_")
    )

    os.makedirs(folder, exist_ok=True)

    output_file = os.path.join(folder, f"{pmcid}.xml")

    if os.path.exists(output_file):
        print(f"XML Already Exists : {pmcid}")
        return

    try:

        response = requests.get(xml_url, timeout=30)

        if response.status_code != 200:
            print(f"XML Failed : {pmcid}")
            return

        with open(output_file, "wb") as f:
            f.write(response.content)

        print(f"XML Downloaded : {pmcid}")

    except Exception as e:
        print(e)


# ==========================================================
# MAIN
# ==========================================================

def main():

    DOWNLOAD_PER_CANCER = 5

    for cancer in CANCER_TYPES:

        print("\n" + "=" * 90)
        print(cancer.upper())
        print("=" * 90)

        data = search_articles(
            cancer,
            page_size=DOWNLOAD_PER_CANCER
        )

        articles = data.get("resultList", {}).get("result", [])

        print(f"Found {len(articles)} articles")

        downloaded = 0

        for article in articles:

            pmcid = article.get("pmcid")

            if not pmcid:
                continue

            print(f"\nTitle : {article.get('title')}")
            print(f"PMCID : {pmcid}")

            # -----------------------------
            # SAME PMCID
            # PDF + XML
            # -----------------------------

            download_pdf(pmcid, cancer)

            download_xml(pmcid, cancer)

            downloaded += 1

            time.sleep(1)

        print(f"\nDownloaded {downloaded} article(s) for {cancer}")

    print("\n")
    print("=" * 90)
    print("ALL DOWNLOADS FINISHED")
    print("=" * 90)


if __name__ == "__main__":
    main()