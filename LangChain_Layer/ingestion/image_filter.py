from PIL import Image
import cv2
import numpy as np


class ImageFilter:

    MIN_WIDTH = 200
    MIN_HEIGHT = 200
    MIN_FILE_SIZE_KB = 20

    BLUR_THRESHOLD = 80
    WHITE_THRESHOLD = 245
    BLACK_THRESHOLD = 10

    @staticmethod
    def is_blurry(image_path):

        image = cv2.imread(image_path)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        print(f"{image_path} -> Blur Score: {variance:.2f}")
        return variance < ImageFilter.BLUR_THRESHOLD

    @staticmethod
    def is_blank(image_path):

        image = Image.open(image_path)

        gray = image.convert("L")

        arr = np.array(gray)

        mean = arr.mean()

        if mean > ImageFilter.WHITE_THRESHOLD:
            return True

        if mean < ImageFilter.BLACK_THRESHOLD:
            return True

        return False

    @staticmethod
    def filter_images(images):

        accepted = []
        rejected = []

        for img in images:

            reason = None

            if img["width"] < ImageFilter.MIN_WIDTH:
                reason = "Width too small"

            elif img["height"] < ImageFilter.MIN_HEIGHT:
                reason = "Height too small"

            elif img["file_size_kb"] < ImageFilter.MIN_FILE_SIZE_KB:
                reason = "File size too small"

            elif ImageFilter.is_blank(img["image_path"]):
                reason = "Blank image"

            elif ImageFilter.is_blurry(img["image_path"]):
                reason = "Blurry image"

            if reason:

                rejected.append({
                    "image": img,
                    "reason": reason
                })

            else:

                accepted.append(img)

        return {
            "accepted": accepted,
            "rejected": rejected
        }