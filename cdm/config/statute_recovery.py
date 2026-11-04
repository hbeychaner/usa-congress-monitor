"""Official bibliographic and PDF evidence for historical enacted laws."""

from pydantic import BaseModel, ConfigDict

from cdm.store.create_only import MeasureType


class StatuteRecoverySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    mods_namespace: str = "http://www.loc.gov/mods/v3"
    xlink_namespace: str = "http://www.w3.org/1999/xlink"
    metadata_base: str = "https://www.govinfo.gov/metadata"
    content_base: str = "https://www.govinfo.gov/content/pkg"
    citation_pattern: str = r"^(?P<volume>\d+)\s+Stat\.\s*(?P<page>\d+(?:-\d+)?)$"
    law_pattern: str = (
        r"^(?P<kind>Public|Private) Law (?P<congress>\d+)-(?P<number>\d+)$"
    )
    maximum_pdf_bytes: int = 64 * 1024**2
    maximum_pdf_pages: int = 1000
    maximum_text_characters: int = 16 * 1024**2
    header_characters: int = 4000
    parser_version: str = "statute-metadata-pdf-v1"
    body_heading_pattern: str = (
        r"\b(?P<kind>Public|Private)\s+Law\s*(?P<congress>\d+)\s*[-\u2013\u2014]\s*"
        r"(?P<number>\d+)\W{0,80}\d+(?:st|nd|rd|th)\s*Congress\b"
    )
    bill_patterns: dict[MeasureType, str] = {
        MeasureType.HR: r"H\.?\s*R\.?",
        MeasureType.S: r"S\.?",
        MeasureType.HJRES: r"H\.?\s*J\.?\s*Res\.?",
        MeasureType.SJRES: r"S\.?\s*J\.?\s*Res\.?",
    }
