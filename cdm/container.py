"""Composition root: the one place that wires configuration into collaborators."""

from __future__ import annotations

from functools import cached_property

from elasticsearch import Elasticsearch
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from cdm.backend.services.admin_service import AdminService
from cdm.backend.services.bill_service import BillService
from cdm.backend.services.committee_service import CommitteeService
from cdm.backend.services.graph_service import GraphService
from cdm.backend.services.member_metasubject_overlay import (
    MemberMetasubjectOverlayBuilder,
)
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.member_subject_overlay import MemberSubjectOverlayBuilder
from cdm.backend.services.member_topic_overlay import MemberTopicOverlayBuilder
from cdm.backend.services.neighborhood_service import NeighborhoodService
from cdm.backend.services.search_service import SearchService
from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.backend.services.sponsored_bills import SponsoredBillReader
from cdm.backend.services.state_service import StateService
from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.backend.services.vote_service import VoteService
from cdm.config import AppConfig
from cdm.store.client import ElasticClientFactory
from cdm.store.embedding_store import EmbeddingStore
from cdm.store.metasubject_override_store import MetasubjectOverrideStore
from cdm.store.metasubject_repository import MetasubjectRepository
from cdm.utils.metasubject_namer import OllamaMetasubjectNamer
from cdm.utils.metasubjects import (
    LargestTopicNamer,
    Metasubject,
    MetasubjectAssigner,
    MetasubjectBuilder,
    MetasubjectNamer,
    MetasubjectOverrides,
    StableIdMatcher,
)
from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_labeler import TopicLabeler


class Container:
    """Builds and caches shared collaborators from one ``AppConfig``.

    Tests and scripts construct a Container with their own config, or replace
    individual providers by assigning to the cached attribute.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @cached_property
    def elastic_client(self) -> Elasticsearch:
        return ElasticClientFactory(self.config.elastic).create()

    @cached_property
    def ollama_client(self) -> OllamaClient:
        return OllamaClient(self.config.ollama)

    @cached_property
    def topic_labeler(self) -> TopicLabeler:
        return TopicLabeler(self.ollama_client)

    def embedding_store(self, model: str | None = None) -> EmbeddingStore:
        return EmbeddingStore(
            self.elastic_client,
            model or self.config.embedding.embedding_model,
            index=self.config.elastic.embeddings_index,
            batch_docs=self.config.embedding.embedding_batch_docs,
        )

    @cached_property
    def metasubject_override_store(self) -> MetasubjectOverrideStore:
        return MetasubjectOverrideStore(
            self.elastic_client, self.config.elastic.metasubject_overrides_index
        )

    @cached_property
    def metasubject_repository(self) -> MetasubjectRepository:
        return MetasubjectRepository(
            self.elastic_client, self.config.elastic.analysis_index
        )

    def metasubject_namer(self, *, use_llm: bool) -> MetasubjectNamer:
        if use_llm:
            return OllamaMetasubjectNamer(self.ollama_client)
        return LargestTopicNamer()

    def metasubject_builder(
        self, namer: MetasubjectNamer, overrides: MetasubjectOverrides | None = None
    ) -> MetasubjectBuilder:
        settings = self.config.metasubject
        return MetasubjectBuilder(
            namer,
            StableIdMatcher(settings.metasubject_match_min_similarity),
            settings.metasubject_target_groups,
            overrides,
        )

    def metasubject_assigner(
        self, metasubjects: list[Metasubject]
    ) -> MetasubjectAssigner:
        return MetasubjectAssigner(
            metasubjects, self.config.metasubject.metasubject_low_confidence_similarity
        )

    @cached_property
    def similar_bill_service(self) -> SimilarBillService:
        return SimilarBillService(self.elastic_client, self.embedding_store())

    @cached_property
    def committee_service(self) -> CommitteeService:
        return CommitteeService(self.elastic_client)

    @cached_property
    def bill_service(self) -> BillService:
        return BillService(self.elastic_client)

    @cached_property
    def vote_service(self) -> VoteService:
        return VoteService(self.elastic_client)

    @cached_property
    def state_service(self) -> StateService:
        return StateService(self.elastic_client)

    @cached_property
    def search_service(self) -> SearchService:
        return SearchService(self.elastic_client, self.state_service)

    @cached_property
    def subject_service(self) -> SubjectService:
        return SubjectService(self.elastic_client)

    @cached_property
    def topic_service(self) -> TopicService:
        return TopicService(
            self.elastic_client, self.config.elastic.analysis_index, self.subject_service
        )

    @cached_property
    def member_service(self) -> MemberService:
        return MemberService(
            self.elastic_client, self.search_service, self.topic_service
        )

    @cached_property
    def jobs_engine(self) -> Engine:
        return create_engine(f"sqlite:///{self.config.ledger.job_db_path}")

    @cached_property
    def admin_service(self) -> AdminService:
        return AdminService(self.elastic_client, self.config, self.jobs_engine)

    @cached_property
    def graph_service(self) -> GraphService:
        return GraphService(self.elastic_client, self.member_service)

    @cached_property
    def sponsored_bills(self) -> SponsoredBillReader:
        return SponsoredBillReader(self.elastic_client)

    @cached_property
    def neighborhood_service(self) -> NeighborhoodService:
        return NeighborhoodService(
            self.graph_service,
            self.member_service,
            MemberTopicOverlayBuilder(self.sponsored_bills, self.topic_service),
            MemberSubjectOverlayBuilder(self.elastic_client),
            MemberMetasubjectOverlayBuilder(self.sponsored_bills, self.topic_service),
        )
