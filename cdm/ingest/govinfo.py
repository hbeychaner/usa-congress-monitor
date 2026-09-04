"""Resumable acquisition of official GovInfo bulk artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urljoin

import requests
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


class GovInfoHttpSession(Protocol):
    """Minimal HTTP session contract used by discovery and download code."""

    def get(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class GovInfoPackage:
    """Identity and source location for one official bulk artifact."""

    package_id: str
    collection: str
    congress: int
    measure_type: str
    url: str
    session: int | None = None
    version_code: str | None = None


_METADATA = MetaData()
_GOVINFO_PACKAGES = Table(
    "govinfo_packages",
    _METADATA,
    Column("collection", String, primary_key=True),
    Column("congress", Integer, primary_key=True),
    Column("measure_type", String, primary_key=True),
    Column("package_id", String, primary_key=True),
    Column("url", String, nullable=False),
    Column("session", Integer),
    Column("version_code", String),
    Column("status", String, nullable=False),
    Column("path", String),
    Column("bytes", Integer),
    Column("sha256", String),
    Column("etag", String),
    Column("last_modified", String),
    Column("fetched_at", String),
    Column("parser_version", String),
    Column("error", String),
)


class GovInfoManifestStore:
    """Persist GovInfo package state for resumable acquisition and parsing."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path}")
        _METADATA.create_all(self.engine)

    def upsert(
        self,
        package: GovInfoPackage,
        *,
        status: str,
        path: str | None = None,
        byte_count: int | None = None,
        sha256: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        fetched_at: str | None = None,
        parser_version: str | None = None,
        error: str | None = None,
    ) -> None:
        values = {
            "collection": package.collection,
            "congress": package.congress,
            "measure_type": package.measure_type,
            "package_id": package.package_id,
            "url": package.url,
            "session": package.session,
            "version_code": package.version_code,
            "status": status,
            "path": path,
            "bytes": byte_count,
            "sha256": sha256,
            "etag": etag,
            "last_modified": last_modified,
            "fetched_at": fetched_at,
            "parser_version": parser_version,
            "error": error,
        }
        statement = sqlite_insert(_GOVINFO_PACKAGES).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=(
                _GOVINFO_PACKAGES.c.collection,
                _GOVINFO_PACKAGES.c.congress,
                _GOVINFO_PACKAGES.c.measure_type,
                _GOVINFO_PACKAGES.c.package_id,
            ),
            set_={column: getattr(statement.excluded, column) for column in (
                "url", "session", "version_code", "status", "path", "bytes",
                "sha256", "etag", "last_modified", "fetched_at", "parser_version", "error",
            )},
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

    def get(self, package: GovInfoPackage) -> dict[str, Any] | None:
        statement = select(_GOVINFO_PACKAGES).where(
            _GOVINFO_PACKAGES.c.collection == package.collection,
            _GOVINFO_PACKAGES.c.congress == package.congress,
            _GOVINFO_PACKAGES.c.measure_type == package.measure_type,
            _GOVINFO_PACKAGES.c.package_id == package.package_id,
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def rows(self) -> list[dict[str, Any]]:
        """Return all persisted package states for coverage reporting."""
        statement = select(_GOVINFO_PACKAGES).order_by(
            _GOVINFO_PACKAGES.c.collection, _GOVINFO_PACKAGES.c.package_id
        )
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement).mappings()]


def summarize_govinfo_coverage(
    packages: list[GovInfoPackage],
    manifest_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare discovered packages with persisted acquisition states."""
    states = {
        ":".join((
            str(row["collection"]),
            str(row["congress"]),
            str(row["measure_type"]),
            str(row["package_id"]),
        )): row
        for row in manifest_rows
    }
    counts: dict[str, int] = {
        "available": 0,
        "failed": 0,
        "not_available": 0,
        "pending": 0,
    }
    details: list[dict[str, Any]] = []
    for package in packages:
        key = ":".join((
            package.collection,
            str(package.congress),
            package.measure_type,
            package.package_id,
        ))
        row = states.get(key)
        raw_status = str(row.get("status", "pending")) if row else "pending"
        status = "available" if raw_status in {"complete", "parsed"} else raw_status
        if status not in counts:
            status = "pending"
        counts[status] += 1
        if status != "available":
            details.append({
                "collection": package.collection,
                "congress": package.congress,
                "measure_type": package.measure_type,
                "package_id": package.package_id,
                "status": status,
                "error": row.get("error") if row else None,
            })
    return {
        "expected_count": len(packages),
        "manifest_count": len(manifest_rows),
        "counts": counts,
        "complete": counts["pending"] == 0 and counts["failed"] == 0,
        "details": details,
    }


@dataclass(frozen=True)
class GovInfoCoverage:
    """Result of checking whether an official package is available."""

    package: GovInfoPackage
    status: str
    checked_at: str
    error: str | None = None


class GovInfoDownloadError(RuntimeError):
    """Raised when a GovInfo artifact cannot be downloaded or verified."""


class GovInfoParseError(ValueError):
    """Raised when a GovInfo artifact cannot be normalized safely."""


class GovInfoBillStatusParser:
    """Normalize the stable identity and core metadata in BILLSTATUS XML."""

    _PACKAGE_ID = re.compile(
        r"^BILLSTATUS-(?P<congress>\d+)(?P<type>[A-Z]+)(?P<number>\d+)$",
        re.IGNORECASE,
    )

    def parse(self, xml: bytes | str, package: GovInfoPackage) -> dict[str, Any]:
        """Return a canonical bill dictionary with official provenance."""
        if package.collection.upper() != "BILLSTATUS":
            raise GovInfoParseError("BILLSTATUS parser requires a BILLSTATUS package")
        match = self._PACKAGE_ID.match(package.package_id)
        if not match:
            raise GovInfoParseError(
                f"Invalid BILLSTATUS package id: {package.package_id}"
            )
        if (
            int(match["congress"]) != package.congress
            or match["type"].lower() != package.measure_type.lower()
        ):
            raise GovInfoParseError("Package identity does not match its descriptor")

        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise GovInfoParseError(f"Invalid BILLSTATUS XML: {exc}") from exc

        bill = next(
            (element for element in root if self._local_name(element.tag) == "bill"),
            root,
        )
        source_metadata = {
            "collection": package.collection,
            "package_id": package.package_id,
            "url": package.url,
            "source": "govinfo:billstatus",
        }
        number = int(match["number"])
        bill_type = package.measure_type.lower()
        record: dict[str, Any] = {
            "id": f"bill:{package.congress}:{bill_type}:{number}",
            "congress": package.congress,
            "number": str(number),
            "type": bill_type,
            "title": self._direct_text(bill, "title")
            or self._first_text(bill, "officialTitle")
            or self._first_text(bill, "shortTitle")
            or "",
            "actions": self._actions(bill),
            "sponsors": self._people_in_container(bill, "sponsors", "item"),
            "cosponsors": self._people_in_container(bill, "cosponsors", "item"),
            "committees": self._committees(bill),
            "related_bills": self._related_bills(bill),
            "summaries": self._summaries(bill),
            "subjects": self._subjects(bill),
            "text_versions": self._text_versions(bill),
            "laws": self._laws(bill),
            "source_metadata": source_metadata,
        }
        for field_name in (
            "updateDate",
            "updateDateIncludingText",
            "originChamber",
            "originChamberCode",
            "legislationUrl",
        ):
            value = self._first_text(bill, field_name)
            if value:
                record[field_name] = value
        constitutional = self._first_text(bill, "constitutionalAuthorityStatementText")
        if constitutional:
            record["constitutional_authority_statement_text"] = constitutional
        introduced = self._first_text(bill, "introducedDate")
        if introduced:
            record["introducedDate"] = introduced
        latest_action = self._latest_action(bill)
        if latest_action:
            record["latestAction"] = latest_action
        return record

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _elements(cls, root: ET.Element, name: str):
        return (
            element for element in root.iter() if cls._local_name(element.tag) == name
        )

    @classmethod
    def _first_text(cls, root: ET.Element, name: str) -> str:
        for element in cls._elements(root, name):
            text = " ".join("".join(element.itertext()).split())
            if text:
                return text
        return ""

    @classmethod
    def _direct_text(cls, root: ET.Element, name: str) -> str:
        for element in root:
            if cls._local_name(element.tag) == name:
                text = " ".join("".join(element.itertext()).split())
                if text:
                    return text
        return ""

    @classmethod
    def _actions(cls, root: ET.Element) -> list[dict[str, str]]:
        actions = []
        containers = list(cls._elements(root, "actions"))
        elements = (
            (item for container in containers for item in container)
            if containers
            else ()
        )
        for element in elements:
            date = cls._first_text(element, "actionDate")
            text = cls._first_text(element, "text")
            if date or text:
                actions.append({"actionDate": date, "text": text})
        return actions

    @classmethod
    def _sponsors(cls, root: ET.Element) -> list[dict[str, str]]:
        return cls._people(root, "sponsor")

    @classmethod
    def _people(cls, root: ET.Element, element_name: str) -> list[dict[str, str]]:
        sponsors = []
        for element in cls._elements(root, element_name):
            sponsor = {
                "fullName": cls._first_text(element, "fullName")
                or cls._first_text(element, "name"),
                "bioguideId": cls._first_text(element, "bioguideId"),
            }
            if any(sponsor.values()):
                sponsors.append({key: value for key, value in sponsor.items() if value})
        return sponsors

    @classmethod
    def _people_in_container(
        cls, root: ET.Element, container_name: str, item_name: str
    ) -> list[dict[str, str]]:
        container = next(
            (
                element
                for element in root
                if cls._local_name(element.tag) == container_name
            ),
            None,
        )
        if container is None:
            return []
        people = []
        for element in container:
            if cls._local_name(element.tag) not in {item_name, container_name[:-1]}:
                continue
            values = {
                key: cls._first_text(element, key)
                for key in (
                    "fullName",
                    "bioguideId",
                    "firstName",
                    "middleName",
                    "lastName",
                    "party",
                    "state",
                    "district",
                    "sponsorshipDate",
                    "isOriginalCosponsor",
                )
            }
            if any(values.values()):
                people.append({key: value for key, value in values.items() if value})
        return people

    @classmethod
    def _committees(cls, root: ET.Element) -> list[dict[str, str]]:
        container = next(
            (
                element
                for element in root
                if cls._local_name(element.tag) == "committees"
            ),
            None,
        )
        committees = []
        if container is None:
            return committees
        for element in container:
            if cls._local_name(element.tag) not in {"item", "committee"}:
                continue
            values: dict[str, Any] = {
                "name": cls._first_text(element, "name"),
                "systemCode": cls._first_text(element, "systemCode"),
                "chamber": cls._first_text(element, "chamber"),
                "type": cls._first_text(element, "type"),
            }
            if any(values.values()):
                committees.append({
                    key: value for key, value in values.items() if value
                })
        return committees

    @classmethod
    def _related_bills(cls, root: ET.Element) -> list[dict[str, str]]:
        container = next(
            (
                element
                for element in root
                if cls._local_name(element.tag) == "relatedBills"
            ),
            None,
        )
        related = []
        if container is None:
            return related
        for element in container:
            if cls._local_name(element.tag) not in {"item", "relatedBill"}:
                continue
            values = {
                "congress": cls._first_text(element, "congress"),
                "number": cls._first_text(element, "number"),
                "type": cls._first_text(element, "type"),
                "title": cls._first_text(element, "title"),
            }
            if values["congress"] and values["number"] and values["type"]:
                values["id"] = (
                    f"bill:{values['congress']}:{values['type'].lower()}:{values['number']}"
                )
                relationship = cls._first_text(element, "type")
                identified_by = cls._first_text(element, "identifiedBy")
                result = {key: value for key, value in values.items() if value}
                if relationship:
                    result["relationship"] = relationship
                if identified_by:
                    result["identifiedBy"] = identified_by
                related.append(result)
        return related

    @classmethod
    def _summaries(cls, root: ET.Element) -> list[dict[str, str]]:
        summaries = []
        for element in cls._elements(root, "summary"):
            values = {
                "actionDate": cls._first_text(element, "actionDate"),
                "actionDesc": cls._first_text(element, "actionDesc"),
                "text": cls._first_text(element, "text"),
                "updateDate": cls._first_text(element, "updateDate"),
                "versionCode": cls._first_text(element, "versionCode"),
            }
            if any(values.values()):
                summaries.append(values)
        return summaries

    @classmethod
    def _subjects(cls, root: ET.Element) -> dict[str, Any]:
        subjects = [
            {"name": cls._first_text(element, "name")}
            for element in cls._elements(root, "legislativeSubject")
            if cls._first_text(element, "name")
        ]
        policy_area = cls._first_text(root, "policyArea")
        result: dict[str, Any] = {"legislativeSubjects": subjects}
        if policy_area:
            result["policyArea"] = {"name": policy_area}
        return result

    @classmethod
    def _text_versions(cls, root: ET.Element) -> list[dict[str, Any]]:
        container = next(
            (
                element
                for element in root
                if cls._local_name(element.tag) == "textVersions"
            ),
            None,
        )
        if container is None:
            return []
        versions = []
        for element in container:
            if cls._local_name(element.tag) not in {"item", "textVersion"}:
                continue
            formats = []
            format_container = next(
                (child for child in element if cls._local_name(child.tag) == "formats"),
                None,
            )
            format_items = (
                list(format_container)
                if format_container is not None
                else list(cls._elements(element, "format"))
            )
            for item in format_items:
                if cls._local_name(item.tag) not in {"item", "format"}:
                    continue
                values = {
                    "type": cls._first_text(item, "type"),
                    "url": cls._first_text(item, "url"),
                }
                if not values["type"] and values["url"]:
                    values["type"] = (
                        Path(values["url"].split("?", 1)[0]).suffix.lstrip(".").upper()
                    )
                if any(values.values()):
                    formats.append({
                        key: value for key, value in values.items() if value
                    })
            values: dict[str, Any] = {
                "type": cls._first_text(element, "type"),
                "date": cls._first_text(element, "date"),
                "package_id": cls._first_text(element, "packageId"),
                "source_url": cls._first_text(element, "url"),
            }
            if not values["package_id"] and values["source_url"]:
                values["package_id"] = Path(
                    values["source_url"].split("?", 1)[0].rstrip("/").split("/")[-1]
                ).stem
            if formats:
                values["formats"] = formats
            if any(value for key, value in values.items() if key != "formats"):
                versions.append({key: value for key, value in values.items() if value})
        return versions

    @classmethod
    def _laws(cls, root: ET.Element) -> list[dict[str, str]]:
        laws = []
        for element in cls._elements(root, "law"):
            values = {
                "number": cls._first_text(element, "number"),
                "type": cls._first_text(element, "type"),
            }
            if values["number"] and values["type"]:
                laws.append(values)
        return laws

    @classmethod
    def _latest_action(cls, root: ET.Element) -> dict[str, str] | None:
        actions = cls._actions(root)
        return actions[-1] if actions else None


class GovInfoBillsParser:
    """Normalize one published BILLS XML text version."""

    _PACKAGE_ID = re.compile(
        r"^BILLS-(?P<congress>\d+)(?P<type>[A-Z]+)(?P<number>\d+)(?P<version>[A-Z0-9]+)$",
        re.IGNORECASE,
    )

    def parse(self, xml: bytes | str, package: GovInfoPackage) -> dict[str, Any]:
        """Return a text-version record and extracted published text."""
        if package.collection.upper() != "BILLS":
            raise GovInfoParseError("BILLS parser requires a BILLS package")
        match = self._PACKAGE_ID.match(package.package_id)
        if not match:
            raise GovInfoParseError(f"Invalid BILLS package id: {package.package_id}")
        if (
            int(match["congress"]) != package.congress
            or match["type"].lower() != package.measure_type.lower()
        ):
            raise GovInfoParseError("Package identity does not match its descriptor")
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise GovInfoParseError(f"Invalid BILLS XML: {exc}") from exc

        text = self._all_text(root, "text") or self._first_text(root, "content")
        number = int(match["number"])
        bill_type = package.measure_type.lower()
        return {
            "id": f"bill-text:{package.congress}:{bill_type}:{number}:{match['version'].lower()}",
            "congress": package.congress,
            "number": str(number),
            "type": bill_type,
            "version_code": match["version"].lower(),
            "full_text": text,
            "source_metadata": {
                "collection": package.collection,
                "package_id": package.package_id,
                "url": package.url,
                "source": "govinfo:bills",
            },
        }

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _first_text(cls, root: ET.Element, name: str) -> str:
        for element in root.iter():
            if cls._local_name(element.tag) == name:
                text = " ".join("".join(element.itertext()).split())
                if text:
                    return text
        return ""

    @classmethod
    def _all_text(cls, root: ET.Element, name: str) -> str:
        values = []
        for element in root.iter():
            if cls._local_name(element.tag) == name:
                text = " ".join("".join(element.itertext()).split())
                if text:
                    values.append(text)
        return "\n".join(values)


class GovInfoBillSummaryParser:
    """Normalize a BILLSUM package containing one measure's summaries."""

    _PACKAGE_ID = re.compile(
        r"^BILLSUM-(?P<congress>\d+)(?P<type>[A-Z]+)(?P<number>\d+)$",
        re.IGNORECASE,
    )

    def parse(self, xml: bytes | str, package: GovInfoPackage) -> dict[str, Any]:
        """Return measure metadata and every published summary in the package."""
        if package.collection.upper() != "BILLSUM":
            raise GovInfoParseError("BILLSUM parser requires a BILLSUM package")
        match = self._PACKAGE_ID.match(package.package_id)
        if not match:
            raise GovInfoParseError(f"Invalid BILLSUM package id: {package.package_id}")
        if (
            int(match["congress"]) != package.congress
            or match["type"].lower() != package.measure_type.lower()
        ):
            raise GovInfoParseError("Package identity does not match its descriptor")
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise GovInfoParseError(f"Invalid BILLSUM XML: {exc}") from exc

        item = next(
            (element for element in root if self._local_name(element.tag) == "item"),
            None,
        )
        if item is None:
            raise GovInfoParseError("BILLSUM XML contains no measure item")
        summaries = []
        for summary in item:
            if self._local_name(summary.tag) != "summary":
                continue
            values: dict[str, Any] = dict(summary.attrib)
            values["actionDate"] = self._child_text(summary, "action-date")
            values["actionDesc"] = self._child_text(summary, "action-desc")
            values["updateDate"] = summary.attrib.get("update-date", "")
            values["chamber"] = summary.attrib.get("currentChamber", "")
            values["text"] = self._child_text(summary, "summary-text")
            summaries.append({key: value for key, value in values.items() if value})
        return {
            "id": f"bill:{package.congress}:{package.measure_type.lower()}:{int(match['number'])}",
            "congress": package.congress,
            "number": match["number"],
            "type": package.measure_type.lower(),
            "title": self._child_text(item, "title"),
            "summaries": summaries,
            "source_metadata": {
                "collection": package.collection,
                "package_id": package.package_id,
                "url": package.url,
                "source": "govinfo:billsum",
            },
        }

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _child_text(cls, root: ET.Element, name: str) -> str:
        for element in root:
            if cls._local_name(element.tag) == name:
                return " ".join("".join(element.itertext()).split())
        return ""


class GovInfoDiscovery:
    """Discover and probe packages in the official bulk collections."""

    BASE_URL = "https://www.govinfo.gov/bulkdata"
    JSON_BASE_URL = "https://www.govinfo.gov/bulkdata/json"
    MEASURE_TYPES = (
        "hr",
        "s",
        "hjres",
        "sjres",
        "hconres",
        "sconres",
        "hres",
        "sres",
    )

    def __init__(
        self,
        *,
        session: GovInfoHttpSession | None = None,
        timeout: int = 60,
    ) -> None:
        if timeout < 1:
            raise ValueError("timeout must be positive")
        self.session = session or requests.Session()
        self.timeout = timeout

    def measure_package(
        self, collection: str, congress: int, measure_type: str, number: int
    ) -> GovInfoPackage:
        """Return the official package URL for a measure-level collection."""
        normalized_collection = collection.upper()
        if normalized_collection not in {"BILLSTATUS", "BILLSUM"}:
            raise ValueError("measure collection must be BILLSTATUS or BILLSUM")
        package_id = f"{normalized_collection}-{congress}{measure_type.lower()}{number}"
        url = (
            f"{self.BASE_URL}/{normalized_collection}/{congress}/{measure_type.lower()}/"
            f"{package_id}.xml"
        )
        return GovInfoPackage(
            package_id=package_id,
            collection=normalized_collection,
            congress=congress,
            measure_type=measure_type.lower(),
            url=url,
        )

    def text_package(
        self,
        congress: int,
        session: int,
        measure_type: str,
        number: int,
        version: str,
    ) -> GovInfoPackage:
        """Return the official package URL for one published text version."""
        package_id = f"BILLS-{congress}{measure_type.lower()}{number}{version.lower()}"
        url = (
            f"{self.BASE_URL}/BILLS/{congress}/{session}/{measure_type.lower()}/"
            f"{package_id}.xml"
        )
        return GovInfoPackage(
            package_id=package_id,
            collection="BILLS",
            congress=congress,
            measure_type=measure_type.lower(),
            url=url,
            session=session,
            version_code=version.lower(),
        )

    def probe(self, package: GovInfoPackage) -> GovInfoCoverage:
        """Classify a package as available, not_available, or failed."""
        try:
            response = self.session.get(
                package.url,
                stream=True,
                timeout=self.timeout,
            )
            if response.status_code == 404:
                status = "not_available"
            else:
                response.raise_for_status()
                status = "available"
            return GovInfoCoverage(package, status, GovInfoDownloader._now())
        except (requests.RequestException, OSError) as exc:
            return GovInfoCoverage(
                package, "failed", GovInfoDownloader._now(), str(exc)
            )

    def list_measure_packages(
        self,
        collection: str,
        congress: int,
        measure_type: str,
        *,
        listing_url: str | None = None,
        session: int = 1,
    ) -> list[GovInfoPackage]:
        """Read the official JSON directory and return its package entries."""
        normalized_collection = collection.upper()
        default_path = f"{normalized_collection}/{congress}/"
        if normalized_collection == "BILLS":
            default_path += f"{session}/{measure_type.lower()}/"
        else:
            default_path += f"{measure_type.lower()}/"
        url = listing_url or f"{self.JSON_BASE_URL}/{default_path}"
        response = self.session.get(
            url,
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except (AttributeError, ValueError):
            html = getattr(response, "text", "")
            if not html and hasattr(response, "content"):
                html = response.content.decode("utf-8", errors="replace")
            return self._packages_from_html(
                html, normalized_collection, congress, measure_type, url
            )

        entries = payload if isinstance(payload, list) else None
        if entries is None and isinstance(payload, dict):
            for key in ("files", "items", "results", "packages"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    entries = candidate
                    break
        if entries is None:
            raise GovInfoParseError("GovInfo listing JSON has no package entries")

        packages: list[GovInfoPackage] = []
        for entry in entries:
            if isinstance(entry, str):
                name, entry_url = entry, None
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("path") or entry.get("file")
                entry_url = (
                    entry.get("url") or entry.get("download_url") or entry.get("link")
                )
            else:
                continue
            if not isinstance(name, str):
                continue
            package_id = Path(name).stem
            package_session: int | None = session
            if normalized_collection == "BILLS":
                match = GovInfoBillsParser._PACKAGE_ID.match(package_id)
                package_session = (
                    int(entry["session"])
                    if isinstance(entry, dict) and entry.get("session")
                    else session
                )
                version = match["version"].lower() if match else None
            elif normalized_collection == "BILLSUM":
                match = GovInfoBillSummaryParser._PACKAGE_ID.match(package_id)
                package_session = None
                version = None
            else:
                match = GovInfoBillStatusParser._PACKAGE_ID.match(package_id)
                package_session = None
                version = None
            if not match:
                continue
            package_url = str(entry_url or name)
            if not package_url.startswith("http"):
                package_url = (
                    f"{self.BASE_URL}/{normalized_collection}/{congress}/"
                    f"{measure_type.lower()}/{name}"
                )
            packages.append(
                GovInfoPackage(
                    package_id=package_id,
                    collection=normalized_collection,
                    congress=congress,
                    measure_type=measure_type.lower(),
                    url=package_url,
                    session=package_session,
                    version_code=version,
                )
            )
        return packages

    def list_congress_packages(
        self,
        congress: int,
        *,
        measure_types: tuple[str, ...] = MEASURE_TYPES,
        collections: tuple[str, ...] = ("BILLSTATUS", "BILLSUM", "BILLS"),
        sessions: tuple[int, ...] = (1, 2),
    ) -> list[GovInfoPackage]:
        """Discover all supported official packages for one Congress."""
        packages: dict[str, GovInfoPackage] = {}
        for collection in collections:
            for measure_type in measure_types:
                collection_sessions = sessions if collection.upper() == "BILLS" else (1,)
                for session in collection_sessions:
                    for package in self.list_measure_packages(
                        collection,
                        congress,
                        measure_type,
                        session=session,
                    ):
                        packages.setdefault(package.package_id, package)
        return sorted(packages.values(), key=lambda package: package.package_id)

    @staticmethod
    def _packages_from_html(
        html: str,
        collection: str,
        congress: int,
        measure_type: str,
        listing_url: str,
    ) -> list[GovInfoPackage]:
        """Extract package links from GovInfo's official HTML directory table."""

        class LinkParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.hrefs: list[str] = []

            def handle_starttag(
                self, tag: str, attrs: list[tuple[str, str | None]]
            ) -> None:
                if tag != "a":
                    return
                href = dict(attrs).get("href")
                if href:
                    self.hrefs.append(href)

        parser = LinkParser()
        parser.feed(html)
        normalized_collection = collection.upper()
        normalized_type = measure_type.upper()
        packages: list[GovInfoPackage] = []
        patterns = {
            "BILLSTATUS": GovInfoBillStatusParser._PACKAGE_ID,
            "BILLSUM": GovInfoBillSummaryParser._PACKAGE_ID,
            "BILLS": GovInfoBillsParser._PACKAGE_ID,
        }
        pattern = patterns.get(normalized_collection)
        if pattern is None:
            raise GovInfoParseError(f"Unsupported GovInfo collection: {collection}")
        for href in parser.hrefs:
            name = href.split("?", 1)[0].rstrip("/").split("/")[-1]
            package_id = Path(name).stem
            match = pattern.match(package_id)
            if not match:
                continue
            if match["type"].upper() != normalized_type:
                continue
            package_url = (
                href if href.startswith("http") else urljoin(listing_url, href)
            )
            packages.append(
                GovInfoPackage(
                    package_id=package_id,
                    collection=normalized_collection,
                    congress=congress,
                    measure_type=measure_type.lower(),
                    url=package_url,
                    session=None,
                    version_code=(
                        match["version"].lower()
                        if normalized_collection == "BILLS"
                        else None
                    ),
                )
            )
        return packages


class GovInfoDownloader:
    """Download GovInfo artifacts with atomic writes and a durable manifest."""

    def __init__(
        self,
        root: Path,
        *,
        session: GovInfoHttpSession | None = None,
        timeout: int = 60,
        manifest_store: GovInfoManifestStore | None = None,
    ) -> None:
        if timeout < 1:
            raise ValueError("timeout must be positive")
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = root / "manifest.json"
        self.session = session or requests.Session()
        self.timeout = timeout
        self.manifest_store = manifest_store

    def download(self, package: GovInfoPackage, *, force: bool = False) -> Path:
        """Download *package* and return its verified local artifact path."""
        manifest = self._load_manifest()
        key = self._manifest_key(package)
        previous = (
            manifest.get(key)
            or (self.manifest_store.get(package) if self.manifest_store else None)
            or {}
        )
        destination = self._artifact_path(package)

        if (
            not force
            and previous.get("status") == "complete"
            and previous.get("sha256")
            and destination.exists()
            and self._sha256(destination) == previous["sha256"]
        ):
            return destination

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        headers: dict[str, str] = {}
        if previous.get("etag"):
            headers["If-None-Match"] = previous["etag"]
        if previous.get("last_modified"):
            headers["If-Modified-Since"] = previous["last_modified"]

        try:
            response = self.session.get(
                package.url,
                headers=headers,
                stream=True,
                timeout=self.timeout,
            )
            if response.status_code == 404 and package.collection.upper() == "BILLS":
                response = self.session.get(
                    self._content_url(package),
                    headers=headers,
                    stream=True,
                    timeout=self.timeout,
                )
            if response.status_code == 304 and destination.exists():
                previous["fetched_at"] = self._now()
                previous["status"] = "complete"
                manifest[key] = previous
                self._save_manifest(manifest)
                self._record_manifest(package, previous)
                return destination
            response.raise_for_status()
            digest = hashlib.sha256()
            byte_count = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
            os.replace(temporary, destination)
        except (OSError, requests.RequestException) as exc:
            temporary.unlink(missing_ok=True)
            manifest[key] = {
                **asdict(package),
                "status": "failed",
                "error": str(exc),
                "failed_at": self._now(),
            }
            self._save_manifest(manifest)
            self._record_manifest(
                package,
                {
                    **asdict(package),
                    "status": "failed",
                    "error": str(exc),
                },
            )
            raise GovInfoDownloadError(
                f"Failed to download GovInfo package {package.package_id}: {exc}"
            ) from exc

        manifest[key] = {
            **asdict(package),
            "status": "complete",
            "path": str(destination),
            "bytes": byte_count,
            "sha256": digest.hexdigest(),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "fetched_at": self._now(),
        }
        self._save_manifest(manifest)
        self._record_manifest(package, manifest[key])
        return destination

    def extract_zip(self, package: GovInfoPackage, archive: Path) -> Path:
        """Safely extract a downloaded collection ZIP beneath its artifact root."""
        destination = self.root / package.collection / package.package_id
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        with zipfile.ZipFile(archive) as handle:
            for member in handle.infolist():
                target = (destination / member.filename).resolve()
                if target != root and root not in target.parents:
                    raise GovInfoDownloadError(
                        f"Unsafe path in GovInfo ZIP {package.package_id}: {member.filename}"
                    )
            handle.extractall(destination)
        return destination

    def _record_manifest(self, package: GovInfoPackage, record: dict[str, Any]) -> None:
        if not self.manifest_store:
            return
        self.manifest_store.upsert(
            package,
            status=str(record.get("status", "unknown")),
            path=record.get("path"),
            byte_count=record.get("bytes"),
            sha256=record.get("sha256"),
            etag=record.get("etag"),
            last_modified=record.get("last_modified"),
            fetched_at=record.get("fetched_at"),
            error=record.get("error"),
        )

    def _artifact_path(self, package: GovInfoPackage) -> Path:
        safe_id = "".join(
            character if character.isalnum() or character in "-_." else "_"
            for character in package.package_id
        )
        suffix = Path(package.url.split("?", 1)[0]).suffix or ".xml"
        return self.root / package.collection / f"{safe_id}{suffix}"

    @staticmethod
    def _content_url(package: GovInfoPackage) -> str:
        package_id = (
            f"BILLS-{package.congress}{package.measure_type.lower()}"
            f"{package.package_id.removeprefix('BILLS-')[len(str(package.congress)) + len(package.measure_type) :].lower()}"
        )
        return f"https://www.govinfo.gov/content/pkg/{package_id}/xml/{package_id}.xml"

    @staticmethod
    def _manifest_key(package: GovInfoPackage) -> str:
        return ":".join((
            package.collection,
            str(package.congress),
            package.measure_type,
            package.package_id,
        ))

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        if not self.manifest_path.exists():
            return {}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, self.manifest_path)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
