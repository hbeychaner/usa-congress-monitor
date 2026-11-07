"""Composition root for Celery workers and job-submitting scripts."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property

from elasticsearch import Elasticsearch

from cdm.config.topic_analysis import TopicTrainingOptions
from cdm.graph.job import GraphBuildJob
from cdm.graph.live_repair import LiveGraphRepair
from cdm.graph.promotion import VotingGraphPromotion
from cdm.graph.repair import GraphRepairCapture, GraphRepairRehearsal
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.topics import TopicModelReader
from cdm.jobs.analytics import AnalysisProgress, PerspectiveRequest
from cdm.perspectives.boilerplate import BoilerplateLearner
from cdm.perspectives.builder import PerspectiveBuilder
from cdm.perspectives.clustering import PerspectiveClusterer
from cdm.perspectives.corpus import (
    BipartisanVoteReader,
    CongressCorpusReader,
    MeasureFilter,
    MemberNameReader,
    MemberPartyReader,
)
from cdm.perspectives.evidence import SubjectContrast, TermEvidence
from cdm.perspectives.job import PerspectiveBuildJob
from cdm.perspectives.labeler import PerspectiveLabeler
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.perspectives.runner import PerspectiveRunner
from cdm.perspectives.summarizer import ApproachSummarizer
from cdm.perspectives.terms import DistinctiveTerms, Tokenizer
from cdm.store.metasubject_override_store import MetasubjectOverrideStore
from cdm.store.metasubject_repository import MetasubjectRepository
from cdm.topics.training import TopicTrainingJob
from cdm.utils.metasubject_namer import OllamaMetasubjectNamer, OllamaNameDisambiguator
from cdm.utils.metasubjects import (
    LargestTopicNamer,
    MetasubjectAssigner,
    MetasubjectBuilder,
    StableIdMatcher,
)
from cdm.utils.topic_modeler import TopicModeler
from cdm.workers.analytics_runner import AnalyticsJobRunner
from cdm.workers.operations import OperationsContainer


class WorkerContainer(OperationsContainer):
    """Adds ingestion and analysis construction to the read/submission root."""

    @cached_property
    def graph_repair_capture(self) -> GraphRepairCapture:
        return GraphRepairCapture(self.elastic_client, self.config.graph_repair)

    def graph_repair_rehearsal(self, url: str) -> GraphRepairRehearsal:
        return GraphRepairRehearsal(Elasticsearch(url, request_timeout=120))

    def graph_source_repair(self, staging_url: str | None = None) -> LiveGraphRepair:
        return LiveGraphRepair(
            self.graph_repair_capture,
            self.graph_repair_rehearsal(staging_url)
            if staging_url is not None
            else None,
        )

    @cached_property
    def voting_graph_promotion(self) -> VotingGraphPromotion:
        return VotingGraphPromotion(self.graph_source_repair())

    def topic_training_job(
        self, options: TopicTrainingOptions, report: Callable[[AnalysisProgress], None]
    ) -> TopicTrainingJob:
        use_llm = (
            not options.no_llm_labels
            and not options.preview
            and not options.publish_version
        )
        model = options.embedding_model or self.config.embedding.embedding_model
        settings = self.config.metasubject
        return TopicTrainingJob(
            self.elastic_client,
            self.topic_publications,
            self.metasubject_repository,
            TopicModeler(
                embedding_model=model,
                min_topic_size=options.min_topic_size,
                embedding_store=None
                if options.preview or options.publish_version
                else self.embedding_store(model),
            ),
            MetasubjectBuilder(
                OllamaMetasubjectNamer(self.ollama_client)
                if use_llm
                else LargestTopicNamer(),
                StableIdMatcher(settings.metasubject_match_min_similarity),
                settings.metasubject_target_groups,
                None
                if options.publish_version
                else self.metasubject_override_store.current(),
                OllamaNameDisambiguator(self.ollama_client) if use_llm else None,
                settings.metasubject_name_carry_max_size_ratio,
            ),
            lambda groups: MetasubjectAssigner(
                groups, settings.metasubject_low_confidence_similarity
            ),
            options,
            report,
            self.topic_labeler if use_llm else None,
        )

    def graph_build_job(
        self, report: Callable[[AnalysisProgress], None]
    ) -> GraphBuildJob:
        return GraphBuildJob(
            GraphStore(self.elastic_client),
            BillSignatureReader(self.elastic_client),
            RollCallReader(self.elastic_client),
            self.topic_model_reader,
            report,
        )

    def perspective_build_job(
        self, request: PerspectiveRequest, report: Callable[[AnalysisProgress], None]
    ) -> PerspectiveBuildJob:
        return PerspectiveBuildJob(
            self.perspective_runner(
                use_llm=not request.no_llm_labels and not request.dry_run
            ),
            self.perspective_repository,
            report,
        )

    @cached_property
    def topic_model_reader(self) -> TopicModelReader:
        return TopicModelReader(
            self.elastic_client,
            self.config.elastic.analysis_index,
            self.topic_publications,
        )

    @cached_property
    def metasubject_override_store(self) -> MetasubjectOverrideStore:
        return MetasubjectOverrideStore(
            self.elastic_client, self.config.elastic.metasubject_overrides_index
        )

    @cached_property
    def metasubject_repository(self) -> MetasubjectRepository:
        return MetasubjectRepository(
            self.elastic_client,
            self.config.elastic.analysis_index,
            self.topic_publications,
        )

    @cached_property
    def congress_corpus_reader(self) -> CongressCorpusReader:
        parties = MemberPartyReader(self.elastic_client).read()
        return CongressCorpusReader(
            self.elastic_client,
            parties,
            self.config.perspective,
            MeasureFilter(self.config.perspective),
            BipartisanVoteReader(self.elastic_client, parties, self.config.perspective),
        )

    @cached_property
    def boilerplate_learner(self) -> BoilerplateLearner:
        base = Tokenizer(
            MemberNameReader(self.elastic_client).read(),
            self.config.perspective.perspective_max_ngram,
        )
        return BoilerplateLearner(self.config.perspective, base)

    def perspective_builder(
        self, *, use_llm: bool, lexicon: BoilerplateLexicon
    ) -> PerspectiveBuilder:
        config = self.config.perspective
        tokenizer = Tokenizer(lexicon, config.perspective_max_ngram)
        return PerspectiveBuilder(
            config,
            PerspectiveClusterer(config, tokenizer),
            DistinctiveTerms(config, tokenizer),
            TermEvidence(config, tokenizer),
            SubjectContrast(config),
            PerspectiveLabeler(self.ollama_client, enabled=use_llm),
            ApproachSummarizer(self.ollama_client, enabled=use_llm),
        )

    def perspective_runner(self, *, use_llm: bool) -> PerspectiveRunner:
        return PerspectiveRunner(
            self.config.perspective,
            self.topic_model_reader,
            self.congress_corpus_reader,
            self.boilerplate_learner,
            lambda lexicon: self.perspective_builder(use_llm=use_llm, lexicon=lexicon),
        )

    @cached_property
    def analytics_runner(self) -> AnalyticsJobRunner:
        return AnalyticsJobRunner(
            self.job_store,
            self.topic_training_job,
            self.graph_build_job,
            self.perspective_build_job,
        )
