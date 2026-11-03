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
    def test_anonymous_action_rows_retain_duplicate_evidence(self) -> None:
        action: JsonObject = {"actionDate": "1990-09-27", "text": "Passed"}
        other: JsonObject = {"actionDate": "1990-09-28", "text": "Signed"}
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {"actions": [action, action], "pagination": {"count": 3, "next": "second"}},
            {"actions": [other], "pagination": {"count": 3}},
        ]
        result = BillDetailFetcher(client, 2).fetch("first", BillDetailKind.ACTIONS)
        assert result.evidence.complete
        assert result.data == [action, other]
        assert result.evidence.fetched_count == 3
        assert result.evidence.fetched_record_count == 2
        assert len(result.evidence.repeated_actions) == 1
        assert result.evidence.repeated_actions[0].record == action
        assert result.evidence.repeated_actions[0].occurrences == 2
        assert result.evidence.page_count == 2

    @pytest.mark.parametrize("expected", [1, 3])
    def test_anonymous_action_duplicates_do_not_waive_raw_count_mismatch(
        self, expected: int
    ) -> None:
        action: JsonObject = {"text": "Passed"}
        result = HydrationFixture.fetch(
            {"actions": [action, action], "pagination": {"count": expected}}
        )
        assert not result.evidence.complete
        assert result.evidence.fetched_count == 2

    def test_anonymous_action_duplicates_without_count_retain_multiplicity(
        self,
    ) -> None:
        action: JsonObject = {"text": "Passed"}
        result = HydrationFixture.fetch({"actions": [action, action]})
        assert result.evidence.complete
        assert result.evidence.fetched_count == 2
        assert result.evidence.fetched_record_count == 1
        assert result.evidence.repeated_actions[0].occurrences == 2

    def test_explicit_action_identity_conflict_still_fails(self) -> None:
        with pytest.raises(RuntimeError, match="Conflicting"):
            HydrationFixture.fetch(
                {
                    "actions": [
                        {"id": "a", "text": "Passed"},
                        {"id": "a", "text": "Failed"},
                    ]
                }
            )

    def test_other_anonymous_collections_still_require_distinct_counts(self) -> None:
        result = HydrationFixture.fetch(
            {
                "titles": [{"title": "Same"}, {"title": "Same"}],
                "pagination": {"count": 2},
            },
            BillDetailKind.TITLES,
        )
        assert not result.evidence.complete

    def test_action_counts_match_the_historical_35_row_31_body_shape(self) -> None:
        distinct: list[JsonObject] = [
            {"actionDate": "1990-09-27", "text": f"Action {number}"}
            for number in range(31)
        ]
        rows = distinct[:4] + distinct
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {"actions": rows[:20], "pagination": {"count": 35, "next": "second"}},
            {"actions": rows[20:], "pagination": {"count": 35}},
        ]
        result = BillDetailFetcher(client, 2).fetch("first", BillDetailKind.ACTIONS)
        evidence = result.evidence
        assert evidence.complete
        assert evidence.expected_count == evidence.fetched_count == 35
        assert evidence.fetched_record_count == len(result.data) == 31
        assert len(evidence.repeated_actions) == 4
        assert all(action.occurrences == 2 for action in evidence.repeated_actions)
        assert (
            DetailEvidence.model_validate_json(evidence.model_dump_json()) == evidence
        )
        malformed = evidence.model_dump()
        malformed["fetched_record_count"] = 32
        with pytest.raises(ValidationError, match="reconcile"):
            DetailEvidence.model_validate(malformed)

    def test_related_bill_count_measures_relationships_not_bill_objects(self) -> None:
        record: JsonObject = {
            "url": "related-bill",
            "relationshipDetails": [
                {"identifiedBy": "CRS", "type": "Identical bill"},
                {"identifiedBy": "Senate", "type": "Procedurally related"},
            ],
        }
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {"relatedBills": [record], "pagination": {"count": 2, "next": "page2"}},
            {"relatedBills": [record], "pagination": {"count": 2}},
        ]
        result = BillDetailFetcher(client, 2).fetch(
            "endpoint", BillDetailKind.RELATED_BILLS
        )
        assert result.data == [record]
        assert result.evidence.complete
        assert result.evidence.page_count == 2
        assert result.evidence.expected_count == result.evidence.fetched_count == 2
        assert result.evidence.fetched_record_count == 1

    def test_duplicate_relationships_do_not_satisfy_source_count(self) -> None:
        relationship: JsonObject = {"identifiedBy": "CRS", "type": "Identical bill"}
        result = HydrationFixture.fetch(
            {
                "relatedBills": [
                    {
                        "url": "related-bill",
                        "relationshipDetails": [relationship, relationship],
                    }
                ],
                "pagination": {"count": 2},
            },
            BillDetailKind.RELATED_BILLS,
        )
        assert not result.evidence.complete
        assert result.evidence.fetched_count == 1

    @pytest.mark.parametrize(
        "record",
        [{"url": "related-bill"}, {"url": "related-bill", "relationshipDetails": None}],
    )
    def test_missing_relationship_collection_is_not_complete(
        self, record: JsonObject
    ) -> None:
        result = HydrationFixture.fetch(
            {"relatedBills": [record], "pagination": {"count": 1}},
            BillDetailKind.RELATED_BILLS,
        )
        assert not result.evidence.complete
        assert result.evidence.fetched_count == 0
        assert result.evidence.fetched_record_count == 1

    def test_conflicting_related_bill_metadata_still_fails(self) -> None:
        with pytest.raises(RuntimeError, match="Conflicting"):
            HydrationFixture.fetch(
                {
                    "relatedBills": [
                        {
                            "url": "same-bill",
                            "title": "Original",
                            "relationshipDetails": [],
                        },
                        {
                            "url": "same-bill",
                            "title": "Changed",
                            "relationshipDetails": [],
                        },
                    ]
                },
                BillDetailKind.RELATED_BILLS,
            )

    @pytest.mark.parametrize("identity_field", ["url", "id"])
    def test_cosponsor_identity_includes_its_sponsorship_episode(
        self, identity_field: str
    ) -> None:
        records: list[JsonObject] = [
            {
                identity_field: "member-identity",
                "sponsorshipDate": "1993-02-03",
                "sponsorshipWithdrawnDate": "1993-02-03",
            },
            {
                identity_field: "member-identity",
                "sponsorshipDate": "1993-06-07",
                "sponsorshipWithdrawnDate": None,
            },
        ]
        result = HydrationFixture.fetch(
            {
                "cosponsors": records,
                "pagination": {"count": 1, "countIncludingWithdrawnCosponsors": 2},
            },
            BillDetailKind.COSPONSORS,
        )
        assert result.data == records
        assert result.evidence.complete
        assert result.evidence.expected_count == result.evidence.fetched_count == 2
        assert result.evidence.expected_active_count == 1
        assert result.evidence.fetched_active_count == 1

    def test_same_cosponsor_episode_with_conflicting_withdrawal_still_fails(
        self,
    ) -> None:
        with pytest.raises(RuntimeError, match="Conflicting"):
            HydrationFixture.fetch(
                {
                    "cosponsors": [
                        {
                            "url": "member",
                            "sponsorshipDate": "1993-02-03",
                            "sponsorshipWithdrawnDate": None,
                        },
                        {
                            "url": "member",
                            "sponsorshipDate": "1993-02-03",
                            "sponsorshipWithdrawnDate": "1993-02-04",
                        },
                    ]
                },
                BillDetailKind.COSPONSORS,
            )

    def test_active_cosponsor_count_mismatch_cannot_certify_complete(self) -> None:
        result = HydrationFixture.fetch(
            {
                "cosponsors": [
                    {"url": "member-a", "sponsorshipDate": "1993-02-03"},
                    {"url": "member-b", "sponsorshipDate": "1993-06-07"},
                ],
                "pagination": {"count": 1, "countIncludingWithdrawnCosponsors": 2},
            },
            BillDetailKind.COSPONSORS,
        )
        assert not result.evidence.complete
        assert result.evidence.fetched_count == result.evidence.expected_count == 2

    @pytest.mark.parametrize("count_field", ["count", "total"])
    def test_real_source_count_alias_prevents_false_completeness(
        self, count_field: str
    ) -> None:
        result = HydrationFixture.fetch(
            {"actions": [{"id": "one"}], "pagination": {count_field: 2}}
        )
        assert result.evidence.expected_count == 2
        assert not result.evidence.complete

    def test_real_source_count_must_not_change_between_pages(self) -> None:
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {"actions": [{"id": "one"}], "pagination": {"count": 2, "next": "second"}},
            {"actions": [{"id": "two"}], "pagination": {"count": 3}},
        ]
        with pytest.raises(RuntimeError, match="count changed"):
            BillDetailFetcher(client, 2).fetch("first", BillDetailKind.ACTIONS)

    def test_conflicting_generic_count_aliases_fail(self) -> None:
        with pytest.raises(ValueError, match="count"):
            HydrationFixture.fetch(
                {"actions": [], "pagination": {"count": 0, "total": 1}}
            )

    @pytest.mark.parametrize(
        "pagination",
        [
            {"count": 2, "countIncludingWithdrawnCosponsors": 1},
            {"total": 1, "countIncludingWithdrawnCosponsors": 2},
            {"count": True},
        ],
    )
    def test_inconsistent_cosponsor_counts_fail(self, pagination: JsonObject) -> None:
        with pytest.raises(ValueError):
            HydrationFixture.fetch(
                {"cosponsors": [], "pagination": pagination},
                BillDetailKind.COSPONSORS,
            )

    def test_active_cosponsor_count_must_not_change_between_pages(self) -> None:
        client = Mock(spec=CDGClient)
        client.get_json.side_effect = [
            {
                "cosponsors": [],
                "pagination": {
                    "count": 1,
                    "countIncludingWithdrawnCosponsors": 2,
                    "next": "second",
                },
            },
            {
                "cosponsors": [],
                "pagination": {"count": 2, "countIncludingWithdrawnCosponsors": 2},
            },
        ]
        with pytest.raises(RuntimeError, match="count changed"):
            BillDetailFetcher(client, 2).fetch("first", BillDetailKind.COSPONSORS)

    @pytest.mark.parametrize("repeat_policy", [False, True])
    def test_subject_count_includes_policy_area_once(self, repeat_policy: bool) -> None:
        client = Mock(spec=CDGClient)
        policy: JsonObject = {"name": "Health"}
        client.get_json.side_effect = [
            {
                "subjects": {
                    "legislativeSubjects": [{"name": "First"}],
                    "policyArea": policy,
                },
                "pagination": {"count": 3, "next": "second"},
            },
            {
                "subjects": {
                    "legislativeSubjects": [{"name": "Second"}],
                    **({"policyArea": policy} if repeat_policy else {}),
                },
                "pagination": {"count": 3},
            },
        ]
        result = BillDetailFetcher(client, 2).fetch("first", BillDetailKind.SUBJECTS)
        assert result.evidence.complete
        assert result.evidence.fetched_count == result.evidence.expected_count == 3
        assert result.data == {
            "legislativeSubjects": [{"name": "First"}, {"name": "Second"}],
            "policyArea": policy,
        }

    @pytest.mark.parametrize("policy", [None, {}])
    def test_empty_policy_placeholder_does_not_satisfy_source_count(
        self, policy: JsonObject | None
    ) -> None:
        result = HydrationFixture.fetch(
            {
                "subjects": {"legislativeSubjects": [], "policyArea": policy},
                "pagination": {"count": 1},
            },
            BillDetailKind.SUBJECTS,
        )
        assert not result.evidence.complete
        assert result.evidence.fetched_count == 0

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
    def test_hydration_preserves_withdrawn_and_rejoined_cosponsor(self) -> None:
        person: JsonObject = {
            "bioguideId": "T000001",
            "firstName": "Test",
            "lastName": "Member",
            "fullName": "Test Member",
            "state": "CA",
            "url": "https://api.congress.gov/v3/member/T000001",
        }
        bill = HydrationFixture.bill()
        bill.add_bill_details(
            HydrationFixture.client(
                {
                    BillDetailKind.COSPONSORS: {
                        "cosponsors": [
                            {
                                **person,
                                "sponsorshipDate": "1993-02-03",
                                "sponsorshipWithdrawnDate": "1993-02-03",
                            },
                            {
                                **person,
                                "sponsorshipDate": "1993-06-07",
                                "sponsorshipWithdrawnDate": None,
                            },
                        ],
                        "pagination": {
                            "count": 1,
                            "countIncludingWithdrawnCosponsors": 2,
                        },
                    }
                }
            )
        )
        assert bill.hydration_assessment.status is HydrationStatus.COMPLETE
        assert isinstance(bill.cosponsors, list)
        assert len(bill.cosponsors) == 2
        assert bill.cosponsors[0].sponsorship_withrawn_date is not None
        assert bill.cosponsors[1].sponsorship_withrawn_date is None

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

    @pytest.mark.parametrize(
        ("expected_active", "fetched_active", "complete"),
        [(3, 1, False), (1, 3, False), (1, 2, True), (1, None, True)],
    )
    def test_invalid_active_evidence_is_rejected(
        self,
        expected_active: int,
        fetched_active: int | None,
        complete: bool,
    ) -> None:
        with pytest.raises(ValidationError):
            DetailEvidence(
                page_count=1,
                expected_count=2,
                fetched_count=2,
                expected_active_count=expected_active,
                fetched_active_count=fetched_active,
                state=DetailState.EXPANDED,
                complete=complete,
                reason="Contradictory active count",
            )

    def test_evidence_without_active_counts_remains_readable(self) -> None:
        evidence = DetailEvidence.model_validate_json(
            '{"page_count":1,"expected_count":2,"fetched_count":2,'
            '"state":"expanded","complete":true,"reason":"Legacy evidence"}'
        )
        assert evidence.complete
        assert evidence.fetched_record_count is None
        assert evidence.expected_active_count is None
        assert evidence.fetched_active_count is None

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
