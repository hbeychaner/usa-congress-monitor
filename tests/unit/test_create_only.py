from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from elasticsearch import Elasticsearch
from pydantic import BaseModel, ValidationError

from cdm.config.create_only import (
    AliasName,
    CreateOnlySettings,
    CreateOnlyTarget,
    IndexName,
)
from cdm.store.create_only import (
    BillCreation,
    BillCreationError,
    BillCreationStatus,
    CreateOnlyBillWriter,
    SourceDigest,
)
from cdm.utils.json_types import JsonObject


class Response(BaseModel):
    body: JsonObject


class WriterFixture:
    def __init__(self) -> None:
        self.client = MagicMock(spec=Elasticsearch)
        self.client.indices = MagicMock()
        self.client.options.return_value = self.client
        self.target = CreateOnlyTarget(
            cluster_uuid="cluster",
            index_name=IndexName("bills"),
            index_uuid="index-uuid",
            aliases=(AliasName("bills-read"), AliasName("bills-write")),
        )
        self.client.info.return_value = Response(body={"cluster_uuid": "cluster"})
        self.client.indices.get_settings.return_value = Response(
            body={"bills": {"settings": {"index": {"uuid": "index-uuid"}}}}
        )
        self.client.indices.get_alias.return_value = Response(
            body={"bills": {"aliases": {"bills-read": {}, "bills-write": {}}}}
        )
        self.writer = CreateOnlyBillWriter(
            self.client, self.target, CreateOnlySettings(maximum_batch_size=2)
        )

    def document(self, number: int = 1) -> BillCreation:
        identity = f"bill:94:hr:{number}"
        return BillCreation(
            identity=identity,
            source={
                "id": identity,
                "congress": 94,
                "type": "HR",
                "number": str(number),
                "source_type": "bill",
                "title": f"Bill {number}",
            },
        )

    def responses(
        self,
        documents: list[BillCreation],
        statuses: list[int],
        *,
        existing_source: JsonObject | None = None,
    ) -> None:
        items: list[JsonObject] = []
        docs: list[JsonObject] = []
        for document, status in zip(documents, statuses, strict=True):
            item: JsonObject = {
                "_id": document.identity,
                "_index": "bills",
                "status": status,
            }
            if status == 201:
                item.update(result="created", _seq_no=10, _primary_term=1)
            else:
                item["error"] = {
                    "type": (
                        "version_conflict_engine_exception"
                        if status == 409
                        else "mapper_parsing_exception"
                    ),
                    "reason": "test rejection",
                }
            items.append({"create": item})
            if status in (201, 409):
                docs.append(
                    {
                        "_id": document.identity,
                        "_index": "bills",
                        "found": True,
                        "_source": (
                            existing_source
                            if status == 409 and existing_source is not None
                            else document.source
                        ),
                        "_seq_no": 10,
                        "_primary_term": 1,
                    }
                )
        self.client.bulk.return_value = Response(
            body={"errors": any(status != 201 for status in statuses), "items": items}
        )
        self.client.mget.return_value = Response(body={"docs": docs})


class TestCreateOnlyBillWriter:
    def test_creates_with_only_atomic_create_actions_and_exact_readback(self) -> None:
        fixture = WriterFixture()
        document = fixture.document()
        fixture.responses([document], [201])
        result = fixture.writer.create([document])
        assert result.verified[0].status is BillCreationStatus.CREATED
        assert result.verified[0].source_sha256 == SourceDigest.of(document.source)
        assert not result.rejected
        fixture.client.bulk.assert_called_once_with(
            index="bills",
            operations=[{"create": {"_id": document.identity}}, document.source],
        )
        fixture.client.options.assert_called_once_with(
            max_retries=0, retry_on_timeout=False, request_timeout=60
        )

    def test_conflict_preserves_richer_source_and_reports_existing(self) -> None:
        fixture = WriterFixture()
        document = fixture.document()
        richer = document.source | {"full_text": "Retained richer text"}
        before = deepcopy(richer)
        fixture.responses([document], [409], existing_source=richer)
        result = fixture.writer.create([document])
        assert result.verified[0].status is BillCreationStatus.ALREADY_PRESENT
        assert result.verified[0].source_sha256 == SourceDigest.of(richer)
        assert richer == before
        assert fixture.client.bulk.call_args.kwargs["operations"][0] == {
            "create": {"_id": document.identity}
        }

    def test_partial_failure_retains_verified_success_and_rejected_identity(
        self,
    ) -> None:
        fixture = WriterFixture()
        documents = [fixture.document(1), fixture.document(2)]
        fixture.responses(documents, [201, 400])
        with pytest.raises(BillCreationError) as caught:
            fixture.writer.create(documents)
        result = caught.value.result
        assert [item.identity for item in result.verified] == [documents[0].identity]
        assert result.rejected[0].identity == documents[1].identity
        assert result.rejected[0].status_code == 400

    def test_all_rejections_do_not_attempt_a_success_shaped_readback(self) -> None:
        fixture = WriterFixture()
        fixture.responses([fixture.document()], [400])
        with pytest.raises(BillCreationError):
            fixture.writer.create([fixture.document()])
        fixture.client.mget.assert_not_called()

    @pytest.mark.parametrize("count", [0, 3])
    def test_batch_bound_checked_before_any_request(self, count: int) -> None:
        fixture = WriterFixture()
        with pytest.raises(ValueError):
            fixture.writer.create(
                [fixture.document(number + 1) for number in range(count)]
            )
        fixture.client.bulk.assert_not_called()
        fixture.client.info.assert_not_called()

    def test_duplicate_identity_is_rejected_before_submission(self) -> None:
        fixture = WriterFixture()
        document = fixture.document()
        with pytest.raises(ValueError, match="duplicate"):
            fixture.writer.create([document, document])
        fixture.client.bulk.assert_not_called()

    def test_mutated_source_is_revalidated_before_submission(self) -> None:
        fixture = WriterFixture()
        document = fixture.document()
        document.source["congress"] = 95
        with pytest.raises(ValidationError):
            fixture.writer.create([document])
        fixture.client.bulk.assert_not_called()

    @pytest.mark.parametrize(
        "field,value",
        [
            ("id", "bill:94:hr:2"),
            ("congress", 95),
            ("type", "s"),
            ("number", "2"),
            ("source_type", "law"),
        ],
    )
    def test_input_identity_disagreements_are_rejected(
        self, field: str, value: str | int
    ) -> None:
        fixture = WriterFixture()
        source = fixture.document().source | {field: value}
        with pytest.raises(ValidationError):
            BillCreation(identity="bill:94:hr:1", source=source)

    def test_cluster_change_blocks_writes(self) -> None:
        fixture = WriterFixture()
        fixture.client.info.return_value = Response(body={"cluster_uuid": "other"})
        with pytest.raises(RuntimeError, match="cluster"):
            fixture.writer.create([fixture.document()])
        fixture.client.bulk.assert_not_called()

    def test_index_uuid_change_blocks_writes(self) -> None:
        fixture = WriterFixture()
        fixture.client.indices.get_settings.return_value = Response(
            body={"bills": {"settings": {"index": {"uuid": "other"}}}}
        )
        with pytest.raises(RuntimeError, match="UUID"):
            fixture.writer.create([fixture.document()])
        fixture.client.bulk.assert_not_called()

    def test_alias_cannot_be_used_as_the_physical_index(self) -> None:
        fixture = WriterFixture()
        fixture.client.indices.get_settings.return_value = Response(
            body={"actual-bills": {"settings": {"index": {"uuid": "index-uuid"}}}}
        )
        with pytest.raises(RuntimeError, match="physical"):
            fixture.writer.create([fixture.document()])
        fixture.client.bulk.assert_not_called()

    def test_rebound_alias_blocks_writes(self) -> None:
        fixture = WriterFixture()
        fixture.client.indices.get_alias.return_value = Response(
            body={"other": {"aliases": {"bills-read": {}, "bills-write": {}}}}
        )
        with pytest.raises(RuntimeError, match="alias"):
            fixture.writer.create([fixture.document()])
        fixture.client.bulk.assert_not_called()

    def test_transport_ambiguity_is_not_retried_or_reported_as_success(self) -> None:
        fixture = WriterFixture()
        fixture.client.bulk.side_effect = TimeoutError("ambiguous response")
        with pytest.raises(TimeoutError, match="ambiguous"):
            fixture.writer.create([fixture.document()])
        assert fixture.client.bulk.call_count == 1
        fixture.client.mget.assert_not_called()

    def test_conflict_with_incompatible_existing_identity_fails(self) -> None:
        fixture = WriterFixture()
        richer = fixture.document().source | {"congress": 95}
        fixture.responses([fixture.document()], [409], existing_source=richer)
        with pytest.raises(ValidationError, match="disagrees"):
            fixture.writer.create([fixture.document()])

    @pytest.mark.parametrize("changed", ["source", "sequence_number"])
    def test_created_readback_must_match_exact_source_and_version(
        self, changed: str
    ) -> None:
        fixture = WriterFixture()
        document = fixture.document()
        fixture.responses([document], [201])
        source = (
            document.source | {"title": "Changed"}
            if changed == "source"
            else document.source
        )
        fixture.client.mget.return_value = Response(
            body={
                "docs": [
                    {
                        "_index": "bills",
                        "_id": document.identity,
                        "_source": source,
                        "found": True,
                        "_seq_no": 11 if changed == "sequence_number" else 10,
                        "_primary_term": 1,
                    }
                ]
            }
        )
        with pytest.raises(RuntimeError, match="acknowledged"):
            fixture.writer.create([document])

    def test_bulk_response_cannot_omit_an_identity(self) -> None:
        fixture = WriterFixture()
        fixture.responses([], [])
        with pytest.raises(RuntimeError, match="identities/order"):
            fixture.writer.create([fixture.document()])

    def test_missing_readback_fails_instead_of_skipping(self) -> None:
        fixture = WriterFixture()
        fixture.responses([fixture.document()], [201])
        fixture.client.mget.return_value = Response(body={"docs": []})
        with pytest.raises(RuntimeError, match="identities/order"):
            fixture.writer.create([fixture.document()])
