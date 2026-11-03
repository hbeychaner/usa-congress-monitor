from pathlib import Path

import pytest
from pydantic import ValidationError

from cdm.graph.repair import FileSeal, RecordId, RepairBundle, StoredDocument


@pytest.mark.parametrize(
    "name", ["../outside", "/absolute", "sub/file", "sub\\file", ".", "..", ""]
)
def test_manifest_rejects_non_basename_artifacts(name: str) -> None:
    with pytest.raises(ValidationError):
        FileSeal(name=name, sha256="0" * 64, size=0)


def test_duplicate_ids_and_inconsistent_source_identity_fail() -> None:
    doc = StoredDocument(
        id=RecordId("row"), source={"id": "row"}, seq_no=0, primary_term=1
    )
    with pytest.raises(ValueError, match="Duplicate"):
        RepairBundle.unique([doc, doc])
    with pytest.raises(ValueError, match="inconsistent"):
        RepairBundle.unique([doc.model_copy(update={"source": {"id": "other"}})])
    with pytest.raises(ValueError, match="capture bound"):
        RepairBundle.unique([doc], limit=0)


def test_symlink_evidence_rejected(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_text("source")
    linked = tmp_path / "linked"
    linked.symlink_to(original)
    with pytest.raises(ValueError, match="unsafe evidence"):
        FileSeal.read(linked)
