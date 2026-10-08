from cdm.ingest.govinfo import GovInfoBillsParser, GovInfoPackage

XML = (
    '<?xml version="1.0"?>\n<bill>\n<form>'
    "<title>Youth HIV & AIDS Day &amp; more</title></form>\n"
    "<text>body</text></bill>"
)


def test_bare_ampersand_is_recovered():
    package = GovInfoPackage(
        collection="BILLS",
        congress=113,
        measure_type="hres",
        package_id="BILLS-113hres148ih",
        url="https://example.test/x.xml",
        session=1,
    )
    for payload in (XML, XML.encode()):
        record = GovInfoBillsParser().parse(payload, package)
        assert record["congress"] == 113
