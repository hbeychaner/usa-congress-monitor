"""Measured read ceilings and narrow projections for interactive APIs."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cdm.contracts.queries import QueryReadError


class ActivityKind(StrEnum):
    BILL = "bill"
    AMENDMENT = "amendment"


class SearchKind(StrEnum):
    MEMBER = "member"
    STATE = "state"
    BILL = "bill"


class BillProjectionKind(StrEnum):
    BILL = "bill"
    LAW = "law"


class BillReadField(StrEnum):
    ID = "id"
    SOURCE_TYPE = "source_type"


class BillIdentityPrefix(StrEnum):
    BILL = "bill:"


class QueryReadConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_result_window: int = Field(default=10000, ge=100, le=10000)
    max_page_size: int = Field(default=100, gt=0, le=100)
    vote_bucket_limit: int = Field(default=20000, gt=0, le=20000)
    max_query_chars: int = 200
    bill_relationship_fields: tuple[str, ...] = (
        "actions",
        "amendments",
        "committees",
        "cosponsors",
        "summaries",
        "titles",
        "text_versions",
    )
    bill_fields: tuple[str, ...] = (
        "id",
        "title",
        "congress",
        "bill_type",
        "number",
        "origin_chamber",
        "chamber",
        "update_date",
    )
    member_search_fields: tuple[str, ...] = (
        "id",
        "bioguide_id",
        "name",
        "full_name",
        "direct_order_name",
        "party_name",
        "party",
        "state_code",
        "state",
    )
    member_fields: tuple[str, ...] = (
        "id",
        "bioguide_id",
        "name",
        "full_name",
        "party_name",
        "party",
        "state",
        "state_code",
        "terms",
        "district",
        "depiction.image_url",
        "image_url",
    )
    bill_search_fields: tuple[str, ...] = (
        "id",
        "title",
        "congress",
        "bill_type",
        "number",
    )
    activity_fields: tuple[str, ...] = (
        "id",
        "title",
        "congress",
        "update_date",
        "latest_action_date",
        "sponsor_bioguide_ids",
        "type",
        "number",
        "purpose",
        "description",
        "submitted_date",
        "amended_bill.id",
        "amended_bill.title",
        "amended_bill_id",
    )
    activity_date_script: str = """
        String primary = doc['id'].value.startsWith('bill:')
            ? 'latest_action_date' : 'submitted_date';
        for (String field : [primary, 'update_date']) {
            if (doc.containsKey(field) && doc[field].size() != 0) {
                emit(doc[field].value.toInstant().toEpochMilli()); return;
            }
        }
    """

    def offset(self, page: int, limit: int) -> int:
        if page < 1:
            raise QueryReadError("Page must be positive.", "page")
        if not 1 <= limit <= self.max_page_size:
            raise QueryReadError(
                f"Limit must be between 1 and {self.max_page_size}.", "limit"
            )
        if page * limit > self.max_result_window:
            raise QueryReadError(
                f"Browsing is limited to the first {self.max_result_window:,} matches; narrow the filters.",
                "page",
            )
        return (page - 1) * limit

    def text(self, value: str, parameter: str) -> None:
        if len(value) > self.max_query_chars:
            raise QueryReadError(
                f"Query text cannot exceed {self.max_query_chars} characters.",
                parameter,
            )

    def selected[E: StrEnum](self, value: str | None, kind: type[E]) -> list[E]:
        self.text(value or "", "types")
        tokens = [
            token.strip().lower() for token in (value or "").split(",") if token.strip()
        ]
        try:
            return (
                list(dict.fromkeys(kind(token) for token in tokens))
                if tokens
                else list(kind)
            )
        except ValueError as exc:
            raise QueryReadError(
                f"Supported types: {', '.join(item.value for item in kind)}.", "types"
            ) from exc
