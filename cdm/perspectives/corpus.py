"""Reads one Congress's bills, their sponsoring parties, and cached embeddings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan

from cdm.config import PerspectiveConfig
from cdm.graph.models import PartyGroup
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.perspectives.models import MAJOR_PARTIES, PerspectiveBill
from cdm.perspectives.terms import Tokenizer
from cdm.store.opensearch import read_alias
from cdm.utils.topic_modeler import TopicDocument, build_topic_documents

SPONSOR_FIELD = "sponsor_bioguide_ids"
COSPONSOR_FIELD = "cosponsor_bioguide_ids"
TYPE_FIELD = "type"
ID_TYPE_POSITION = 2
FULL_TEXT_FIELD = "full_text_lemma"
NAME_FIELDS = ("name", "direct_order_name", "first_name", "last_name")
BILL_FIELDS = [
    "title",
    TYPE_FIELD,
    "title_lemma",
    "summaries",
    "introduced_date",
    "latest_action",
    "policy_area",
    "subjects.legislative_subjects",
    SPONSOR_FIELD,
    COSPONSOR_FIELD,
    FULL_TEXT_FIELD,
]


@dataclass(frozen=True)
class CongressCorpus:
    """Bills of one Congress with the topic-model documents they were embedded from."""

    congress: int
    bills: dict[str, PerspectiveBill]
    documents: dict[str, TopicDocument]


class MemberPartyReader:
    """Maps bioguide ids to a party group from the member index."""

    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def read(self) -> dict[str, PartyGroup]:
        parties: dict[str, PartyGroup] = {}
        hits = scan(
            self.client,
            index=read_alias("member"),
            query={
                "query": {"match_all": {}},
                "_source": ["bioguide_id", "party_name", "party"],
            },
        )
        for hit in hits:
            source = hit["_source"]
            bioguide_id = source.get("bioguide_id")
            name = str(source.get("party_name") or source.get("party") or "")
            if bioguide_id and name:
                parties[str(bioguide_id)] = PartyGroup.of(name)
        return parties


class MemberNameReader:
    """Name and state tokens of every member, so sponsor credits are not read as subjects."""

    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def read(self) -> BoilerplateLexicon:
        names: set[str] = set()
        places: set[str] = set()
        hits = scan(
            self.client,
            index=read_alias("member"),
            query={
                "query": {"match_all": {}},
                "_source": [*NAME_FIELDS, "state"],
            },
        )
        for hit in hits:
            source = hit["_source"]
            for field in NAME_FIELDS:
                names.update(Tokenizer.content_words(str(source.get(field) or "")))
            places.update(Tokenizer.content_words(str(source.get("state") or "")))
        return BoilerplateLexicon(
            person_names=frozenset(names), place_names=frozenset(places)
        )


class BipartisanVoteReader:
    """Finds bills with a passage vote that most voting members of both major parties backed."""

    def __init__(
        self,
        client: Elasticsearch,
        parties: dict[str, PartyGroup],
        config: PerspectiveConfig,
    ) -> None:
        self.client = client
        self.parties = parties
        self.min_share = config.perspective_vote_yea_min_share
        self.passage = re.compile(
            config.perspective_passage_question_pattern, re.IGNORECASE
        )

    def read(self, congress: int) -> set[str]:
        hits = scan(
            self.client,
            index=read_alias("rollcall"),
            query={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"congress": congress}},
                            {"exists": {"field": "legislation_id"}},
                        ]
                    }
                },
                "_source": ["legislation_id", "question", "yea_ids", "nay_ids"],
            },
        )
        bills: set[str] = set()
        for hit in hits:
            source = hit["_source"]
            if not self.passage.search(str(source.get("question") or "")):
                continue
            if self.backed_by_both(source.get("yea_ids"), source.get("nay_ids")):
                bills.add(str(source["legislation_id"]))
        return bills

    def backed_by_both(
        self, yea_ids: list[str] | None, nay_ids: list[str] | None
    ) -> bool:
        return all(
            self._yea_share(party, yea_ids or [], nay_ids or []) > self.min_share
            for party in MAJOR_PARTIES
        )

    def _yea_share(
        self, party: PartyGroup, yea_ids: list[str], nay_ids: list[str]
    ) -> float:
        yea = sum(self.parties.get(member) == party for member in yea_ids)
        nay = sum(self.parties.get(member) == party for member in nay_ids)
        return yea / (yea + nay) if yea + nay else 0.0


class MeasureFilter:
    """Drops resolutions and ceremonial measures, which carry no policy approach."""

    def __init__(self, config: PerspectiveConfig) -> None:
        self.types = {kind.lower() for kind in config.perspective_excluded_types}
        self.title = re.compile(
            config.perspective_excluded_title_pattern, re.IGNORECASE
        )

    def is_policy(self, measure_type: str, title: str) -> bool:
        return measure_type.lower() not in self.types and not self.title.search(title)


class CongressCorpusReader:
    """Streams a Congress's policy bills and attaches the primary sponsor's party."""

    def __init__(
        self,
        client: Elasticsearch,
        parties: dict[str, PartyGroup],
        config: PerspectiveConfig,
        measures: MeasureFilter,
        votes: BipartisanVoteReader,
    ) -> None:
        self.client = client
        self.parties = parties
        self.config = config
        self.measures = measures
        self.votes = votes

    def read(self, congress: int) -> CongressCorpus:
        hits = list(
            scan(
                self.client,
                index=read_alias("bill"),
                query={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"source_type": "bill"}},
                                {"term": {"congress": congress}},
                            ]
                        }
                    },
                    "_source": BILL_FIELDS,
                },
            )
        )
        documents = {doc.doc_id: doc for doc in build_topic_documents(hits)}
        voted_bipartisan = self.votes.read(congress)
        bills: dict[str, PerspectiveBill] = {}
        for hit in hits:
            doc_id = str(hit["_id"])
            document = documents.get(doc_id)
            if document is None:
                continue
            source = hit["_source"]
            title = str(source.get("title") or "")
            if not self.measures.is_policy(self._measure_type(source, doc_id), title):
                continue
            full_text = str(source.get(FULL_TEXT_FIELD) or "")
            sponsor_party = self._party(source.get(SPONSOR_FIELD))
            bills[doc_id] = PerspectiveBill(
                doc_id=doc_id,
                title=title,
                text=full_text[: self.config.perspective_text_chars] or document.text,
                sponsor_party=sponsor_party,
                sponsor_id=self._sponsor_id(source.get(SPONSOR_FIELD)),
                subjects=self._subjects(source),
                bipartisan=doc_id in voted_bipartisan
                or self._bipartisan(sponsor_party, source.get(COSPONSOR_FIELD)),
            )
        return CongressCorpus(congress=congress, bills=bills, documents=documents)

    @staticmethod
    def _measure_type(source: dict[str, Any], doc_id: str) -> str:
        """The bill type, read from the document id when the type field is missing."""
        declared = source.get(TYPE_FIELD)
        if declared:
            return str(declared)
        parts = doc_id.split(":")
        return parts[ID_TYPE_POSITION] if len(parts) > ID_TYPE_POSITION else ""

    def _bipartisan(
        self, sponsor_party: PartyGroup | None, cosponsor_ids: list[str] | None
    ) -> bool:
        if sponsor_party not in MAJOR_PARTIES or not cosponsor_ids:
            return False
        other = sum(
            self.parties.get(member) in MAJOR_PARTIES
            and self.parties.get(member) != sponsor_party
            for member in cosponsor_ids
        )
        return other >= self.config.perspective_bipartisan_min_cosponsors

    @staticmethod
    def _sponsor_id(sponsor_ids: list[str] | None) -> str:
        return sponsor_ids[0] if sponsor_ids else ""

    @staticmethod
    def _subjects(source: dict[str, Any]) -> list[str]:
        area = (source.get("policy_area") or {}).get("name")
        listed = (source.get("subjects") or {}).get("legislative_subjects") or []
        names = [str(area)] if area else []
        names.extend(str(item["name"]) for item in listed if item.get("name"))
        return list(dict.fromkeys(names))

    def _party(self, sponsor_ids: list[str] | None) -> PartyGroup | None:
        return self.parties.get(sponsor_ids[0]) if sponsor_ids else None
