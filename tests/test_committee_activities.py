from __future__ import annotations

from cdm.ingest.govinfo import GovInfoBillStatusParser, GovInfoPackage

_XML = """<billStatus><bill>
<title>Test Act</title>
<committees>
  <item>
    <systemCode>hsba00</systemCode>
    <name>Financial Services Committee</name>
    <chamber>House</chamber>
    <type>Standing</type>
    <subcommittees>
      <item>
        <systemCode>hsba15</systemCode>
        <name>Housing Subcommittee</name>
        <activities><item><name>Referred to</name><date>2013-04-02T19:45:43Z</date></item></activities>
      </item>
    </subcommittees>
    <activities><item><name>Referred to</name><date>2013-03-13T14:01:50Z</date></item></activities>
  </item>
</committees>
</bill></billStatus>"""

_PACKAGE = GovInfoPackage(
    package_id="BILLSTATUS-113hr1134",
    collection="BILLSTATUS",
    congress=113,
    measure_type="hr",
    url="",
)


def test_committee_activities_and_subcommittees_are_parsed() -> None:
    record = GovInfoBillStatusParser().parse(_XML, _PACKAGE)
    [committee] = record["committees"]
    assert committee["system_code"] == "hsba00"
    assert committee["type"] == "Standing"
    assert committee["activities"] == [
        {"name": "Referred to", "date": "2013-03-13T14:01:50Z"}
    ]
    [subcommittee] = committee["subcommittees"]
    assert subcommittee["system_code"] == "hsba15"
    assert subcommittee["activities"][0]["date"] == "2013-04-02T19:45:43Z"
