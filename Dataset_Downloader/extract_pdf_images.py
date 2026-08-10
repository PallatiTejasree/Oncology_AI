import os
import fitz  # PyMuPDF

# ==========================================================
# Paths
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PDF_FOLDER = os.path.join(BASE_DIR, "downloads", "pdfs")

OUTPUT_FOLDER = os.path.join(BASE_DIR, "downloads", "pdf_images")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ==========================================================
# Extract Images
# ==========================================================

def extract_images(pdf_path):

    document = fitz.open(pdf_path)

    cancer_type = os.path.basename(os.path.dirname(pdf_path))

    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

    save_folder = os.path.join(
        OUTPUT_FOLDER,
        cancer_type,
        pdf_name
    )

    os.makedirs(save_folder, exist_ok=True)

    image_count = 0

    for page_number in range(len(document)):

        page = document.load_page(page_number)

        images = page.get_images(full=True)

        for index, image in enumerate(images):

            xref = image[0]

            pix = fitz.Pixmap(document, xref)

            if pix.n < 5:
                image_path = os.path.join(
                    save_folder,
                    f"page_{page_number+1}_img_{index+1}.png"
                )
                pix.save(image_path)

            else:
                rgb = fitz.Pixmap(fitz.csRGB, pix)
                image_path = os.path.join(
                    save_folder,
                    f"page_{page_number+1}_img_{index+1}.png"
                )
                rgb.save(image_path)
                rgb = None

            pix = None
            image_count += 1

    document.close()

    return image_count


# ==========================================================
# Main
# ==========================================================

def main():

    print("=" * 70)
    print("PDF IMAGE EXTRACTION")
    print("=" * 70)

    print("\nCurrent Working Directory:")
    print(BASE_DIR)

    print("\nLooking for PDFs inside:")
    print(PDF_FOLDER)

    pdfs = []

    for root, dirs, files in os.walk(PDF_FOLDER):

        for file in files:

            if file.lower().endswith(".pdf"):

                pdfs.append(os.path.join(root, file))

    print(f"\nFound {len(pdfs)} PDF(s)\n")

    if len(pdfs) == 0:
        print("No PDF files found.")
        return

    total_images = 0

    for pdf_path in pdfs:

        try:

            cancer_type = os.path.basename(os.path.dirname(pdf_path))

            pdf_name = os.path.basename(pdf_path)

            print("=" * 70)
            print("Cancer :", cancer_type)
            print("PDF    :", pdf_name)

            count = extract_images(pdf_path)

            print(f"Extracted {count} image(s)\n")

            total_images += count

        except Exception as e:

            print("ERROR :", e)

    print("=" * 70)
    print("EXTRACTION FINISHED")
    print("=" * 70)

    print(f"Total PDFs   : {len(pdfs)}")
    print(f"Total Images : {total_images}")


if __name__ == "__main__":
    main()