import os
import shutil

from PIL import Image


# ==========================================================
# PATHS
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


DOWNLOAD_FOLDER = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "../../Dataset_Downloader/downloads"
    )
)


OUTPUT_FOLDER = os.path.abspath(
    os.path.join(
        BASE_DIR,
        "../processed_dataset/filtered_images"
    )
)


os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)


VALID_EXTENSIONS = (

    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp"

)
# ==========================================================
# Find All Images
# ==========================================================

def find_images():

    image_files = []

    for root, dirs, files in os.walk(DOWNLOAD_FOLDER):

        for file in files:

            extension = os.path.splitext(file)[1].lower()

            if extension in VALID_EXTENSIONS:

                image_files.append(
                    os.path.join(root, file)
                )

    return image_files


# ==========================================================
# Validate Image
# ==========================================================

def validate_image(image_path):

    try:

        img = Image.open(image_path)

        width, height = img.size

        # Remove very small images/icons
        if width < 150 or height < 150:
            return False

        # Remove extremely thin images
        ratio = width / height

        if ratio > 6 or ratio < 0.15:
            return False

        # Verify image is not corrupted
        img.verify()

        return True

    except Exception:

        return False


# ==========================================================
# Scan Images
# ==========================================================

def scan_images():

    images = find_images()

    print("=" * 80)
    print(f"Total Images Found : {len(images)}")
    print("=" * 80)

    valid_images = []

    rejected = 0

    for image in images:

        if validate_image(image):

            valid_images.append(image)

        else:

            rejected += 1

    print(f"Valid Images    : {len(valid_images)}")
    print(f"Rejected Images : {rejected}")

    return valid_images
# ==========================================================
# Copy Valid Images
# ==========================================================

def copy_images(valid_images):

    copied = 0

    for image_path in valid_images:

        relative_path = os.path.relpath(
            image_path,
            DOWNLOAD_FOLDER
        )

        destination = os.path.join(
            OUTPUT_FOLDER,
            relative_path
        )

        destination_folder = os.path.dirname(
            destination
        )

        os.makedirs(
            destination_folder,
            exist_ok=True
        )

        try:

            shutil.copy2(
                image_path,
                destination
            )

            copied += 1

        except Exception as e:

            print(f"Error copying {image_path}")
            print(e)

    print()
    print("=" * 80)
    print(f"Images Copied : {copied}")
    print("=" * 80)


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    print()
    print("=" * 80)
    print("MEDICAL IMAGE VALIDATOR")
    print("=" * 80)

    print("Download Folder :", DOWNLOAD_FOLDER)
    print("Output Folder   :", OUTPUT_FOLDER)
    print()

    if not os.path.exists(DOWNLOAD_FOLDER):

        print("Download folder not found.")
        exit()

    valid_images = scan_images()

    copy_images(valid_images)

    print()
    print("=" * 80)
    print("Validation Completed")
    print("=" * 80)