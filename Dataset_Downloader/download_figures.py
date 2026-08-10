import os
import xml.etree.ElementTree as ET
import requests

XML_FOLDER = "downloads/xml"
IMAGE_FOLDER = "downloads/figures"

os.makedirs(IMAGE_FOLDER, exist_ok=True)


def download_image(url, save_path):

    try:

        response = requests.get(url, timeout=30)

        if response.status_code == 200:

            with open(save_path, "wb") as f:
                f.write(response.content)

            return True

    except Exception:
        pass

    return False


def process_xml(xml_path):

    tree = ET.parse(xml_path)

    root = tree.getroot()

    pmcid = os.path.splitext(os.path.basename(xml_path))[0]

    cancer = os.path.basename(os.path.dirname(xml_path))

    save_folder = os.path.join(
        IMAGE_FOLDER,
        cancer,
        pmcid
    )

    os.makedirs(save_folder, exist_ok=True)

    namespace = {
        "xlink": "http://www.w3.org/1999/xlink"
    }

    total = 0

    for fig in root.iter("fig"):

        graphic = fig.find("graphic")

        if graphic is None:
            continue

        href = graphic.attrib.get(
            "{http://www.w3.org/1999/xlink}href"
        )

        if href is None:
            continue

        image_url = (
            f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{href}.jpg"
        )

        save_path = os.path.join(
            save_folder,
            f"{href}.jpg"
        )

        if download_image(image_url, save_path):

            print("Downloaded", href)

            total += 1

    return total


def main():

    total_xml = 0
    total_images = 0

    for cancer in sorted(os.listdir(XML_FOLDER)):

        cancer_folder = os.path.join(XML_FOLDER, cancer)

        if not os.path.isdir(cancer_folder):
            continue

        print("=" * 70)
        print(cancer)

        for file in sorted(os.listdir(cancer_folder)):

            if not file.endswith(".xml"):
                continue

            total_xml += 1

            xml_path = os.path.join(cancer_folder, file)

            print(file)

            count = process_xml(xml_path)

            print("Images :", count)

            total_images += count

    print("\n" + "=" * 70)
    print("FINISHED")
    print("=" * 70)

    print("XML Files :", total_xml)
    print("Images :", total_images)


if __name__ == "__main__":
    main()