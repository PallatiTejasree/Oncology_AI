"""Parse downloaded JATS XML into one canonical JSON document per PMCID."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from Ingestion.config import DOWNLOADS_DIR, PARSED_JSON_DIR

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def normalize_pmcid(value: str) -> str:
    value = (value or "").strip().upper()
    if value.isdigit():
        return f"PMC{value}"
    return value


def find_xml_files(root_folder: Path = DOWNLOADS_DIR) -> list[Path]:
    return sorted(
        path
        for path in Path(root_folder).rglob("*")
        if path.is_file() and path.suffix.lower() in {".xml", ".nxml"}
    )


def get_text(element) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def parse_xml(xml_file: str | Path) -> dict:
    root = ET.parse(xml_file).getroot()

    def article_id(identifier_type: str) -> str:
        for element in root.findall(".//article-id"):
            if element.attrib.get("pub-id-type") == identifier_type:
                return get_text(element)
        return ""

    authors = []
    for contributor in root.findall(".//contrib"):
        if contributor.attrib.get("contrib-type") != "author":
            continue
        name = " ".join(
            part
            for part in (
                get_text(contributor.find(".//given-names")),
                get_text(contributor.find(".//surname")),
            )
            if part
        )
        if name:
            authors.append(name)

    sections = []
    for section in root.findall(".//sec"):
        paragraphs = [get_text(item) for item in section.findall("p")]
        paragraphs = [text for text in paragraphs if text]
        if paragraphs:
            sections.append(
                {"title": get_text(section.find("title")), "text": "\n".join(paragraphs)}
            )

    figures = []
    for figure in root.findall(".//fig"):
        graphic = figure.find(".//graphic")
        figures.append(
            {
                "figure_id": figure.attrib.get("id", ""),
                "label": get_text(figure.find("label")),
                "image": graphic.attrib.get(XLINK_HREF, "") if graphic is not None else "",
                "caption": get_text(figure.find(".//caption")),
            }
        )

    return {
        "title": get_text(root.find(".//article-title")),
        "abstract": get_text(root.find(".//abstract")),
        "journal": get_text(root.find(".//journal-title")),
        "pmcid": article_id("pmc"),
        "doi": article_id("doi"),
        "authors": authors,
        "keywords": [text for text in map(get_text, root.findall(".//kwd")) if text],
        "sections": sections,
        "figures": figures,
    }


def cancer_type_from_path(xml_file: Path, downloads_dir: Path = DOWNLOADS_DIR) -> str:
    relative = xml_file.resolve().relative_to(Path(downloads_dir).resolve())
    return relative.parts[0]


def _merge_existing_labels(output_file: Path, cancer_type: str) -> list[str]:
    labels = {cancer_type}
    if output_file.exists():
        existing = json.loads(output_file.read_text(encoding="utf-8"))
        labels.update(existing.get("cancer_types") or [])
        if existing.get("cancer_type"):
            labels.add(existing["cancer_type"])
    return sorted(labels)


def process_all_xml(
    downloads_dir: Path = DOWNLOADS_DIR,
    output_dir: Path = PARSED_JSON_DIR,
) -> dict:
    downloads_dir = Path(downloads_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    written = 0

    for xml_file in find_xml_files(downloads_dir):
        try:
            article = parse_xml(xml_file)
            cancer_type = cancer_type_from_path(xml_file, downloads_dir)
            pmcid = normalize_pmcid(article["pmcid"] or xml_file.parent.name)
            if not pmcid:
                raise ValueError("Unable to determine PMCID")

            output_file = output_dir / f"{pmcid}.json"
            labels = _merge_existing_labels(output_file, cancer_type)
            article.update(
                {
                    "pmcid": pmcid,
                    "cancer_type": labels[0],
                    "cancer_types": labels,
                    "source_xml": str(xml_file.resolve()),
                }
            )
            output_file.write_text(
                json.dumps(article, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            written += 1
        except Exception as exc:  # retain the complete batch and report failures
            failures.append({"file": str(xml_file), "error": str(exc)})

    unique_documents = len(list(output_dir.glob("PMC*.json")))
    return {
        "xml_files": written + len(failures),
        "processed": written,
        "unique_documents": unique_documents,
        "failures": failures,
    }


if __name__ == "__main__":
    result = process_all_xml()
    print(json.dumps(result, indent=2))
