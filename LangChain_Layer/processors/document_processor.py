import os
from pathlib import Path
from pypdf import PdfReader


def extract_text_from_pdf(file_path: str):
    """
    Extract text from medical PDF reports
    """

    text = ""

    try:
        reader = PdfReader(file_path)

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text.strip()

    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None



def process_document(file_path: str):
    """
    Main document processing function
    """

    path = Path(file_path)

    metadata = {
        "file_name": path.name,
        "file_type": path.suffix,
        "file_size": os.path.getsize(file_path)
    }


    if path.suffix.lower() == ".pdf":

        text = extract_text_from_pdf(file_path)

    elif path.suffix.lower() == ".txt":

        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()

    else:
        raise ValueError(
            "Unsupported document format"
        )


    return {
        "metadata": metadata,
        "text": text
    }