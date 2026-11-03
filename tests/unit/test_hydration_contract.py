from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from pydantic import ValidationError

from cdm.backend.services.bill_service import BillService
from cdm.config.source_policy import SourceName
from cdm.contracts.hydration import (
    BillDetailFetcher,
    BillDetailKind,
    DetailEvidence,
    DetailResult,
    DetailState,
    HydrationAssessment,
    HydrationStatus,
)
from cdm.data_collection.client import CDGClient
from cdm.data_collection.specs.bill_specs import BILL_ITEM_SPEC
from cdm.ingest.runner import IngestRunner, Resource
from cdm.models.bills import Bill, BillMetadata
from cdm.models.people import Member, Sponsor
from cdm.store.index_manager import load_definitions
from cdm.store.indexer import to_document
from cdm.utils.json_types import JsonObject


class HydrationFixture:
    @staticmethod
    def bill() -> Bill:
        return Bill.model_validate(
            {
                "congress": 119,
                "number": "1",
                "title": "Title",
                "type": "HR",
                "originChamber": "House",
                "originChamberCode": "H",
                "updateDate": "2026-01-01T00:00:00Z",
                "updateDateIncludingText": "2026-01-01T00:00:00Z",
            }
        )

    @staticmethod
    def client(overrides: dict[BillDetailKind, JsonObject] | None = None) -> Mock:
        client = Mock(spec=CDGClient)
        responses: dict[str, JsonObject] = {
            f"bill/119/hr/1/{kind.endpoint}": {
                kind.value: {"legislativeSubjects": []}
                if kind is BillDetailKind.SUBJECTS
                else []
            }
            for kind in BillDetailKind
        }
        for kind, response in (overrides or {}).items():
            responses[f"bill/119/hr/1/{kind.endpoint}"] = response
        client.get_json.side_effect = responses.__getitem__
        return client

    @staticmethod
    def fetch(
        response: JsonObject, kind: BillDetailKind = BillDetailKind.ACTIONS
    ) -> DetailResult:
        client = Mock(spec=CDGClient)
        client.get_json.return_value = response
        return BillDetailFetcher(client, 2).fetch("endpoint", kind)


class TestDetailRetrieval:
    @pytest.mark.parametrize(
        "subjects",
        [
            {"legislativeSubjects": []},
            {
                "legislativeSubjects": [{"name": "Health"}],
                "policyArea": {"name": "Health"},
            },
        ],
    )
    def test_subject_object_is_expanded_evidence(self, subjects: JsonObject) -> None:
        result = HydrationFixture.fetch({"subjects": subjects}, BillDetailKind.SUBJECTS)
        assert result.evidence.complete
        assert result.evidence.state is DetailState.OBJECT
        assert result.data == subjects

    def test_paginated_subjects_are_combined(self) -> None:
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {
                "subjects": {"legislativeSubjects": [{"name": "A"}]},
                "pagination": {"total": 2, "next": "second"},
            },
            {
                "subjects": {"legislativeSubjects": [{"name": "B"}]},
                "pagination": {"total": 2},
            },
        ]
        result = BillDetailFetcher(client, 2).fetch("first", BillDetailKind.SUBJECTS)
        assert result.data == {"legislativeSubjects": [{"name": "A"}, {"name": "B"}]}
        assert result.evidence.complete
        assert result.evidence.page_count == 2

    @pytest.mark.parametrize("subjects", [{}, {"policyArea": {"name": "Health"}}])
    def test_missing_subjects_list_is_not_explicit_empty(
        self, subjects: JsonObject
    ) -> None:
        result = HydrationFixture.fetch({"subjects": subjects}, BillDetailKind.SUBJECTS)
        assert not result.evidence.complete

    def test_partial_subject_pages_retain_the_records_that_were_received(self) -> None:
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {
                "subjects": {"legislativeSubjects": [{"name": "A"}]},
                "pagination": {"next": "second"},
            },
            {"subjects": {"policyArea": {"name": "Health"}}},
        ]
        result = BillDetailFetcher(client, 2).fetch("first", BillDetailKind.SUBJECTS)
        assert not result.evidence.complete
        assert result.data == {
            "legislativeSubjects": [{"name": "A"}],
            "policyArea": {"name": "Health"},
        }

    @pytest.mark.parametrize("count,complete", [(0, True), (2, False)])
    def test_count_url_requires_expansion_except_authoritative_zero(
        self, count: int, complete: bool
    ) -> None:
        result = HydrationFixture.fetch(
            {"actions": {"count": count, "url": "endpoint"}}
        )
        assert result.evidence.complete is complete
        assert result.evidence.expected_count == count

    @pytest.mark.parametrize(
        "rows",
        [
            [{"id": "a"}],
            [{"id": "a"}, {"id": "a"}],
            [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        ],
    )
    def test_count_mismatch_or_duplicates_do_not_certify_completeness(
        self, rows: list[JsonObject]
    ) -> None:
        result = HydrationFixture.fetch({"actions": rows, "pagination": {"total": 2}})
        assert not result.evidence.complete

    @pytest.mark.parametrize(
        "response",
        [
            {},
            {"actions": None},
            {"actions": [1]},
            {"actions": "invalid"},
            {"actions": [], "pagination": []},
            {"actions": [], "pagination": {"total": True}},
            {"actions": [], "pagination": {"total": -1}},
            {"actions": [], "pagination": {"next": ""}},
            {"actions": {"count": True, "url": "endpoint"}},
        ],
    )
    def test_invalid_shapes_fail_explicitly(self, response: JsonObject) -> None:
        with pytest.raises((ValueError, ValidationError)):
            HydrationFixture.fetch(response)

    def test_duplicate_identity_with_different_values_fails(self) -> None:
        with pytest.raises(RuntimeError, match="identity"):
            HydrationFixture.fetch(
                {"actions": [{"id": "a", "text": "old"}, {"id": "a", "text": "new"}]}
            )

    @pytest.mark.parametrize("mode", ["loop", "limit", "changing_count"])
    def test_incomplete_pagination_fails(self, mode: str) -> None:
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {
                "actions": [],
                "pagination": {
                    "total": 1,
                    "next": "first" if mode == "loop" else "second",
                },
            },
            {
                "actions": [],
                "pagination": {
                    "total": 2 if mode == "changing_count" else 1,
                    "next": "third",
                },
            },
        ]
        with pytest.raises(RuntimeError):
            BillDetailFetcher(client, 2).fetch("first", BillDetailKind.ACTIONS)


class TestHydrationAssessment:
    @pytest.mark.parametrize("model", [Member, Sponsor])
    @pytest.mark.parametrize("direct_name", [None, "Alternate display name"])
    def test_member_alias_roundtrip_preserves_authoritative_name(
        self, model: type[Member], direct_name: str | None
    ) -> None:
        member = model.model_validate(
            {
                "bioguideId": "T000001",
                "firstName": "Test",
                "lastName": "Member",
                "fullName": "Test Member",
                "directOrderName": direct_name,
                "invertedOrderName": None,
                "state": "CA",
            }
        )
        restored = model.model_validate(member.model_dump(mode="json", by_alias=True))
        assert restored.full_name == member.full_name == "Test Member"
        assert restored == member
        assert member.model_dump(mode="json")["full_name"] == "Test Member"

    def test_hydration_preserves_sponsor_with_null_alternate_names(self) -> None:
        bill = Bill.model_validate(
            {
                **HydrationFixture.bill().model_dump(mode="json", by_alias=True),
                "sponsors": [
                    {
                        "bioguideId": "T000001",
                        "firstName": "Test",
                        "lastName": "Member",
                        "fullName": "Test Member",
                        "directOrderName": None,
                        "invertedOrderName": None,
                        "state": "CA",
                    }
                ],
            }
        )
        bill.add_bill_details(HydrationFixture.client())
        assert bill.hydration_assessment.status is HydrationStatus.COMPLETE
        assert isinstance(bill.sponsors, list)
        assert bill.sponsors[0].full_name == "Test Member"

    def test_bill_assessment_uses_all_required_details(self) -> None:
        bill = HydrationFixture.bill()
        bill.add_bill_details(HydrationFixture.client())
        assert bill.hydration_assessment.status is HydrationStatus.COMPLETE
        assert bill.detail_hydration[BillDetailKind.SUBJECTS].complete
        assert bill.subjects is not None
        assert set(bill.hydration_assessment.details) == set(BillDetailKind)

    def test_unexpanded_detail_makes_overall_assessment_partial(self) -> None:
        bill = HydrationFixture.bill()
        bill.add_bill_details(
            HydrationFixture.client(
                {
                    BillDetailKind.RELATED_BILLS: {
                        "relatedBills": {
                            "count": 2,
                            "url": "https://example.invalid/related",
                        }
                    }
                }
            )
        )
        assert bill.hydration_assessment.status is HydrationStatus.PARTIAL
        assert bill.related_bills is not None

    def test_failed_late_response_does_not_partially_mutate_bill(self) -> None:
        bill = HydrationFixture.bill()
        before = bill.model_dump(mode="json")
        with pytest.raises(ValueError):
            bill.add_bill_details(HydrationFixture.client({BillDetailKind.TITLES: {}}))
        assert bill.model_dump(mode="json") == before

    def test_partial_subject_object_does_not_erase_existing_subjects(self) -> None:
        bill = HydrationFixture.bill()
        bill.add_bill_details(
            HydrationFixture.client(
                {
                    BillDetailKind.SUBJECTS: {
                        "subjects": {"legislativeSubjects": [{"name": "Existing"}]}
                    }
                }
            )
        )
        bill.add_bill_details(
            HydrationFixture.client(
                {
                    BillDetailKind.SUBJECTS: {
                        "subjects": {"policyArea": {"name": "Health"}}
                    }
                }
            )
        )
        assert bill.hydration_assessment.status is HydrationStatus.PARTIAL
        assert bill.subjects is not None
        assert bill.subjects.model_dump(mode="json")["legislative_subjects"] == [
            {"name": "Existing", "update_date": None}
        ]

    def test_http_error_is_not_indexed_as_full_text(self) -> None:
        bill = HydrationFixture.bill()
        client = HydrationFixture.client(
            {
                BillDetailKind.TEXT_VERSIONS: {
                    "textVersions": [
                        {
                            "type": "Introduced",
                            "date": None,
                            "formats": [
                                {
                                    "type": "Formatted Text",
                                    "url": "https://example.invalid/text",
                                }
                            ],
                        }
                    ]
                }
            }
        )
        client.session = Mock()
        response = requests.Response()
        response.status_code = 404
        response._content = b"Not found"
        client.session.get.return_value = response
        with pytest.raises(RuntimeError, match="Network error"):
            bill.add_bill_details(client)
        assert bill.full_text == ""
        assert bill.hydration_assessment.status is HydrationStatus.UNKNOWN

    @pytest.mark.parametrize("legacy_status", [None, "complete"])
    def test_legacy_or_unassessed_record_is_unknown(
        self, legacy_status: str | None
    ) -> None:
        record: JsonObject = {"hydration_status": legacy_status}
        assert HydrationAssessment.from_record(record).status is HydrationStatus.UNKNOWN

    def test_complete_claim_without_required_evidence_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HydrationAssessment(
                status=HydrationStatus.COMPLETE,
                source=SourceName.CONGRESS,
                assessed_at=datetime.now(UTC),
            )

    def test_invalid_complete_evidence_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DetailEvidence(
                page_count=1,
                expected_count=2,
                fetched_count=1,
                state=DetailState.EXPANDED,
                complete=True,
                reason="Invalid count",
            )

    def test_indexing_does_not_invent_complete_from_legacy_label(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("cdm.store.indexer._apply_lemmas", Mock())
        document = to_document(
            {"id": "bill:119:hr:1", "hydration_status": "complete"}, "bill"
        )
        assert document["hydration_status"] == "unknown"
        assert (
            HydrationAssessment.from_record(document).status is HydrationStatus.UNKNOWN
        )

    def test_versioned_assessment_is_explicit_source_only_provenance(self) -> None:
        properties = load_definitions()["legislation"]["mappings"]["properties"]
        assert properties["hydration_assessment"] == {
            "type": "object",
            "enabled": False,
        }
        assert properties["hydration_status"] == {"type": "keyword"}

    def test_ingest_runner_uses_partial_evidence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = HydrationFixture.client(
            {
                BillDetailKind.RELATED_BILLS: {
                    "relatedBills": {
                        "count": 2,
                        "url": "https://example.invalid/related",
                    }
                }
            }
        )
        client.fetch_one.return_value = HydrationFixture.bill()
        client.resolve_runtime_params_from_record.return_value = {}
        runner = IngestRunner(outdir=tmp_path, resource=Resource.BILL)
        monkeypatch.setattr(runner, "_client", lambda: client)
        result = runner._fetch_single_item(
            BillMetadata.model_validate(
                {
                    "congress": 119,
                    "type": "HR",
                    "number": "1",
                    "title": "Title",
                    "url": "https://api.congress.gov/v3/bill/119/hr/1",
                }
            ),
            BILL_ITEM_SPEC,
            tmp_path,
        )
        assert result["hydration_status"] == "partial"
        assert HydrationAssessment.from_record(result).status is HydrationStatus.PARTIAL


class TestHydrationReadBoundary:
    @pytest.mark.parametrize("claimed", [None, "complete"])
    def test_old_labels_do_not_make_bill_detail_complete(
        self, claimed: str | None
    ) -> None:
        client = Mock()
        client.get.return_value = {
            "_source": {
                "id": "bill:119:hr:1",
                "source_type": "bill",
                "title": "Title",
                "hydration_status": claimed,
            }
        }
        result = BillService(client, Mock()).get("bill:119:hr:1")
        assert result.bill.hydration.status is HydrationStatus.UNKNOWN
        assert result.bill.title == "Title"

    def test_corrupt_assessment_is_not_a_success_shaped_unknown(self) -> None:
        client = Mock()
        client.get.return_value = {
            "_source": {
                "id": "bill:119:hr:1",
                "source_type": "bill",
                "hydration_assessment": {"schema_version": 2},
            }
        }
        with pytest.raises(ValidationError):
            BillService(client, Mock()).get("bill:119:hr:1")
