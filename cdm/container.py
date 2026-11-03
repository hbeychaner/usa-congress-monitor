"""Composition root for API reads and durable job submission."""

from __future__ import annotations

from functools import cached_property

from elasticsearch import Elasticsearch
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from cdm.backend.services.admin_service import AdminService
from cdm.backend.services.bill_service import BillService
from cdm.backend.services.bill_vote_index import BillVoteIndex
from cdm.backend.services.committee_service import CommitteeService
from cdm.backend.services.graph_service import GraphService
from cdm.backend.services.member_metasubject_overlay import (
    MemberMetasubjectOverlayBuilder,
)
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.member_subject_overlay import MemberSubjectOverlayBuilder
from cdm.backend.services.member_topic_overlay import MemberTopicOverlayBuilder
from cdm.backend.services.neighborhood_service import NeighborhoodService
from cdm.backend.services.party_service import PartyService
from cdm.backend.services.search_service import SearchService
from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.backend.services.sponsored_bills import SponsoredBillReader
from cdm.backend.services.state_service import StateService
from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_neighborhood_service import TopicNeighborhoodService
from cdm.backend.services.topic_service import TopicService
from cdm.backend.services.topic_sponsors import AssignedBillReader, TopicSponsorReader
from cdm.backend.services.vote_breakdown_service import VoteBreakdownService
from cdm.backend.services.vote_service import VoteService
from cdm.config import AppConfig
from cdm.graph.store import GraphStore
from cdm.jobs.analytics import AnalyticsJobs
from cdm.jobs.store import JobStore
from cdm.store.client import ElasticClientFactory
from cdm.store.embedding_store import EmbeddingStore
from cdm.store.perspective_repository import PerspectiveRepository
from cdm.store.topic_publication import TopicPublicationStore
from cdm.topics.retirement import RetirementReporter
from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_labeler import TopicLabeler
from cdm.workers.celery_app import celery_app
from cdm.workers.dispatch import JobDispatcher, JobSubmitter


class Container:
    """Builds and caches shared collaborators from one ``AppConfig``.

    Tests and scripts construct a Container with their own config, or replace
    individual providers by assigning to the cached attribute.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @cached_property
    def job_store(self) -> JobStore:
        return JobStore(self.config.ledger.job_db_path, repair=False)

    @cached_property
    def job_dispatcher(self) -> JobDispatcher:
        return JobDispatcher(celery_app, self.config.queue)

    @cached_property
    def job_submitter(self) -> JobSubmitter:
        return JobSubmitter(self.job_store, self.job_dispatcher)

    @cached_property
    def analytics_jobs(self) -> AnalyticsJobs:
        return AnalyticsJobs(self.job_store, self.job_dispatcher)

    @cached_property
    def elastic_client(self) -> Elasticsearch:
        return ElasticClientFactory(self.config.elastic).create()

    @cached_property
    def ollama_client(self) -> OllamaClient:
        return OllamaClient(self.config.ollama)

    @cached_property
    def topic_labeler(self) -> TopicLabeler:
        return TopicLabeler(self.ollama_client)

    def embedding_store(
        self,
        model: str | None = None,
        *,
        index: str | None = None,
    ) -> EmbeddingStore:
        model = model or self.config.embedding.embedding_model
        return EmbeddingStore(
            self.elastic_client,
            model,
            index=index
            if index is not None
            else EmbeddingStore.namespace(self.config.elastic.embeddings_index, model),
            batch_docs=self.config.embedding.embedding_batch_docs,
        )

    @cached_property
    def topic_publications(self) -> TopicPublicationStore:
        return TopicPublicationStore(
            self.elastic_client, self.config.elastic.analysis_index
        )

    @cached_property
    def retirement_reporter(self) -> RetirementReporter:
        return RetirementReporter(
            self.topic_publications,
            GraphStore(self.elastic_client),
            self.config.elastic.embeddings_index,
        )

    @cached_property
    def perspective_repository(self) -> PerspectiveRepository:
        return PerspectiveRepository(
            self.elastic_client, self.config.elastic.analysis_index
        )

    @cached_property
    def party_service(self) -> PartyService:
        return PartyService(
            self.perspective_repository,
            self.config.perspective,
            self.topic_publications,
        )

    @cached_property
    def similar_bill_service(self) -> SimilarBillService:
        return SimilarBillService(
            self.elastic_client,
            self.embedding_store(index=self.config.elastic.embeddings_index),
            self.topic_publications,
        )

    @cached_property
    def committee_service(self) -> CommitteeService:
        return CommitteeService(self.elastic_client)

    @cached_property
    def bill_service(self) -> BillService:
        return BillService(
            self.elastic_client,
            BillVoteIndex(self.elastic_client, self.config.query_reads),
            self.config.query_reads,
        )

    @cached_property
    def vote_service(self) -> VoteService:
        return VoteService(self.elastic_client)

    @cached_property
    def vote_breakdown_service(self) -> VoteBreakdownService:
        return VoteBreakdownService(self.elastic_client)

    @cached_property
    def state_service(self) -> StateService:
        return StateService(self.elastic_client)

    @cached_property
    def search_service(self) -> SearchService:
        return SearchService(
            self.elastic_client, self.state_service, self.config.query_reads
        )

    @cached_property
    def subject_service(self) -> SubjectService:
        return SubjectService(self.elastic_client)

    @cached_property
    def topic_service(self) -> TopicService:
        return TopicService(
            self.elastic_client,
            self.config.elastic.analysis_index,
            self.subject_service,
            self.topic_publications,
        )

    @cached_property
    def member_service(self) -> MemberService:
        return MemberService(
            self.elastic_client, self.search_service, self.config.query_reads
        )

    @cached_property
    def jobs_engine(self) -> Engine:
        return create_engine(f"sqlite:///{self.config.ledger.job_db_path}")

    @cached_property
    def admin_service(self) -> AdminService:
        return AdminService(self.elastic_client, self.config, self.jobs_engine)

    @cached_property
    def graph_service(self) -> GraphService:
        return GraphService(
            GraphStore(self.elastic_client),
            self.member_service,
            self.topic_publications,
            self.config.query_reads,
        )

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

    @cached_property
    def topic_neighborhood_service(self) -> TopicNeighborhoodService:
        return TopicNeighborhoodService(
            self.neighborhood_service,
            self.topic_service,
            AssignedBillReader(self.elastic_client, self.config.elastic.analysis_index),
            TopicSponsorReader(self.elastic_client),
        )
