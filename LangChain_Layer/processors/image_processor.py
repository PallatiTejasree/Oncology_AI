from pathlib import Path
from PIL import Image
import os


def process_image(file_path: str):
    """
    Process uploaded medical image
    """

    path = Path(file_path)

    try:
        image = Image.open(file_path)

        metadata = {
            "file_name": path.name,
            "file_type": path.suffix,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "file_size": os.path.getsize(file_path)
        }


        return {
            "image_path": file_path,
            "metadata": metadata
        }


    except Exception as e:
        print(f"Image processing error: {e}")
        return None