"""Deterministic checks that uploaded files belong to the same clinical case."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_SPACE = re.compile(r"\s+")
_NAME_PATTERNS = (
    re.compile(r"(?im)^\s*patient\s+name\s*[:\-]\s*([^\n|]+)"),
    re.compile(r"(?im)^\s*patient\s*[:\-]\s*([^\n|]+)"),
)
_ID_PATTERNS = (
    re.compile(r"(?im)^\s*patient\s+id\s*[:\-]\s*([a-z0-9/\-]+)"),
)
_AGE_GENDER = re.compile(
    r"(?im)^\s*age\s*(?:/|&|and)\s*gender\s*[:\-]\s*(\d{1,3})\s*(?:y|yrs?|years?)?\s*/?\s*(male|female|m|f)\b"
)
_AGE_PATTERNS = (
    re.compile(r"(?im)^\s*age\s*[:\-]\s*(\d{1,3})\s*(?:y|yrs?|years?)?\b"),
    re.compile(r"(?im)\b(\d{1,3})\s*(?:y|yrs?|years?)\s*/\s*(?:male|female|m|f)\b"),
)
_GENDER_PATTERNS = (
    re.compile(r"(?im)^\s*(?:gender|sex)\s*[:\-]\s*(male|female|m|f)\b"),
    re.compile(r"(?im)\b\d{1,3}\s*(?:y|yrs?|years?)\s*/\s*(male|female|m|f)\b"),
)
_DATE_PATTERN = re.compile(r"\b(?:\d{1,2}[-/.](?:\d{1,2}|[A-Za-z]{3,9})[-/.]\d{2,4})\b")

_MODALITY_TERMS = {
    "ct": ("ct scan", "computed tomography", "ct thorax", "ct abdomen"),
    "mri": ("mri", "magnetic resonance"),
    "pet_ct": ("pet-ct", "pet/ct", "fdg pet"),
    "ultrasound": ("ultrasound", "sonography", "usg"),
    "pathology": ("histopathology", "pathology report", "biopsy", "microscopy"),
    "laboratory": ("laboratory report", "blood test", "complete blood count", "cbc"),
    "xray": ("x-ray", "x ray", "radiograph"),
}
_ANATOMY_TERMS = {
    "brain": ("brain", "cerebral", "intracranial"),
    "breast": ("breast",),
    "lung": ("lung", "pulmonary", "thorax", "chest"),
    "liver": ("liver", "hepatic"),
    "colon_rectum": ("colon", "colorectal", "rectal", "sigmoid"),
    "prostate": ("prostate",),
    "ovary": ("ovary", "ovarian", "adnexal"),
    "uterus_cervix": ("uterus", "uterine", "cervix", "cervical"),
    "bone": ("bone", "osseous", "iliac"),
    "lymph_nodes": ("lymph node", "lymphadenopathy", "nodal"),
}
_CANCER_TERMS = {
    "breast_cancer": ("breast carcinoma", "breast cancer", "ductal carcinoma", "lobular carcinoma"),
    "colorectal_cancer": ("colorectal carcinoma", "colorectal cancer", "colon cancer", "rectal cancer"),
    "lung_cancer": ("lung carcinoma", "lung cancer", "pulmonary carcinoma"),
    "prostate_cancer": ("prostate carcinoma", "prostate cancer"),
    "lymphoma": ("lymphoma",),
    "leukemia": ("leukemia", "leukaemia"),
    "sarcoma": ("sarcoma",),
    "myeloma": ("myeloma",),
}


@dataclass(frozen=True)
class MaterialIdentity:
    file_name: str
    patient_name: str | None = None
    patient_id: str | None = None
    age: int | None = None
    gender: str | None = None
    dates: tuple[str, ...] = ()
    modalities: tuple[str, ...] = ()
    anatomy: tuple[str, ...] = ()
    cancer_labels: tuple[str, ...] = ()
    laterality: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConsistencyResult:
    consistent: bool
    user_message: str | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 100.0
    status: str = "consistent"
    identities: list[MaterialIdentity] = field(default_factory=list)


def _clean_identifier(value: str) -> str:
    return _SPACE.sub(" ", value).strip(" .,:;-_").casefold()


def _first_match(patterns: tuple[re.Pattern, ...], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text or "")
        if match:
            value = _clean_identifier(match.group(1))
            if value:
                return value
    return None


def _term_matches(text: str, vocabulary: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    normalized = _SPACE.sub(" ", text.casefold())
    return tuple(sorted(
        label for label, terms in vocabulary.items()
        if any(term in normalized for term in terms)
    ))


def _extract_age_gender(text: str) -> tuple[int | None, str | None]:
    combined = _AGE_GENDER.search(text)
    age = int(combined.group(1)) if combined else None
    gender = combined.group(2) if combined else None
    if age is None:
        raw_age = _first_match(_AGE_PATTERNS, text)
        age = int(raw_age) if raw_age and raw_age.isdigit() else None
    if gender is None:
        gender = _first_match(_GENDER_PATTERNS, text)
    if gender:
        gender = gender.casefold()
        gender = {"m": "male", "f": "female"}.get(gender, gender)
    return age, gender


def extract_material_identity(file_name: str, text: str | None) -> MaterialIdentity:
    content = text or ""
    age, gender = _extract_age_gender(content)
    normalized = content.casefold()
    laterality = tuple(
        side for side in ("left", "right", "bilateral")
        if re.search(rf"\b{side}\b", normalized)
    )
    return MaterialIdentity(
        file_name=file_name,
        patient_name=_first_match(_NAME_PATTERNS, content),
        patient_id=_first_match(_ID_PATTERNS, content),
        age=age,
        gender=gender,
        dates=tuple(dict.fromkeys(_DATE_PATTERN.findall(content))),
        modalities=_term_matches(content, _MODALITY_TERMS),
        anatomy=_term_matches(content, _ANATOMY_TERMS),
        cancer_labels=_term_matches(content, _CANCER_TERMS),
        laterality=laterality,
    )


def assess_upload_consistency(sources: list[dict[str, str | None]]) -> ConsistencyResult:
    """Reject a group only when explicit cross-file identifiers conflict.

    Different modalities (for example pathology and CT) can legitimately belong
    to one case, so modality alone is never considered a mismatch.
    """
    identities = [
        extract_material_identity(str(source.get("file_name") or "uploaded file"), source.get("text"))
        for source in sources
        if source.get("text")
    ]
    if len(identities) < 2:
        return ConsistencyResult(True, status="insufficient_identifiers", identities=identities)

    reasons: list[str] = []
    warnings: list[str] = []
    score = 100.0
    names = {item.patient_name for item in identities if item.patient_name}
    patient_ids = {item.patient_id for item in identities if item.patient_id}
    genders = {item.gender for item in identities if item.gender}
    ages = [item.age for item in identities if item.age is not None]
    if len(names) > 1:
        reasons.append("The patient names found in the uploaded files do not match.")
        score -= 70
    if len(patient_ids) > 1:
        reasons.append("The patient identifiers found in the uploaded files do not match.")
        score -= 80
    if len(genders) > 1:
        reasons.append("The patient gender details found in the uploaded files do not match.")
        score -= 65

    if len(ages) > 1 and max(ages) - min(ages) > 5:
        warnings.append("The recorded ages differ substantially; please confirm the files are from the intended case.")
        score -= 10

    labelled_anatomy = [set(item.anatomy) for item in identities if item.anatomy]
    if len(labelled_anatomy) > 1 and not set.intersection(*labelled_anatomy):
        warnings.append("The files focus on different anatomical areas; this may be valid for staging or follow-up care.")
        score -= 5

    labelled_cancers = [set(item.cancer_labels) for item in identities if item.cancer_labels]
    if len(labelled_cancers) > 1 and not set.intersection(*labelled_cancers):
        warnings.append("The files mention different cancer types; please confirm they belong to the same case.")
        score -= 15

    score = max(0.0, round(score, 1))

    if not reasons:
        return ConsistencyResult(
            True,
            warnings=warnings,
            score=score,
            status="needs_review" if warnings else "consistent",
            identities=identities,
        )

    return ConsistencyResult(
        False,
        (
            "These uploaded materials do not appear to belong to the same patient or clinical case. "
            "Please upload the correct matching report and image, then try again. No AI analysis was performed."
        ),
        reasons=reasons,
        warnings=warnings,
        score=score,
        status="mismatch",
        identities=identities,
    )


def consistency_diagnostics(consistency: ConsistencyResult) -> dict:
    """Return non-sensitive structured diagnostics suitable for persistence."""
    return {
        "status": consistency.status,
        "score": consistency.score,
        "calibrated": False,
        "reasons": consistency.reasons,
        "warnings": consistency.warnings,
        "files_checked": [item.file_name for item in consistency.identities],
        "signals": [
            {
                "file_name": item.file_name,
                "patient_name_present": bool(item.patient_name),
                "patient_id_present": bool(item.patient_id),
                "age_present": item.age is not None,
                "gender_present": bool(item.gender),
                "modalities": list(item.modalities),
                "anatomy": list(item.anatomy),
                "cancer_labels": list(item.cancer_labels),
                "laterality": list(item.laterality),
                "dates_found": len(item.dates),
            }
            for item in consistency.identities
        ],
    }


def mismatch_result(consistency: ConsistencyResult, user_message: str | None = None) -> dict:
    details = " ".join(consistency.reasons)
    return {
        "query_type": "validation",
        "response_type": "rejection",
        "intent": "upload_mismatch",
        "summary": " ".join(filter(None, [user_message or consistency.user_message, details])),
        "evidence": [],
        "supporting_image_evidence": [],
        "uploaded_sources": [],
        "diagnostics": {
            "upload_consistency": consistency_diagnostics(consistency)
        },
        "model_name": "deterministic-upload-consistency-v1",
        "disclaimer": None,
    }
