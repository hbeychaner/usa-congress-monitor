"""Conservative source reconciliation policy; live merge behavior is unchanged."""

from enum import StrEnum
from typing import NewType

from pydantic import BaseModel, ConfigDict, Field

FieldName = NewType("FieldName", str)


class SourceName(StrEnum):
    BILLSTATUS = "govinfo:billstatus"
    BILLSUM = "govinfo:billsum"
    BILLS = "govinfo:bills"
    STATUTE = "govinfo:statute"
    CONGRESS = "congress.gov_api"
    UNKNOWN = "unknown"


class SourcePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    authority: tuple[SourceName, ...] = (
        SourceName.BILLSTATUS,
        SourceName.CONGRESS,
        SourceName.BILLSUM,
    )
    list_fields: frozenset[FieldName] = frozenset(
        map(
            FieldName,
            (
                "actions",
                "amendments",
                "committees",
                "cosponsors",
                "laws",
                "related_bills",
                "subjects",
                "summaries",
                "text_versions",
                "titles",
            ),
        )
    )
    identity_fields: frozenset[FieldName] = frozenset(
        map(
            FieldName,
            (
                "id",
                "source_metadata",
                "source_snapshot",
                "source_snapshot_unavailable_reason",
                "source_checked_at",
                "reconciliation",
                "hydration_assessment",
                "hydration_status",
                "detail_hydration",
                "hydrated_at",
                "hydrated_sources",
            ),
        )
    )
    bill_id_pattern: str = (
        r"^(bill:(\d+):([a-z]+):(\d+))(?::\d{4}-\d{2}-\d{2}(?:[T ].*)?)?$"
    )
    freshness_hours: int = Field(default=24, gt=0)
    version_fields: tuple[FieldName, ...] = (
        FieldName("updateDate"),
        FieldName("updateDateIncludingText"),
    )
    billstatus_fields: dict[FieldName, str] = {
        FieldName("title"): "title",
        FieldName("introduced_date"): "introducedDate",
        FieldName("sponsors"): "sponsors",
        FieldName("actions"): "actions",
        FieldName("latest_action"): "actions",
        FieldName("policy_area"): "subjects",
        FieldName("cosponsors"): "cosponsors",
        FieldName("committees"): "committees",
        FieldName("related_bills"): "relatedBills",
        FieldName("summaries"): "summaries",
        FieldName("subjects"): "subjects",
        FieldName("titles"): "titles",
        FieldName("text_versions"): "textVersions",
        FieldName("laws"): "laws",
        FieldName("amendments"): "amendments",
    }

    def rank(self, source: SourceName, field: FieldName) -> int:
        order = (
            (SourceName.BILLSUM, SourceName.BILLSTATUS, SourceName.CONGRESS)
            if field == "summaries"
            else self.authority
        )
        return order.index(source) if source in order else len(order)
