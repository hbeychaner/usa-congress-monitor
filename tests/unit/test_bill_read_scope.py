from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from elasticsearch import Elasticsearch

from cdm.backend.errors import EntityNotFoundError
from cdm.backend.services.bill_service import BillService
from cdm.backend.services.bill_vote_index import BillVoteIndex
from cdm.backend.services.search_service import SearchService
from cdm.store.bill_scope import BillReadScope
from cdm.store.client import IncompleteSearchError
from cdm.store.create_only import BillSourceIdentity
from cdm.utils.json_types import JsonObject


@pytest.fixture
def law() -> JsonObject:
    return {
        "id": "bill:119:hr:187",
        "source_type": "law",
        "congress": 119,
        "type": "HR",
        "number": "187",
        "title": "Enacted measure",
        "full_text": "Preserved enacted text",
    }


def test_law_projection_reads_as_bill_without_reclassification(law: JsonObject) -> None:
    before = deepcopy(law)
    client = Mock(spec=Elasticsearch)
    client.get.return_value = {"_source": law}
    result = BillService(client, Mock(spec=BillVoteIndex)).get("bill:119:hr:187")
    assert result.bill.bill_id == "bill:119:hr:187"
    assert result.bill.full_text == "Preserved enacted text"
    assert law == before
    client.index.assert_not_called()
    with pytest.raises(ValueError):
        BillSourceIdentity.model_validate(law)


@pytest.mark.parametrize("kind", ["amendment", "person", "unknown"])
def test_non_bill_classifications_remain_excluded(law: JsonObject, kind: str) -> None:
    law["source_type"] = kind
    client = Mock(spec=Elasticsearch)
    client.get.return_value = {"_source": law}
    with pytest.raises(EntityNotFoundError):
        BillService(client, Mock(spec=BillVoteIndex)).get("bill:119:hr:187")


@pytest.mark.parametrize("field,value", [("congress", 118), ("number", 188), ("id", "bill:119:hr:188")])
def test_inconsistent_law_identity_is_an_explicit_read_error(
    law: JsonObject, field: str, value: int | str
) -> None:
    law[field] = value
    with pytest.raises(IncompleteSearchError, match="identity"):
        BillReadScope.contains(law, "bill:119:hr:187")


def test_independent_law_identity_does_not_become_a_bill(law: JsonObject) -> None:
    law["id"] = "law:119:public:1"
    assert not BillReadScope.contains(law, "law:119:public:1")


def test_scope_filters_both_projections_by_bill_namespace() -> None:
    assert BillReadScope.query() == {
        "bool": {
            "filter": [
                {"terms": {"source_type": ["bill", "law"]}},
                {"prefix": {"id": "bill:"}},
            ]
        }
    }


def test_exact_bill_identity_queries_never_load_the_nlp_model() -> None:
    with (
        patch("cdm.backend.services.bill_service.try_lemmatize_query", side_effect=AssertionError),
        patch("cdm.backend.services.search_service.try_lemmatize_query", side_effect=AssertionError),
    ):
        assert BillService._text_query("BILL:119:HR:187") == {
            "term": {"id": "bill:119:hr:187"}
        }
        assert SearchService._bill_query("bill:119:hr:187", 10)["size"] == 10
