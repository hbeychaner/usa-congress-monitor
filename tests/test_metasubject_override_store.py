from __future__ import annotations

from typing import Any

from cdm.store.metasubject_override_store import MetasubjectOverrideStore


class _Indices:
    def __init__(self, owner: _FakeClient) -> None:
        self.owner = owner

    def exists(self, index: str) -> bool:
        return self.owner.created

    def create(self, index: str, mappings: dict[str, Any]) -> None:
        self.owner.created = True


class _FakeClient:
    def __init__(self) -> None:
        self.created = False
        self.docs: dict[str, dict[str, Any]] = {}
        self.indices = _Indices(self)

    def index(self, index: str, id: str, document: dict[str, Any], **_: Any) -> None:
        assert id not in self.docs
        self.docs[id] = document

    def search(self, index: str, size: int, query: dict[str, Any]) -> dict[str, Any]:
        wanted = query.get("term", {}).get("metasubject_id")
        hits = [
            {"_source": doc}
            for doc in self.docs.values()
            if wanted is None or doc["metasubject_id"] == wanted
        ]
        return {"hits": {"hits": hits}}


def _store() -> MetasubjectOverrideStore:
    return MetasubjectOverrideStore(_FakeClient(), index="overrides")


def test_latest_version_wins_and_history_is_kept() -> None:
    store = _store()
    store.set_name(3, "Health")
    store.set_name(3, "Health Care")
    store.set_name(5, "Taxes")
    assert store.current().names == {3: "Health Care", 5: "Taxes"}
    assert [v.version for v in store.history(3)] == [1, 2]


def test_clear_removes_override_without_deleting_history() -> None:
    store = _store()
    store.set_name(3, "Health")
    store.clear(3)
    assert store.current().names == {}
    assert len(store.history(3)) == 2


def test_missing_index_yields_no_overrides() -> None:
    assert _store().current().names == {}
