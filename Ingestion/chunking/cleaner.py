"""
Text cleaning utilities for medical reports.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean report text while preserving medical information.

    Parameters
    ----------
    text : str
        Raw report text.

    Returns
    -------
    str
        Cleaned report text.
    """

    if not isinstance(text, str):
        return ""

    # Normalize newlines
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Collapse multiple spaces
    text = re.sub(r"[ ]{2,}", " ", text)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()