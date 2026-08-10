import fitz
from pathlib import Path
from PIL import Image


class PDFProcessor:

    @staticmethod
    def extract(file_path: str):
        """
        Extract:
        - Full text
        - Page-wise text
        - Embedded images
        - Image metadata
        """

        doc = fitz.open(file_path)

        pages = []
        full_text = ""
        extracted_images = []

        output_folder = Path("sample_files/extracted_images")
        output_folder.mkdir(parents=True, exist_ok=True)

        pdf_name = Path(file_path).stem

        for page_number, page in enumerate(doc):

            # -------------------------------
            # Extract Page Text
            # -------------------------------
            text = page.get_text()

            pages.append({
                "page": page_number + 1,
                "text": text
            })

            full_text += text + "\n"

            # -------------------------------
            # Extract Images
            # -------------------------------
            image_list = page.get_images(full=True)

            for image_index, img in enumerate(image_list):

                xref = img[0]

                pix = fitz.Pixmap(doc, xref)

                image_name = (
                    f"{pdf_name}_page{page_number + 1}_img{image_index + 1}.png"
                )

                image_path = output_folder / image_name

                # Convert CMYK → RGB if needed
                if pix.n < 5:
                    pix.save(image_path)
                else:
                    rgb_pix = fitz.Pixmap(fitz.csRGB, pix)
                    rgb_pix.save(image_path)
                    rgb_pix = None

                # Read image metadata
                image = Image.open(image_path)

                width, height = image.size

                file_size = image_path.stat().st_size / 1024

                extracted_images.append({
                    "page": page_number + 1,
                    "image_name": image_name,
                    "image_path": str(image_path),
                    "width": width,
                    "height": height,
                    "mode": image.mode,
                    "format": image.format,
                    "file_size_kb": round(file_size, 2)
                })

                image.close()
                pix = None

        doc.close()

        return {
            "text": full_text,
            "pages": pages,
            "images": extracted_images,
            "total_pages": len(pages)
        }