"""Canonical bill reads include enacted-law projections without reclassification."""

from pydantic import TypeAdapter, ValidationError

from cdm.config.query_reads import (
    BillIdentityPrefix,
    BillProjectionKind,
    BillReadField,
)
from cdm.store.client import IncompleteSearchError
from cdm.store.create_only import BillId, CanonicalBillIdentity
from cdm.utils.json_types import JsonObject


class BillReadScope:
    @staticmethod
    def identity_query(text: str) -> JsonObject | None:
        try:
            identity = TypeAdapter(BillId).validate_python(text.strip().lower())
        except ValidationError:
            return None
        return {"term": {BillReadField.ID: identity}}

    @staticmethod
    def query() -> JsonObject:
        return {
            "bool": {
                "filter": [
                    {
                        "terms": {
                            BillReadField.SOURCE_TYPE: [
                                kind.value for kind in BillProjectionKind
                            ]
                        }
                    },
                    {"prefix": {BillReadField.ID: BillIdentityPrefix.BILL}},
                ]
            }
        }

    @staticmethod
    def contains(source: JsonObject, identity: str) -> bool:
        kind = source.get(BillReadField.SOURCE_TYPE)
        if kind == BillProjectionKind.BILL:
            return True
        if kind != BillProjectionKind.LAW or not identity.startswith(
            BillIdentityPrefix.BILL
        ):
            return False
        try:
            canonical = CanonicalBillIdentity.model_validate(source)
        except ValidationError as exc:
            raise IncompleteSearchError(
                f"Law projection has an invalid canonical bill identity: {identity}"
            ) from exc
        if canonical.id != identity:
            raise IncompleteSearchError(
                f"Law projection identity disagrees with its document id: {identity}"
            )
        return True
