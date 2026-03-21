import json
import pathlib
import pytest

from scripts.ingest import fetch_and_save_all


def test_ingest_outputs_have_ids(tmp_path):
    outdir = tmp_path / "bills_out"
    # Run ingest function with small limits to avoid long external runs
    fetch_and_save_all(
        outdir=outdir,
        resource="bill",
        fetch_items=True,
        max_items=5,
        max_pages=1,
        congress=110,
    )

    listf = outdir / "list.json"
    itemsf = outdir / "items.json"

    assert listf.exists(), f"Missing list file: {listf}"
    assert itemsf.exists(), f"Missing items file: {itemsf}"

    l = json.loads(listf.read_text(encoding="utf-8"))
    it = json.loads(itemsf.read_text(encoding="utf-8"))

    assert isinstance(l, list)
    assert isinstance(it, list)
    assert len(l) > 0
    assert len(it) > 0

    missing = []
    for idx, rec in enumerate(l, start=1):
        if not rec.get("id"):
            missing.append(("list", idx, rec))

    for idx, rec in enumerate(it, start=1):
        if not rec.get("id"):
            missing.append(("items", idx, rec))

    if missing:
        details = "\n".join(f"{t} entry #{i}: {r}" for t, i, r in missing[:10])
        pytest.fail(f"Found records missing 'id' fields:\n{details}")
