"""Settings for controlled reading of official Statutes at Large XML."""

from pydantic import BaseModel, ConfigDict


class StatutesSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    namespace: str = "http://schemas.gpo.gov/xml/uslm"
    dc_namespace: str = "http://purl.org/dc/elements/1.1/"
    root_tag: str = "statutesAtLarge"
    law_tag: str = "pLaw"
    citation_pattern: str = r"^(?P<volume>\d+) Stat\. (?P<page>\d+(?:-\d+)?)$"
    law_citation_pattern: str = (
        r"^(?P<kind>Public|Private) Law (?P<congress>\d+)-(?P<number>\d+)$"
    )
    page_identifier_pattern: str = r"^/us/stat/(?P<volume>\d+)/(?P<page>\d+(?:-\d+)?)$"
    block_elements: frozenset[str] = frozenset(
        (
            "p",
            "section",
            "subsection",
            "paragraph",
            "subparagraph",
            "title",
            "subtitle",
            "chapter",
            "heading",
            "longTitle",
            "enactingFormula",
            "appropriations",
            "table",
            "tr",
            "td",
            "page",
        )
    )
