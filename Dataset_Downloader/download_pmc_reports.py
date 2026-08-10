import os
import time
import requests
from bs4 import BeautifulSoup

from cancer_types import CANCER_TYPES

# ==========================================================
# CONFIGURATION
# ==========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

DOWNLOAD_PER_CANCER = 5


# ==========================================================
# SEARCH EUROPE PMC
# ==========================================================

def search_articles(cancer_name):

    query = f"({cancer_name}) AND OPEN_ACCESS:y AND SRC:PMC"

    params = {
        "query": query,
        "format": "json",
        "pageSize": DOWNLOAD_PER_CANCER
    }

    response = requests.get(
        SEARCH_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    return data.get("resultList", {}).get("result", [])


# ==========================================================
# FIND REAL PDF LINK
# ==========================================================

def get_pdf_url(pmcid):

    article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"

    response = requests.get(
        article_url,
        headers=HEADERS,
        timeout=30
    )

    if response.status_code != 200:
        return None

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    pdf_url = None

    for tag in soup.find_all("a", href=True):

        href = tag["href"]

        if "/pdf/" in href and href.endswith(".pdf"):

            if href.startswith("/"):
                pdf_url = "https://pmc.ncbi.nlm.nih.gov" + href
            else:
                pdf_url = href

            break

    return pdf_url


# ==========================================================
# DOWNLOAD PDF
# ==========================================================

def download_pdf(pdf_url, pmcid, cancer):

    folder = os.path.join(
        "downloads",
        "pdf_reports",
        cancer.replace(" ", "_")
    )

    os.makedirs(folder, exist_ok=True)

    output_file = os.path.join(
        folder,
        f"{pmcid}.pdf"
    )

    if os.path.exists(output_file):
        print(f"✓ PDF Already Exists : {pmcid}")
        return

    response = requests.get(
        pdf_url,
        headers=HEADERS,
        stream=True,
        timeout=60
    )

    if response.status_code != 200:
        print("❌ PDF Download Failed")
        return

    if "application/pdf" not in response.headers.get(
        "Content-Type",
        ""
    ):
        print("❌ Invalid PDF")
        return

    with open(output_file, "wb") as f:

        for chunk in response.iter_content(8192):

            if chunk:
                f.write(chunk)

    print("✓ PDF Saved")
    # ==========================================================
# DOWNLOAD XML
# ==========================================================

def download_xml(pmcid, cancer):

    folder = os.path.join(
        "downloads",
        "xml_reports",
        cancer.replace(" ", "_")
    )

    os.makedirs(folder, exist_ok=True)

    output_file = os.path.join(
        folder,
        f"{pmcid}.xml"
    )

    if os.path.exists(output_file):
        print(f"✓ XML Already Exists : {pmcid}")
        return

    xml_url = (
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/"
        f"{pmcid}/fullTextXML"
    )

    response = requests.get(
        xml_url,
        headers=HEADERS,
        timeout=60
    )

    if response.status_code != 200:
        print("❌ XML Download Failed")
        return

    with open(output_file, "wb") as f:
        f.write(response.content)

    print("✓ XML Saved")


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("\n")
    print("=" * 90)
    print("EUROPE PMC DOWNLOADER")
    print("=" * 90)

    for cancer in CANCER_TYPES:

        print("\n")
        print("=" * 90)
        print(cancer.upper())
        print("=" * 90)

        try:
            articles = search_articles(cancer)

        except Exception as e:
            print(e)
            continue

        print(f"Found {len(articles)} Articles\n")

        downloaded = 0

        for article in articles:

            pmcid = article.get("pmcid")

            if not pmcid:
                continue

            print("-" * 80)
            print("Title :", article.get("title"))
            print("PMCID :", pmcid)

            pdf_url = get_pdf_url(pmcid)

            if pdf_url is None:
                print("❌ PDF Link Not Found")
                continue

            print("PDF :", pdf_url)

            download_pdf(
                pdf_url,
                pmcid,
                cancer
            )

            download_xml(
                pmcid,
                cancer
            )

            downloaded += 1

            time.sleep(1)

        print(f"\nDownloaded {downloaded} paper(s) for {cancer}")

    print("\n")
    print("=" * 90)
    print("ALL DOWNLOADS COMPLETED")
    print("=" * 90)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()