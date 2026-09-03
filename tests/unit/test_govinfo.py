import hashlib
import zipfile
from typing import Any

import pytest
import requests

from cdm.ingest.govinfo import (
    GovInfoBillsParser,
    GovInfoBillStatusParser,
    GovInfoBillSummaryParser,
    GovInfoDiscovery,
    GovInfoDownloader,
    GovInfoDownloadError,
    GovInfoManifestStore,
    GovInfoPackage,
    GovInfoParseError,
    summarize_govinfo_coverage,
)


class StubResponse:
    def __init__(
        self,
        content: bytes = b"",
        status_code: int = 200,
        json_payload: Any | None = None,
    ):
        self.content = content
        self.status_code = status_code
        self.json_payload = json_payload
        self.headers = {
            "ETag": '"test-etag"',
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        }

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        del chunk_size
        yield self.content

    def json(self):
        if self.json_payload is not None:
            return self.json_payload
        raise ValueError("no JSON payload")


class StubSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def package():
    return GovInfoPackage(
        package_id="BILLSTATUS-118hr1",
        collection="BILLSTATUS",
        congress=118,
        measure_type="hr",
        url="https://www.govinfo.gov/bulkdata/BILLSTATUS/118/hr/BILLSTATUS-118hr1.xml",
    )


def test_download_writes_artifact_and_manifest(tmp_path):
    session = StubSession(StubResponse(b"<billstatus />"))
    path = GovInfoDownloader(tmp_path, session=session).download(package())

    assert path.read_bytes() == b"<billstatus />"
    manifest = (tmp_path / "manifest.json").read_text()
    assert '"status": "complete"' in manifest
    assert hashlib.sha256(path.read_bytes()).hexdigest() in manifest
    assert not list(tmp_path.rglob("*.part"))


def test_download_reuses_verified_artifact_without_request(tmp_path):
    session = StubSession(StubResponse(b"<billstatus />"))
    downloader = GovInfoDownloader(tmp_path, session=session)
    first = downloader.download(package())
    second = downloader.download(package())

    assert second == first
    assert len(session.calls) == 1


def test_download_accepts_not_modified_response(tmp_path):
    downloader = GovInfoDownloader(
        tmp_path,
        session=StubSession(StubResponse(b"<billstatus />")),
    )
    expected = downloader.download(package())
    session = StubSession(StubResponse(status_code=304))
    resumed = GovInfoDownloader(tmp_path, session=session).download(
        package(), force=True
    )

    assert resumed == expected
    assert resumed.read_bytes() == b"<billstatus />"
    assert session.calls[0][1]["headers"]["If-None-Match"] == '"test-etag"'


def test_download_records_failure_and_removes_partial_artifact(tmp_path):
    session = StubSession(StubResponse(status_code=500))

    with pytest.raises(GovInfoDownloadError, match="BILLSTATUS-118hr1"):
        GovInfoDownloader(tmp_path, session=session).download(package())

    assert not list(tmp_path.rglob("*.part"))
    assert '"status": "failed"' in (tmp_path / "manifest.json").read_text()


def test_discovery_builds_measure_and_text_package_urls():
    discovery = GovInfoDiscovery()

    status = discovery.measure_package("billstatus", 118, "hr", 1)
    text = discovery.text_package(118, 1, "hr", 1, "ih")

    assert status.package_id == "BILLSTATUS-118hr1"
    assert status.url.endswith("/BILLSTATUS/118/hr/BILLSTATUS-118hr1.xml")
    assert text.package_id == "BILLS-118hr1ih"
    assert text.url.endswith("/BILLS/118/1/hr/BILLS-118hr1ih.xml")
    assert text.session == 1
    assert text.version_code == "ih"


@pytest.mark.parametrize(
    "measure_type", ["hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"]
)
def test_discovery_builds_supported_measure_package_ids(measure_type):
    package = GovInfoDiscovery().measure_package("BILLSTATUS", 118, measure_type, 1)

    assert package.package_id == f"BILLSTATUS-118{measure_type}1"
    assert f"/BILLSTATUS/118/{measure_type}/" in package.url


def test_discovery_reads_official_json_listing():
    response = StubResponse(
        json_payload={
            "files": [
                {"name": "BILLSTATUS-118HR1.xml"},
                {
                    "name": "BILLSTATUS-118HR2.xml",
                    "url": "https://example.test/hr2.xml",
                },
                {"name": "README.txt"},
            ]
        }
    )
    session = StubSession(response)

    packages = GovInfoDiscovery(session=session).list_measure_packages(
        "BILLSTATUS", 118, "hr", listing_url="https://example.test/list.json"
    )

    assert [item.package_id for item in packages] == [
        "BILLSTATUS-118HR1",
        "BILLSTATUS-118HR2",
    ]
    assert packages[1].url == "https://example.test/hr2.xml"
    assert session.calls[0][1]["headers"] == {"Accept": "application/json"}


def test_discovery_reads_billsum_json_listing():
    response = StubResponse(json_payload={"files": [{"name": "BILLSUM-118hr1.xml"}]})

    packages = GovInfoDiscovery(session=StubSession(response)).list_measure_packages(
        "BILLSUM", 118, "hr", listing_url="https://example.test/list.json"
    )

    assert [item.package_id for item in packages] == ["BILLSUM-118hr1"]


def test_discovery_uses_session_for_bills_listing():
    session = StubSession(StubResponse(json_payload={"files": []}))

    GovInfoDiscovery(session=session).list_measure_packages("BILLS", 118, "hr")

    assert session.calls[0][0].endswith("/json/BILLS/118/1/hr/")


def test_discovery_reads_official_html_directory():
    response = StubResponse(
        content=b"""<html><a href="/bulkdata/BILLSTATUS/118/hr/BILLSTATUS-118hr1.xml">
        BILLSTATUS-118hr1.xml</a><a href="README.txt">README.txt</a></html>"""
    )

    packages = GovInfoDiscovery(session=StubSession(response)).list_measure_packages(
        "BILLSTATUS",
        118,
        "hr",
        listing_url="https://www.govinfo.gov/bulkdata/BILLSTATUS/118/hr/",
    )

    assert [item.package_id for item in packages] == ["BILLSTATUS-118hr1"]
    assert packages[0].url.endswith("/BILLSTATUS/118/hr/BILLSTATUS-118hr1.xml")


def test_downloader_extracts_zip_and_rejects_traversal(tmp_path):
    archive = tmp_path / "collection.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("BILLSTATUS-118HR1.xml", b"<billstatus />")
    downloader = GovInfoDownloader(tmp_path)
    extracted = downloader.extract_zip(package(), archive)

    assert (extracted / "BILLSTATUS-118HR1.xml").read_bytes() == b"<billstatus />"

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as handle:
        handle.writestr("../outside.xml", b"bad")
    with pytest.raises(GovInfoDownloadError, match="Unsafe path"):
        downloader.extract_zip(package(), unsafe)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(200, "available"), (404, "not_available")],
)
def test_discovery_probe_classifies_http_coverage(status_code, expected):
    govinfo_package = package()
    coverage = GovInfoDiscovery(
        session=StubSession(StubResponse(status_code=status_code))
    ).probe(govinfo_package)

    assert coverage.status == expected
    assert coverage.error is None


def test_discovery_probe_records_transport_failure():
    class FailedSession:
        def get(self, url, **kwargs):
            del url, kwargs
            raise requests.ConnectionError("offline")

    coverage = GovInfoDiscovery(session=FailedSession()).probe(package())

    assert coverage.status == "failed"
    assert coverage.error == "offline"


def test_manifest_store_upserts_package_state(tmp_path):
    store = GovInfoManifestStore(tmp_path / "govinfo.sqlite3")
    govinfo_package = package()

    store.upsert(
        govinfo_package,
        status="complete",
        path="BILLSTATUS/BILLSTATUS-118hr1.xml",
        byte_count=42,
        sha256="abc123",
        parser_version="1",
    )
    store.upsert(govinfo_package, status="parsed", parser_version="2")

    record = store.get(govinfo_package)
    assert record is not None
    assert record["status"] == "parsed"
    assert record["parser_version"] == "2"
    assert record["package_id"] == "BILLSTATUS-118hr1"


def test_manifest_rows_support_complete_coverage_summary(tmp_path):
    packages = [
        package(),
        GovInfoPackage(
            package_id="BILLSUM-118hr1",
            collection="BILLSUM",
            congress=118,
            measure_type="hr",
            url="https://example.test/summary.xml",
        ),
        GovInfoPackage(
            package_id="BILLSTATUS-118hr2",
            collection="BILLSTATUS",
            congress=118,
            measure_type="hr",
            url="https://example.test/status-2.xml",
        ),
    ]
    store = GovInfoManifestStore(tmp_path / "govinfo.sqlite3")
    store.upsert(packages[0], status="parsed")
    store.upsert(packages[1], status="not_available")
    store.upsert(packages[2], status="failed", error="offline")

    report = summarize_govinfo_coverage(packages, store.rows())

    assert report["expected_count"] == 3
    assert report["manifest_count"] == 3
    assert report["counts"] == {
        "available": 1,
        "failed": 1,
        "not_available": 1,
        "pending": 0,
    }
    assert report["complete"] is False
    assert {detail["status"] for detail in report["details"]} == {
        "failed",
        "not_available",
    }


def test_downloader_can_resume_from_sqlite_manifest(tmp_path):
    store = GovInfoManifestStore(tmp_path / "govinfo.sqlite3")
    first_session = StubSession(StubResponse(b"<billstatus />"))
    downloader = GovInfoDownloader(
        tmp_path, session=first_session, manifest_store=store
    )
    path = downloader.download(package())
    (tmp_path / "manifest.json").unlink()

    second_session = StubSession(StubResponse(b"unexpected"))
    resumed = GovInfoDownloader(
        tmp_path, session=second_session, manifest_store=store
    ).download(package())

    assert resumed == path
    assert second_session.calls == []


def test_discovery_lists_and_deduplicates_congress_packages():
    class DiscoveryStub:
        def list_measure_packages(
            self,
            collection: str,
            congress: int,
            measure_type: str,
            *,
            listing_url: str | None = None,
            session: int = 1,
        ) -> list[GovInfoPackage]:
            del listing_url
            return [
                GovInfoPackage(
                    package_id=f"{collection}-{congress}{measure_type}1",
                    collection=collection,
                    congress=congress,
                    measure_type=measure_type,
                    url="https://example.test/package.xml",
                    session=session if collection == "BILLS" else None,
                )
            ]

    discovery = GovInfoDiscovery.__new__(GovInfoDiscovery)
    discovery.list_measure_packages = DiscoveryStub().list_measure_packages
    packages = discovery.list_congress_packages(
        118,
        measure_types=("hr",),
        collections=("BILLSTATUS", "BILLS"),
        sessions=(1, 2),
    )

    assert {package.collection for package in packages} == {"BILLSTATUS", "BILLS"}
    assert len(packages) == 2


def test_billstatus_parser_normalizes_namespaced_xml_and_provenance():
    xml = b"""
        <billStatus xmlns="urn:test">
            <bill><billNumber>1</billNumber><congress>118</congress>
                <officialTitle>An official title</officialTitle>
                <introducedDate>2023-01-03</introducedDate>
                <sponsors><sponsor><fullName>Alex Example</fullName>
                    <bioguideId>E000001</bioguideId></sponsor></sponsors>
                <cosponsors><cosponsor><fullName>Casey Example</fullName>
                    <bioguideId>E000002</bioguideId></cosponsor></cosponsors>
                <committees><committee><name>House Committee on Testing</name>
                    <systemCode>HSXX</systemCode><chamber>House</chamber></committee></committees>
                <actions><item><actionDate>2023-01-04</actionDate><text>Introduced</text></item>
                    <item><actionDate>2023-02-01</actionDate><text>Referred</text></item></actions>
                <summaries><summary><actionDate>2023-02-02</actionDate>
                    <actionDesc>Summary</actionDesc><text><![CDATA[<p>Bill summary</p>]]></text>
                    <versionCode>00</versionCode></summary></summaries>
                <subjects><legislativeSubject><name>Testing</name></legislativeSubject>
                    <policyArea><name>Science</name></policyArea></subjects>
                <textVersions><textVersion><type>Introduced</type><date>2023-01-03</date>
                    <packageId>BILLS-118HR1IH</packageId><formats><format><type>XML</type>
                    <url>https://www.govinfo.gov/content/pkg/BILLS-118HR1IH/xml/BILLS-118HR1IH.xml</url>
                    </format></formats></textVersion></textVersions>
                <laws><law><number>118-1</number><type>Public Law</type></law></laws>
            </bill>
        </billStatus>
        """

    record = GovInfoBillStatusParser().parse(xml, package())

    assert record["id"] == "bill:118:hr:1"
    assert record["title"] == "An official title"
    assert record["introducedDate"] == "2023-01-03"
    assert record["actions"][-1]["text"] == "Referred"
    assert record["latestAction"]["actionDate"] == "2023-02-01"
    assert record["sponsors"] == [{"fullName": "Alex Example", "bioguideId": "E000001"}]
    assert record["cosponsors"][0]["bioguideId"] == "E000002"
    assert record["committees"][0]["systemCode"] == "HSXX"
    assert record["summaries"][0]["text"] == "<p>Bill summary</p>"
    assert record["subjects"]["policyArea"]["name"] == "Science"
    assert record["text_versions"][0]["formats"][0]["type"] == "XML"
    assert record["laws"] == [{"number": "118-1", "type": "Public Law"}]
    assert record["source_metadata"]["source"] == "govinfo:billstatus"


def test_billstatus_parser_keeps_text_versions_when_count_is_present():
    xml = """
        <billStatus>
            <bill>
                <textVersions>
                    <count>1</count>
                    <item>
                        <type>Introduced</type>
                        <date>2023-01-03</date>
                        <packageId>BILLS-118HR1IH</packageId>
                    </item>
                </textVersions>
            </bill>
        </billStatus>
    """

    record = GovInfoBillStatusParser().parse(xml, package())

    assert record["text_versions"][0]["package_id"] == "BILLS-118HR1IH"


def test_billstatus_parser_rejects_mismatched_package_identity():
    with pytest.raises(GovInfoParseError, match="identity"):
        GovInfoBillStatusParser().parse(
            "<billStatus />",
            GovInfoPackage(
                package_id="BILLSTATUS-117HR1",
                collection="BILLSTATUS",
                congress=118,
                measure_type="hr",
                url="https://example.test/status.xml",
            ),
        )


def test_bills_parser_extracts_text_version_and_full_text():
    govinfo_package = GovInfoPackage(
        package_id="BILLS-118HR1IH",
        collection="BILLS",
        congress=118,
        measure_type="hr",
        url="https://www.govinfo.gov/bulkdata/BILLS/118/1/HR/BILLS-118HR1IH.xml",
    )

    record = GovInfoBillsParser().parse(
        "<billText xmlns='urn:test'><content><![CDATA[Section 1. Test text.]]></content></billText>",
        govinfo_package,
    )

    assert record["id"] == "bill-text:118:hr:1:ih"
    assert record["version_code"] == "ih"
    assert record["full_text"] == "Section 1. Test text."
    assert record["source_metadata"]["source"] == "govinfo:bills"


def test_billsum_parser_extracts_real_summary_schema():
    govinfo_package = GovInfoPackage(
        package_id="BILLSUM-118hr1",
        collection="BILLSUM",
        congress=118,
        measure_type="hr",
        url="https://www.govinfo.gov/bulkdata/BILLSUM/118/hr/BILLSUM-118hr1.xml",
    )

    record = GovInfoBillSummaryParser().parse(
        """<BillSummaries><item congress='118' measure-type='hr' measure-number='1'>
        <title>Example Act</title><summary summary-id='v1' currentChamber='HOUSE'
        update-date='2023-01-02'><action-date>2023-01-01</action-date>
        <action-desc>Introduced</action-desc><summary-text><![CDATA[<p>Summary.</p>]]>
        </summary-text></summary></item></BillSummaries>""",
        govinfo_package,
    )

    assert record["id"] == "bill:118:hr:1"
    assert record["title"] == "Example Act"
    assert record["summaries"][0]["text"] == "<p>Summary.</p>"
    assert record["source_metadata"]["source"] == "govinfo:billsum"
