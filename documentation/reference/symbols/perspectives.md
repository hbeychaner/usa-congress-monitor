# perspectives source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/perspectives/__init__.py

[Source](../../../cdm/perspectives/__init__.py)

No declarations in this module.


## cdm/perspectives/boilerplate.py

[Source](../../../cdm/perspectives/boilerplate.py)

- class: [`BoilerplateLearner()`](../../../cdm/perspectives/boilerplate.py#L18)
- function: [`BoilerplateLearner.__init__(self, config: PerspectiveConfig, base: Tokenizer) -> None`](../../../cdm/perspectives/boilerplate.py#L21)
- function: [`BoilerplateLearner.learn(self, texts_by_topic: Mapping[int, Sequence[str]]) -> BoilerplateLexicon`](../../../cdm/perspectives/boilerplate.py#L25)
- function: [`BoilerplateLearner._rare_names(self, topics: list[Sequence[str]]) -> frozenset[str]`](../../../cdm/perspectives/boilerplate.py#L36)
- function: [`BoilerplateLearner._spread(self, analyzer: Analyzer, topics: list[Sequence[str]], *, corpus_cap: bool) -> frozenset[str]`](../../../cdm/perspectives/boilerplate.py#L52)

## cdm/perspectives/builder.py

[Source](../../../cdm/perspectives/builder.py)

- class: [`GroupSummary()`](../../../cdm/perspectives/builder.py#L35)
- field: [`GroupSummary.sample_titles: list[str]`](../../../cdm/perspectives/builder.py#L36)
- field: [`GroupSummary.summary: str`](../../../cdm/perspectives/builder.py#L37)
- function: [`_log_odds(hits: int, total: int) -> float`](../../../cdm/perspectives/builder.py#L40)
- class: [`PerspectiveBuilder()`](../../../cdm/perspectives/builder.py#L44)
- function: [`PerspectiveBuilder.__init__(self, config: PerspectiveConfig, clusterer: PerspectiveClusterer, terms: DistinctiveTerms, evidence: TermEvidence, subjects: SubjectContrast, labeler: PerspectiveLabeler, summarizer: ApproachSummarizer) -> None`](../../../cdm/perspectives/builder.py#L47)
- function: [`PerspectiveBuilder.build(self, *, congress: int, topic_id: int, topic_label: str, bills: list[PerspectiveBill]) -> TopicPerspectives`](../../../cdm/perspectives/builder.py#L65)
- function: [`PerspectiveBuilder._party_bills(bills: list[PerspectiveBill]) -> list[PartyBillCount]`](../../../cdm/perspectives/builder.py#L112)
- function: [`PerspectiveBuilder._bilateral(self, topic_label: str, bills: list[PerspectiveBill]) -> BilateralSupport \| None`](../../../cdm/perspectives/builder.py#L118)
- function: [`PerspectiveBuilder._pool(self) -> int`](../../../cdm/perspectives/builder.py#L150)
- function: [`PerspectiveBuilder._supported(self, candidates: list[str], bills: list[PerspectiveBill]) -> list[TermUse]`](../../../cdm/perspectives/builder.py#L153)
- function: [`PerspectiveBuilder._summary(self, topic_label: str, group: str, terms: list[TermUse], subjects: list[SubjectUse], bills: list[PerspectiveBill]) -> GroupSummary`](../../../cdm/perspectives/builder.py#L161)
- function: [`PerspectiveBuilder._party_terms(self, topic_label: str, bills: list[PerspectiveBill]) -> list[PartyTerms]`](../../../cdm/perspectives/builder.py#L184)
- field: [`PerspectiveBuilder._party_terms.result: list[PartyTerms]`](../../../cdm/perspectives/builder.py#L203)
- function: [`PerspectiveBuilder._perspective(self, congress: int, topic_id: int, topic_label: str, cluster: int, clusters: ClusterResult, bills: list[PerspectiveBill], terms: list[str]) -> Perspective`](../../../cdm/perspectives/builder.py#L224)
- function: [`PerspectiveBuilder._parties(members: list[PerspectiveBill], everyone: list[PerspectiveBill]) -> list[PartyShare]`](../../../cdm/perspectives/builder.py#L254)
- field: [`PerspectiveBuilder._parties.shares: list[PartyShare]`](../../../cdm/perspectives/builder.py#L259)

## cdm/perspectives/clustering.py

[Source](../../../cdm/perspectives/clustering.py)

- class: [`ClusterResult()`](../../../cdm/perspectives/clustering.py#L28)
- field: [`ClusterResult.labels: Labels`](../../../cdm/perspectives/clustering.py#L29)
- field: [`ClusterResult.silhouette: float`](../../../cdm/perspectives/clustering.py#L30)
- field: [`ClusterResult.stability: float`](../../../cdm/perspectives/clustering.py#L31)
- field: [`ClusterResult.features: Matrix`](../../../cdm/perspectives/clustering.py#L32)
- function: [`ClusterResult.count(self) -> int`](../../../cdm/perspectives/clustering.py#L35)
- function: [`ClusterResult.nearest(self, cluster: int, limit: int) -> list[int]`](../../../cdm/perspectives/clustering.py#L38)
- class: [`PerspectiveClusterer()`](../../../cdm/perspectives/clustering.py#L46)
- function: [`PerspectiveClusterer.__init__(self, config: PerspectiveConfig, tokenizer: Tokenizer) -> None`](../../../cdm/perspectives/clustering.py#L49)
- function: [`PerspectiveClusterer.features(self, texts: Sequence[str]) -> Matrix \| None`](../../../cdm/perspectives/clustering.py#L53)
- function: [`PerspectiveClusterer.cluster(self, texts: Sequence[str]) -> ClusterResult \| None`](../../../cdm/perspectives/clustering.py#L76)
- field: [`PerspectiveClusterer.cluster.best: tuple[int, Labels, float] \| None`](../../../cdm/perspectives/clustering.py#L86)
- function: [`PerspectiveClusterer._fit(features: Matrix, count: int, seed: int) -> Labels`](../../../cdm/perspectives/clustering.py#L105)
- function: [`PerspectiveClusterer._stability(self, features: Matrix, count: int, labels: Labels) -> float`](../../../cdm/perspectives/clustering.py#L109)

## cdm/perspectives/corpus.py

[Source](../../../cdm/perspectives/corpus.py)

- class: [`CongressCorpus()`](../../../cdm/perspectives/corpus.py#L42)
- field: [`CongressCorpus.congress: int`](../../../cdm/perspectives/corpus.py#L45)
- field: [`CongressCorpus.bills: dict[str, PerspectiveBill]`](../../../cdm/perspectives/corpus.py#L46)
- field: [`CongressCorpus.documents: dict[str, TopicDocument]`](../../../cdm/perspectives/corpus.py#L47)
- class: [`MemberPartyReader()`](../../../cdm/perspectives/corpus.py#L50)
- function: [`MemberPartyReader.__init__(self, client: Elasticsearch) -> None`](../../../cdm/perspectives/corpus.py#L53)
- function: [`MemberPartyReader.read(self) -> dict[str, PartyGroup]`](../../../cdm/perspectives/corpus.py#L56)
- field: [`MemberPartyReader.read.parties: dict[str, PartyGroup]`](../../../cdm/perspectives/corpus.py#L57)
- class: [`MemberNameReader()`](../../../cdm/perspectives/corpus.py#L75)
- function: [`MemberNameReader.__init__(self, client: Elasticsearch) -> None`](../../../cdm/perspectives/corpus.py#L78)
- function: [`MemberNameReader.read(self) -> BoilerplateLexicon`](../../../cdm/perspectives/corpus.py#L81)
- field: [`MemberNameReader.read.names: set[str]`](../../../cdm/perspectives/corpus.py#L82)
- field: [`MemberNameReader.read.places: set[str]`](../../../cdm/perspectives/corpus.py#L83)
- class: [`BipartisanVoteReader()`](../../../cdm/perspectives/corpus.py#L102)
- function: [`BipartisanVoteReader.__init__(self, client: Elasticsearch, parties: dict[str, PartyGroup], config: PerspectiveConfig) -> None`](../../../cdm/perspectives/corpus.py#L105)
- function: [`BipartisanVoteReader.read(self, congress: int) -> set[str]`](../../../cdm/perspectives/corpus.py#L118)
- field: [`BipartisanVoteReader.read.bills: set[str]`](../../../cdm/perspectives/corpus.py#L134)
- function: [`BipartisanVoteReader.backed_by_both(self, yea_ids: list[str] \| None, nay_ids: list[str] \| None) -> bool`](../../../cdm/perspectives/corpus.py#L143)
- function: [`BipartisanVoteReader._yea_share(self, party: PartyGroup, yea_ids: list[str], nay_ids: list[str]) -> float`](../../../cdm/perspectives/corpus.py#L151)
- class: [`MeasureFilter()`](../../../cdm/perspectives/corpus.py#L159)
- function: [`MeasureFilter.__init__(self, config: PerspectiveConfig) -> None`](../../../cdm/perspectives/corpus.py#L162)
- function: [`MeasureFilter.is_policy(self, measure_type: str, title: str) -> bool`](../../../cdm/perspectives/corpus.py#L168)
- class: [`CongressCorpusReader()`](../../../cdm/perspectives/corpus.py#L172)
- function: [`CongressCorpusReader.__init__(self, client: Elasticsearch, parties: dict[str, PartyGroup], config: PerspectiveConfig, measures: MeasureFilter, votes: BipartisanVoteReader) -> None`](../../../cdm/perspectives/corpus.py#L175)
- function: [`CongressCorpusReader.read(self, congress: int) -> CongressCorpus`](../../../cdm/perspectives/corpus.py#L189)
- field: [`CongressCorpusReader.read.bills: dict[str, PerspectiveBill]`](../../../cdm/perspectives/corpus.py#L209)
- function: [`CongressCorpusReader._measure_type(source: dict[str, Any], doc_id: str) -> str`](../../../cdm/perspectives/corpus.py#L234)
- function: [`CongressCorpusReader._bipartisan(self, sponsor_party: PartyGroup \| None, cosponsor_ids: list[str] \| None) -> bool`](../../../cdm/perspectives/corpus.py#L242)
- function: [`CongressCorpusReader._sponsor_id(sponsor_ids: list[str] \| None) -> str`](../../../cdm/perspectives/corpus.py#L255)
- function: [`CongressCorpusReader._subjects(source: dict[str, Any]) -> list[str]`](../../../cdm/perspectives/corpus.py#L259)
- function: [`CongressCorpusReader._party(self, sponsor_ids: list[str] \| None) -> PartyGroup \| None`](../../../cdm/perspectives/corpus.py#L266)

## cdm/perspectives/evidence.py

[Source](../../../cdm/perspectives/evidence.py)

- class: [`TermEvidence()`](../../../cdm/perspectives/evidence.py#L18)
- function: [`TermEvidence.__init__(self, config: PerspectiveConfig, tokenizer: Tokenizer) -> None`](../../../cdm/perspectives/evidence.py#L21)
- function: [`TermEvidence.describe(self, terms: Sequence[str], bills: Sequence[PerspectiveBill]) -> list[TermUse]`](../../../cdm/perspectives/evidence.py#L25)
- field: [`TermEvidence.describe.users: dict[str, list[PerspectiveBill]]`](../../../cdm/perspectives/evidence.py#L29)
- field: [`TermEvidence.describe.described: list[TermUse]`](../../../cdm/perspectives/evidence.py#L34)
- field: [`TermEvidence.describe.seen: set[frozenset[str]]`](../../../cdm/perspectives/evidence.py#L35)
- class: [`SubjectContrast()`](../../../cdm/perspectives/evidence.py#L63)
- function: [`SubjectContrast.__init__(self, config: PerspectiveConfig) -> None`](../../../cdm/perspectives/evidence.py#L66)
- function: [`SubjectContrast.top(self, inside: Sequence[PerspectiveBill], outside: Sequence[PerspectiveBill]) -> list[SubjectUse]`](../../../cdm/perspectives/evidence.py#L69)
- field: [`SubjectContrast.top.scored: list[tuple[float, SubjectUse]]`](../../../cdm/perspectives/evidence.py#L74)
- field: [`SubjectContrast.top.kept: list[SubjectUse]`](../../../cdm/perspectives/evidence.py#L91)
- function: [`SubjectContrast._same_idea(first: str, second: str) -> bool`](../../../cdm/perspectives/evidence.py#L100)

## cdm/perspectives/job.py

[Source](../../../cdm/perspectives/job.py)

- class: [`PerspectiveBuildJob()`](../../../cdm/perspectives/job.py#L11)
- function: [`PerspectiveBuildJob.__init__(self, runner: PerspectiveRunner, repository: PerspectiveRepository, report: Callable[[AnalysisProgress], None]) -> None`](../../../cdm/perspectives/job.py#L12)
- function: [`PerspectiveBuildJob.run(self, request: PerspectiveRequest) -> None`](../../../cdm/perspectives/job.py#L22)

## cdm/perspectives/labeler.py

[Source](../../../cdm/perspectives/labeler.py)

- class: [`PerspectiveLabelConfig(BaseModel)`](../../../cdm/perspectives/labeler.py#L12)
- field: [`PerspectiveLabelConfig.system_prompt: str`](../../../cdm/perspectives/labeler.py#L13)
- field: [`PerspectiveLabelConfig.max_words: int`](../../../cdm/perspectives/labeler.py#L23)
- field: [`PerspectiveLabelConfig.title_chars: int`](../../../cdm/perspectives/labeler.py#L24)
- class: [`PerspectiveLabeler()`](../../../cdm/perspectives/labeler.py#L27)
- function: [`PerspectiveLabeler.__init__(self, ollama: OllamaClient, *, enabled: bool=True, config: PerspectiveLabelConfig \| None=None) -> None`](../../../cdm/perspectives/labeler.py#L30)
- function: [`PerspectiveLabeler.label(self, topic: str, terms: list[str], titles: list[str]) -> LabelResult`](../../../cdm/perspectives/labeler.py#L47)

## cdm/perspectives/lexicon.py

[Source](../../../cdm/perspectives/lexicon.py)

- class: [`BoilerplateLexicon()`](../../../cdm/perspectives/lexicon.py#L9)
- field: [`BoilerplateLexicon.words: frozenset[str]`](../../../cdm/perspectives/lexicon.py#L10)
- field: [`BoilerplateLexicon.phrases: frozenset[str]`](../../../cdm/perspectives/lexicon.py#L11)
- field: [`BoilerplateLexicon.person_names: frozenset[str]`](../../../cdm/perspectives/lexicon.py#L12)
- field: [`BoilerplateLexicon.place_names: frozenset[str]`](../../../cdm/perspectives/lexicon.py#L13)
- function: [`BoilerplateLexicon.with_names(self, person_names: frozenset[str]) -> BoilerplateLexicon`](../../../cdm/perspectives/lexicon.py#L15)
- function: [`BoilerplateLexicon.with_terms(self, words: frozenset[str], phrases: frozenset[str]) -> BoilerplateLexicon`](../../../cdm/perspectives/lexicon.py#L20)

## cdm/perspectives/models.py

[Source](../../../cdm/perspectives/models.py)

- field: [`MAJOR_PARTIES: tuple[PartyGroup, ...]`](../../../cdm/perspectives/models.py#L11)
- class: [`PerspectiveBill(ResponseModel)`](../../../cdm/perspectives/models.py#L14)
- field: [`PerspectiveBill.doc_id: str`](../../../cdm/perspectives/models.py#L17)
- field: [`PerspectiveBill.title: str`](../../../cdm/perspectives/models.py#L18)
- field: [`PerspectiveBill.text: str`](../../../cdm/perspectives/models.py#L19)
- field: [`PerspectiveBill.sponsor_party: PartyGroup \| None`](../../../cdm/perspectives/models.py#L20)
- field: [`PerspectiveBill.sponsor_id: str`](../../../cdm/perspectives/models.py#L21)
- field: [`PerspectiveBill.subjects: list[str]`](../../../cdm/perspectives/models.py#L23)
- field: [`PerspectiveBill.bipartisan: bool`](../../../cdm/perspectives/models.py#L25)
- class: [`PartyShare(ResponseModel)`](../../../cdm/perspectives/models.py#L28)
- field: [`PartyShare.party: PartyGroup`](../../../cdm/perspectives/models.py#L31)
- field: [`PartyShare.bills: int`](../../../cdm/perspectives/models.py#L32)
- field: [`PartyShare.share: float`](../../../cdm/perspectives/models.py#L33)
- field: [`PartyShare.lean: float`](../../../cdm/perspectives/models.py#L35)
- class: [`Perspective(LabelProvenance)`](../../../cdm/perspectives/models.py#L38)
- field: [`Perspective.congress: int`](../../../cdm/perspectives/models.py#L43)
- field: [`Perspective.topic_id: int`](../../../cdm/perspectives/models.py#L44)
- field: [`Perspective.perspective_id: int`](../../../cdm/perspectives/models.py#L45)
- field: [`Perspective.label: str`](../../../cdm/perspectives/models.py#L46)
- field: [`Perspective.size: int`](../../../cdm/perspectives/models.py#L47)
- field: [`Perspective.terms: list[str]`](../../../cdm/perspectives/models.py#L48)
- field: [`Perspective.sample_titles: list[str]`](../../../cdm/perspectives/models.py#L49)
- field: [`Perspective.parties: list[PartyShare]`](../../../cdm/perspectives/models.py#L50)
- class: [`BillRef(ResponseModel)`](../../../cdm/perspectives/models.py#L53)
- field: [`BillRef.doc_id: str`](../../../cdm/perspectives/models.py#L54)
- field: [`BillRef.title: str`](../../../cdm/perspectives/models.py#L55)
- class: [`TermUse(ResponseModel)`](../../../cdm/perspectives/models.py#L58)
- field: [`TermUse.term: str`](../../../cdm/perspectives/models.py#L61)
- field: [`TermUse.bills: int`](../../../cdm/perspectives/models.py#L62)
- field: [`TermUse.sponsors: int`](../../../cdm/perspectives/models.py#L63)
- field: [`TermUse.examples: list[BillRef]`](../../../cdm/perspectives/models.py#L64)
- class: [`SubjectUse(ResponseModel)`](../../../cdm/perspectives/models.py#L67)
- field: [`SubjectUse.name: str`](../../../cdm/perspectives/models.py#L70)
- field: [`SubjectUse.bills: int`](../../../cdm/perspectives/models.py#L71)
- field: [`SubjectUse.share: float`](../../../cdm/perspectives/models.py#L72)
- class: [`PartyTerms(ResponseModel)`](../../../cdm/perspectives/models.py#L75)
- field: [`PartyTerms.party: PartyGroup`](../../../cdm/perspectives/models.py#L78)
- field: [`PartyTerms.bills: int`](../../../cdm/perspectives/models.py#L79)
- field: [`PartyTerms.terms: list[TermUse]`](../../../cdm/perspectives/models.py#L80)
- field: [`PartyTerms.subjects: list[SubjectUse]`](../../../cdm/perspectives/models.py#L81)
- field: [`PartyTerms.sample_titles: list[str]`](../../../cdm/perspectives/models.py#L82)
- field: [`PartyTerms.summary: str`](../../../cdm/perspectives/models.py#L83)
- class: [`BilateralSupport(ResponseModel)`](../../../cdm/perspectives/models.py#L86)
- field: [`BilateralSupport.bills: int`](../../../cdm/perspectives/models.py#L89)
- field: [`BilateralSupport.bipartisan_bills: int`](../../../cdm/perspectives/models.py#L90)
- field: [`BilateralSupport.share: float`](../../../cdm/perspectives/models.py#L91)
- field: [`BilateralSupport.bilateral: bool`](../../../cdm/perspectives/models.py#L92)
- field: [`BilateralSupport.terms: list[TermUse]`](../../../cdm/perspectives/models.py#L94)
- field: [`BilateralSupport.subjects: list[SubjectUse]`](../../../cdm/perspectives/models.py#L95)
- field: [`BilateralSupport.sample_titles: list[str]`](../../../cdm/perspectives/models.py#L96)
- field: [`BilateralSupport.summary: str`](../../../cdm/perspectives/models.py#L98)
- class: [`PartyBillCount(ResponseModel)`](../../../cdm/perspectives/models.py#L101)
- field: [`PartyBillCount.party: PartyGroup`](../../../cdm/perspectives/models.py#L104)
- field: [`PartyBillCount.bills: int`](../../../cdm/perspectives/models.py#L105)
- class: [`TopicPerspectives(ResponseModel)`](../../../cdm/perspectives/models.py#L108)
- field: [`TopicPerspectives.congress: int`](../../../cdm/perspectives/models.py#L111)
- field: [`TopicPerspectives.topic_id: int`](../../../cdm/perspectives/models.py#L112)
- field: [`TopicPerspectives.topic_label: str`](../../../cdm/perspectives/models.py#L113)
- field: [`TopicPerspectives.bills: int`](../../../cdm/perspectives/models.py#L114)
- field: [`TopicPerspectives.party_bills: list[PartyBillCount]`](../../../cdm/perspectives/models.py#L115)
- field: [`TopicPerspectives.silhouette: float \| None`](../../../cdm/perspectives/models.py#L116)
- field: [`TopicPerspectives.stability: float \| None`](../../../cdm/perspectives/models.py#L117)
- field: [`TopicPerspectives.passed: bool`](../../../cdm/perspectives/models.py#L118)
- field: [`TopicPerspectives.party_terms: list[PartyTerms]`](../../../cdm/perspectives/models.py#L119)
- field: [`TopicPerspectives.bilateral: BilateralSupport \| None`](../../../cdm/perspectives/models.py#L120)
- field: [`TopicPerspectives.perspectives: list[Perspective]`](../../../cdm/perspectives/models.py#L121)
- field: [`TopicPerspectives.skipped_reason: str`](../../../cdm/perspectives/models.py#L122)

## cdm/perspectives/runner.py

[Source](../../../cdm/perspectives/runner.py)

- class: [`NoTopicModelError(RuntimeError)`](../../../cdm/perspectives/runner.py#L20)
- class: [`PerspectiveRunner()`](../../../cdm/perspectives/runner.py#L24)
- function: [`PerspectiveRunner.__init__(self, config: PerspectiveConfig, topics: TopicModelReader, corpus: CongressCorpusReader, learner: BoilerplateLearner, builders: BuilderFactory) -> None`](../../../cdm/perspectives/runner.py#L27)
- function: [`PerspectiveRunner.source_version(self) -> str`](../../../cdm/perspectives/runner.py#L41)
- function: [`PerspectiveRunner.run(self, congress: int, model_version: str, *, topic_ids: list[int] \| None=None, top_topics: int \| None=None, on_topic: TopicCallback \| None=None) -> list[TopicPerspectives]`](../../../cdm/perspectives/runner.py#L47)
- field: [`PerspectiveRunner.run.bills_by_topic: defaultdict[int, list[str]]`](../../../cdm/perspectives/runner.py#L59)
- field: [`PerspectiveRunner.run.results: list[TopicPerspectives]`](../../../cdm/perspectives/runner.py#L70)
- function: [`PerspectiveRunner._selected(self, bills_by_topic: dict[int, list[str]], topic_ids: list[int] \| None, top_topics: int \| None) -> list[int]`](../../../cdm/perspectives/runner.py#L83)

## cdm/perspectives/summarizer.py

[Source](../../../cdm/perspectives/summarizer.py)

- class: [`ApproachSummarizer()`](../../../cdm/perspectives/summarizer.py#L23)
- function: [`ApproachSummarizer.__init__(self, ollama: OllamaClient, *, enabled: bool=True) -> None`](../../../cdm/perspectives/summarizer.py#L26)
- function: [`ApproachSummarizer.summarize(self, topic: str, group: str, terms: list[str], subjects: list[str], titles: list[str]) -> str`](../../../cdm/perspectives/summarizer.py#L30)

## cdm/perspectives/terms.py

[Source](../../../cdm/perspectives/terms.py)

- class: [`Tokenizer()`](../../../cdm/perspectives/terms.py#L138)
- function: [`Tokenizer.__init__(self, lexicon: BoilerplateLexicon, max_ngram: int=3) -> None`](../../../cdm/perspectives/terms.py#L141)
- function: [`Tokenizer.content_words(text: str) -> list[str]`](../../../cdm/perspectives/terms.py#L146)
- function: [`Tokenizer.words(self, text: str) -> list[str]`](../../../cdm/perspectives/terms.py#L154)
- function: [`Tokenizer.terms(self, text: str) -> list[str]`](../../../cdm/perspectives/terms.py#L159)
- function: [`Tokenizer.ngrams(self, text: str) -> list[str]`](../../../cdm/perspectives/terms.py#L163)
- field: [`Tokenizer.ngrams.phrases: list[str]`](../../../cdm/perspectives/terms.py#L165)
- function: [`Tokenizer.stem(word: str) -> str`](../../../cdm/perspectives/terms.py#L176)
- function: [`Tokenizer._keeps(self, run: list[str]) -> bool`](../../../cdm/perspectives/terms.py#L190)
- function: [`Tokenizer._is_sponsor_line(self, name: str, place: str) -> bool`](../../../cdm/perspectives/terms.py#L205)
- class: [`DistinctiveTerms()`](../../../cdm/perspectives/terms.py#L210)
- function: [`DistinctiveTerms.__init__(self, config: PerspectiveConfig, tokenizer: Tokenizer) -> None`](../../../cdm/perspectives/terms.py#L213)
- function: [`DistinctiveTerms.matching(self, texts: Sequence[str], terms: Sequence[str], limit: int) -> list[int]`](../../../cdm/perspectives/terms.py#L217)
- function: [`DistinctiveTerms.top(self, texts: Sequence[str], groups: NDArray[np.intp], limit: int \| None=None) -> dict[int, list[str]]`](../../../cdm/perspectives/terms.py#L226)
- field: [`DistinctiveTerms.top.result: dict[int, list[str]]`](../../../cdm/perspectives/terms.py#L247)
- function: [`DistinctiveTerms._longest(ranked: list[str]) -> list[str]`](../../../cdm/perspectives/terms.py#L264)
