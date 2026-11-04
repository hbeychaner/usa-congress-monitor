"""Bounds and source identity for controlled enacted-law text enrichment."""

from pydantic import BaseModel, ConfigDict


class StatuteTextSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    parser_version: str = "uslm-law-v1"
    volume_base_url: str = "https://www.govinfo.gov/bulkdata/STATUTE"
    pdf_pattern: str = (
        r"^https://www\.congress\.gov/(?P<congress>\d+)/statute/"
        r"STATUTE-(?P<volume>\d+)/"
        r"(?P<package_id>STATUTE-(?P=volume)-Pg(?P<page>\d+)(?:-\d+)?)\.pdf$"
    )
