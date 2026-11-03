"""Reads metasubject documents from the published topic generation."""

from __future__ import annotations

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan

from cdm.config.topic_analysis import TopicKind
from cdm.store.topic_publication import TopicPublicationStore
from cdm.utils.metasubjects import Metasubject


class MetasubjectRepository:
    def __init__(
        self,
        client: Elasticsearch,
        index: str,
        publications: TopicPublicationStore | None = None,
    ) -> None:
        self.client = client
        self.index = index
        self.publications = publications or TopicPublicationStore(client, index)

    def latest(self) -> list[Metasubject]:
        """All metasubjects of the published model, never a partial new run."""
        run = self.publications.current()
        if run is None:
            return []
        return [
            Metasubject.model_validate(hit["_source"])
            for hit in scan(
                self.client,
                index=self.index,
                allow_partial_search_results=False,
                query={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"kind": TopicKind.METASUBJECT}},
                                {"term": {"model_version": run.model_version}},
                            ]
                        }
                    }
                },
            )
        ]
