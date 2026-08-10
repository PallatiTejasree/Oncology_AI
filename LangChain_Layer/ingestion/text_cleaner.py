import re


class MedicalTextCleaner:

    @staticmethod
    def clean(text: str):

        # -----------------------------
        # Remove URLs
        # -----------------------------
        text = re.sub(r"http\S+", " ", text)

        # -----------------------------
        # Remove DOI
        # -----------------------------
        text = re.sub(r"doi:\S+", " ", text, flags=re.IGNORECASE)

        # -----------------------------
        # Remove Copyright
        # -----------------------------
        text = re.sub(
            r"©.*?reserved\.",
            " ",
            text,
            flags=re.IGNORECASE
        )

        # -----------------------------
        # Remove journal citation line
        # Example:
        # Transl Cancer Res 2020;9(5):3721-3724 |
        # -----------------------------
        text = re.sub(
            r"Transl\s+Cancer\s+Res\s+\d{4}.*?\|",
            " ",
            text,
            flags=re.IGNORECASE
        )

        # -----------------------------
        # Remove page headers like
        # Page 1 of 5
        # -----------------------------
        text = re.sub(
            r"Page\s+\d+\s+of\s+\d+",
            " ",
            text,
            flags=re.IGNORECASE
        )

        # -----------------------------
        # Remove multiple spaces
        # -----------------------------
        text = re.sub(r"\s+", " ", text)

        # -----------------------------
        # Remove page breaks
        # -----------------------------
        text = text.replace("\x0c", " ")

        return text.strip()