# Analytics: embeddings, topics, perspectives, and graphs

The application combines source annotations with derived analysis. This guide
identifies each computation, its inputs, persistence, consumers, and limitations.
The [API/frontend reference](../reference/api-and-frontend.md) describes the HTTP
and browser entry points. This is an implementation guide, not a claim that a
particular deployment has complete data or currently trained models.
Exhaustive declarations are indexed in [utils](../reference/symbols/utils.md),
[graph](../reference/symbols/graph.md),
[perspectives](../reference/symbols/perspectives.md),
[contracts](../reference/symbols/contracts.md), and
[backend](../reference/symbols/backend.md).

## Analytical layers and provenance

| Layer | Inputs | Meaning of output |
| --- | --- | --- |
| CRS subjects/policy areas | Indexed bill annotations | Upstream human-curated classification, not learned topics. |
| Sentence embeddings | Natural-language bill title, latest summary, CRS terms | Numeric text similarity features, cached by model and content. |
| BERTopic topics | Embeddings plus lemma-preferred topic text | Discovery clusters, keywords, assignments, and time bins. |
| Metasubjects | Non-outlier topic centroids | Broad groups with matched IDs, generated/curated names, and all-bill assignment. |
| Party perspectives | Policy-bill text grouped by topic and Congress | Textual approaches, party contrasts, evidence, and bipartisan indicators. |
| Member graph | Sponsorship, roll calls, topic assignments | Separate collaboration, voting, and topic-profile neighbor signals. |

Source entry points are [TopicModeler](../../cdm/utils/topic_modeler.py),
[MetasubjectBuilder](../../cdm/utils/metasubjects.py),
[PerspectiveRunner](../../cdm/perspectives/runner.py), and
[GraphBuildJob](../../cdm/graph/job.py).
[WorkerContainer](../../cdm/workers/runtime.py) constructs execution collaborators;
[Container](../../cdm/container.py) owns lightweight reads and durable submission.
Default model/threshold values live in
[app_config.py](../../cdm/config/app_config.py); command-line flags can override
some training values.

## Serving availability and lineage

Analytics responses carry typed `analysis` metadata: `state`,
`source_model_version`, and `published_model_version`. Graph neighborhoods report
one status per requested signal, plus `topic_analysis` when topic overlays or
topic-based centers are requested.

| State | Meaning |
| --- | --- |
| `not_built` | No published analysis, or the requested graph Congress/similarity query has not been covered. |
| `empty` | Published analysis was read successfully but produced no matching results. |
| `available` | Results are available; this is not a source-corpus freshness guarantee. |
| `stale` | A graph or perspective snapshot uses a different topic model from the published model observed for this response. Results remain readable. |
| `unknown` | Legacy lineage, cache ownership, or requested Congress coverage cannot be verified. |
| `unavailable` | A dependency failed or a required published artifact could not be read; HTTP 503 carries this error state instead of an empty success. |

Unbuilt detail requests return 503 with `analysis_state: not_built`; an unknown
topic within a published model remains 404. Timed-out and failed-shard analytics
searches are rejected. A missing query embedding is not a successful empty kNN
search, and no vectors are generated during a read.

Member profiles no longer embed duplicate topic analysis. Clients fetch the
existing member-topics endpoint separately, so unavailable optional analysis
does not prevent the core profile from loading. The frontend shows failures and
availability notices instead of silently hiding those sections.

These states compare known publication lineage, not daily source updates.
Matching model IDs do not prove that newly ingested bills have been analyzed.
Operational graph-age warnings remain separate in graph health.

Bill-facing reads and graph signatures share canonical bill/law eligibility.
Topic training and the perspective policy corpus retain their existing
`source_type=bill` contract; widening bill visibility does not silently change a
published model's fitted corpus. Reconcile source additions against the recorded
input contract before claiming that an existing model includes new records.

For an expanded corpus, compare the actual training projection for every original
input, not only its document version: a metadata-only version advance need not
change the fitted text. Record additions, removals and changed projections
against the protected baseline. Graph signature eligibility can include law
projections that topic training excludes, so their input counts need not match.
Rebuild dependent graphs/perspectives on the accepted model, preserve voting and
historical generations, and verify the actual HTTP/browser lineage and stability
gating before declaring current-corpus acceptance. A cache-read log alone does
not prove exact reused/new embedding counts.

### Label origin is separate from availability

Topic summaries, metasubject summaries, and perspective clusters record
`label_source` and nullable `fallback_reason`. The same metadata is stored with
the derived output and served to clients; topic and perspective detail views
show it without hiding usable fallback results.

| Label source | Meaning |
| --- | --- |
| `llm` | An accepted reply from the configured local model. |
| `keywords` | A deterministic keyword-derived title. |
| `largest_topic` | A metasubject copied its largest topic's title. |
| `override` | An explicit metasubject name override. |
| `deterministic` | A system label or a duplicate-name fallback combining existing titles. |
| `unknown` | A stored legacy label has no verifiable origin. |

Safe fallback reasons are `disabled`, `unavailable`, `request_failed`,
`invalid_response`, and `name_collision`. Raw model replies, exception messages,
and server bodies are not persisted as reasons. These describe the label's
creation, not current model-server readiness or source-data freshness.
Carried-over names retain their original provenance; overrides and renaming
replace it. Existing records are not rewritten or guessed to be LLM-generated.
Training previews still make no LLM calls and write no model, analysis, or embedding
cache data. Optional model failures retain deterministic labels; programming
errors still fail the build rather than being hidden as a successful fallback.

## 1. Corpus construction and cached embeddings

[build_topic_documents](../../cdm/utils/topic_modeler.py#L162) converts search hits
to `TopicDocument` objects. For each bill it:

- strips HTML tags, unescapes HTML, and collapses whitespace;
- selects the nonempty summary with the latest `action_date`;
- combines title, summary, policy area, and legislative-subject names;
- prefers `title_lemma` and summary `text_lemma` for vectorizer text, with per-field
  raw fallback;
- keeps a natural-language `embed_text` for transformer input;
- prefers `introduced_date` as the timestamp, falling back to latest-action date;
- drops a hit only when no usable combined text remains.

Consequently, a bill without a usable title/summary can still contribute subject
terms. These inputs are not the complete operative bill text. Natural-language
embedding input and lemma-preferred keyword input are intentionally different.

[TopicDocument.embedding_input](../../cdm/utils/topic_modeler.py#L105) returns
`embed_text` when available, otherwise `text`.
[TopicModeler._embed](../../cdm/utils/topic_modeler.py#L226) uses `CachedEmbedder`
when an embedding store is injected; the configured default transformer is
`all-mpnet-base-v2`.

[CachedEmbedder.embed](../../cdm/utils/cached_embedder.py#L35) computes content
hashes, fetches fresh vectors, encodes only misses, and writes each completed
chunk. Its default encoding chunk is 2,048 documents. The store's configured
write batch size is separate (`embedding_batch_docs`, default 500).
Output vectors are reordered to the original input job sequence.
A failed run can reuse previously persisted chunks on the next attempt.

Persistence is an Elasticsearch index, not a local NumPy cache:
[Container.embedding_store](../../cdm/container.py) combines
`ElasticConfig.embeddings_index` (default `congress-embeddings`) with the SHA-256
of the model name through
[EmbeddingStore.namespace](../../cdm/store/embedding_store.py).
The resulting model-owned index has validated model/dimension mapping metadata.
Document IDs are bill IDs. Records carry model, content hash, embedding timestamp,
and a cosine-indexed dense vector. The hash includes `model + "\0" + text`.

Separate model namespaces can retain independent vectors for the same bill.
Within one namespace, changed content makes the cached hash stale; a completed
write replaces that bill's prior vector. Vector dimensions and configured model
must remain compatible with the index. Legacy unsuffixed caches are not silently
relabeled or accepted as model-owned training caches.
`EmbeddingStore.similar` performs kNN from an existing cached vector, excludes
the query document, and does not encode missing query bills. Similarity reads use
the published run's cache/model identity when a validated run exists.
[SimilarBillService.similar](../../cdm/backend/services/similar_bill_service.py)
adds indexed bill metadata for the API.

## 2. Topic fitting, assignment, labels, and trends

[scripts/train_topic_model.py](../../scripts/train_topic_model.py) submits a
durable training job; the execution worker runs
[TopicTrainingJob](../../cdm/topics/training.py). Its `_fetch` scans the bill read alias
for `source_type=bill` with `congress >= --min-congress`; the default is 113.
This intentionally excludes earlier title-dominated Congresses unless overridden.
`--max-docs` caps the scanned corpus and is intended for bounded experiments.

[TopicModeler.fit](../../cdm/utils/topic_modeler.py#L248) creates BERTopic with:

- supplied sentence embeddings;
- `CountVectorizer` English plus legislative stopwords;
- alphabetic tokens of at least three letters, unigrams/bigrams, `min_df=5`;
- maximal marginal relevance representation with diversity 0.4;
- default minimum topic size 25 and 15 top words;
- `calculate_probabilities=False`.

The return value contains a `TopicAssignment` per input document, with a topic ID
and available membership value. Topic `-1` is the outlier category.
The `_assignments` adapter uses zero if the library supplies no probability and
takes the maximum if a per-document vector is supplied. These values should not
be described as calibrated policy-classification confidence.

[TopicModeler.transform](../../cdm/utils/topic_modeler.py#L282) assigns new documents
without refitting. It exists as a callable utility; the batch training script
performs a fresh `fit`, not online `partial_fit`.
The transform method encodes directly rather than using `_embed`'s cache path.

`topic_summaries` produces IDs, sizes, deduplicated top words, and keyword-derived
names. [dedupe_terms / keyword_label](../../cdm/utils/topic_terms.py) are shared
label cleanup helpers. Topic numbers belong to a model version; they are not a
stable taxonomy identifier across refits.

[TopicLabeler.label_topics](../../cdm/utils/topic_labeler.py) optionally creates
human-readable titles from keywords and representative documents. Outliers are
not named as ordinary topics. `--no-llm-labels` keeps keyword-based labels.
[OllamaClient](../../cdm/utils/ollama_client.py) probes `/api/tags` and sends
non-streaming `/api/chat` requests to the configured endpoint. Failures return an
empty response to callers, which use their naming fallback.
Default URL/model are `http://localhost:11434` / `llama3.1`; this remains
configuration, not a guarantee of local execution in every deployment.

[TopicModeler.topics_over_time](../../cdm/utils/topic_modeler.py#L291) analyzes
dated fitted documents, using `--nr-bins` (default 60).
Missing timestamps are excluded, and no dated documents is an error.
These BERTopic time bins are not the fixed calendar-quarter bins used for
metasubject counts. Trend frequencies reflect the fitted corpus and available
dates, not external legislative attention or media coverage.

`save` writes BERTopic safetensors with c-TF-IDF, omitting the embedding model.
`load` reattaches an embedder. Fitted document embeddings are available through
`document_embeddings` only on a freshly fitted instance; loading the saved model
does not recreate that fitted-corpus array.

### Topic persistence and reads

`TopicTrainingJob.execute` generates a new UTC-based version and saves the
model below `--model-dir/<version>` (default `models/topics/<version>`).
Its `_actions` constructs the versioned bulk writes to `ElasticConfig.analysis_index`, whose default is
`congress-analysis-topics`. The shared index distinguishes rows with `kind`:

| Kind | Stored information |
| --- | --- |
| `topic` | Version, training timestamp, topic ID, label/keywords/size, centroid, group membership. |
| `assignment` | Version, bill ID, topic ID, membership value, metasubject ID/confidence/provenance flag. |
| `topic_over_time` | Version, topic, timestamp, frequency, evolving words. |
| `metasubject` | Version, broad-group definition, topics, size, centroid. |
| `metasubject_over_time` | Version, group, calendar-quarter timestamp, frequency. |
| `party_topic` | Separate perspective-builder output for a topic and Congress. |

Topic, assignment, and trend IDs include the model version, so versions can
coexist. Bulk errors fail the run before publication.
[`TopicPublicationStore`](../../cdm/store/topic_publication.py) writes a validated
complete-run manifest and compare-and-swaps the `topic-model:published` pointer.
[`TopicService.latest_model_version`](../../cdm/backend/services/topic_service.py)
reads that pointer, not the newest row by `trained_at`. Partial/capped runs and
legacy generations without a validated manifest cannot become current simply
because topic rows exist. Counts, assignments, group coverage and dated trend
totals are validated before publication. Status/ledger success alone is not a
source-corpus completeness or freshness certificate.

Full runs preflight the destination schema before fetching or fitting the corpus.
Existing compatible mappings are preserved; only missing fields are added.
In particular, legacy `label` text fields with a keyword subfield remain intact
instead of being changed to keyword fields. Incompatible required field mappings
or unacknowledged schema changes fail explicitly. Previews never initialize or
modify the publication schema.

### Diagram and data-join keys

| Document/entity | Identity and join |
| --- | --- |
| Bill | Canonical `bill:{congress}:{lowercase_type}:{number}`; assignment `doc_id` and embedding `_id` reference this indexed bill ID. |
| Topic | `topic:{model_version}:{topic_id}`; join on **both** version and topic ID, not topic ID alone. |
| Assignment | `assignment:{model_version}:{doc_id}`; links bill to topic and optional `metasubject_id`, with version and confidence/provenance fields. |
| Topic time row | `over_time:{model_version}:{row_number}`; topic ID and timestamp are attributes, not the row ID. |
| Metasubject | `metasubject:{model_version}:{metasubject_id}`; `topic_ids` joins topics within that model version. |
| Metasubject time row | `metasubject_over_time:{model_version}:{row_number}`; group ID and quarter timestamp are attributes. |
| Party-topic analysis | `party_topic:{model_version}:{congress}:{topic_id}`; nested `perspective_id` is local to the topic/Congress split. |
| Member | Bare bioguide IDs appear in sponsor/cosponsor arrays and graph endpoints; canonical summary `mget` uses `member:{bioguide_id}` in `congress-member-read`. |
| Graph edge | `edge:{graph_version}:{signal}:{member}:{neighbor}`; member and neighbor are bare bioguide IDs; `by_congress` holds nested per-Congress evidence. |
| Graph pointer | `pointer:{signal}` selects a graph version and records observed Congress scope; modern topic pointers pin `source_model_version`. Legacy pointers may lack both. |

Model versions and graph versions are distinct timestamp identifiers.
Roll-call `legislation_id` joins the canonical bill ID; Congress.gov House votes
instead join by Congress, uppercase `legislation_type`, and numeric
`legislation_number`. Their cross-source display de-duplication key is chamber,
Congress, session, and displayed roll number, not either source's document ID.

`TopicService.list_topics` and `get_bill_topics` exclude `-1`.
`get_topic` selects high-probability bills and joins their current indexed titles.
`related_topics` compares saved centroids by cosine similarity.
`get_member_topics` weights topic counts across sponsored/cosponsored bills and
builds quarterly member trends; it can inspect at most 5,000 linked bills.
Subject/policy-area weights come from
[SubjectService](../../cdm/backend/services/subject_service.py), independently
of learned assignments.

## 3. Broad metasubjects and stable-ID matching

[MetasubjectBuilder.build](../../cdm/utils/metasubjects.py#L169) removes outlier
topics, normalizes topic vectors, and groups them with average-linkage,
cosine-distance agglomerative clustering. It targets 30 groups by default, capped
by the number of topics. Group centroids are normalized, topic-size-weighted means.

[StableIdMatcher.match](../../cdm/utils/metasubjects.py#L108) uses a Hungarian
one-to-one assignment against the prior groups' centroid cosine similarities.
Matches at or above the configured threshold (default 0.85) keep prior IDs.
Unmatched groups receive new IDs above the previous maximum.
This is continuity matching, not an assurance of identical semantics.

Matched names normally carry forward, but the default size-ratio limit of 3 can
trigger renaming. New names come from
[OllamaMetasubjectNamer](../../cdm/utils/metasubject_namer.py), with the largest
topic's label as fallback. Optional duplicate-name disambiguation can rename
unpinned groups; hand-set overrides take priority.

[MetasubjectAssigner.assign](../../cdm/utils/metasubjects.py#L266) assigns a bill
to its topic's group when available (`assigned_by=cluster`). Bills without a
mapped topic, including topic outliers, go to the nearest normalized group
centroid (`assigned_by=nearest`).
`confidence` is the cosine similarity to the chosen group, not a probability.
The default low-confidence threshold is 0.5; such bills remain assigned and get
`low_confidence=true`. The assigner requires a nonempty group set.

`with_sizes` recounts all assigned bills, including outliers.
[QuarterlyTrendBuilder.build](../../cdm/utils/metasubjects.py#L322) counts
dated documents by calendar-quarter start; undated documents contribute to sizes
but not quarterly trends.
Metasubject size totals therefore need not equal displayed non-outlier topic totals.

Names can be curated through
[scripts/set_metasubject_override.py](../../scripts/set_metasubject_override.py).
[MetasubjectOverrideStore](../../cdm/store/metasubject_override_store.py) writes
append-only per-group versions in the separately configured
`congress-metasubject-overrides` index by default. Clearing appends a tombstone;
current names are derived from the latest version for each group.
The training script reads overrides during grouping; writing one does not itself
rewrite already-persisted metasubject names.

## 4. Party perspectives and evidence

The actual perspective algorithm is lexical TF-IDF/SVD/KMeans, **not** a second
clustering of cached transformer vectors. Some module descriptions refer to
embeddings; the executed path is
[PerspectiveRunner.run](../../cdm/perspectives/runner.py#L52) →
[PerspectiveBuilder.build](../../cdm/perspectives/builder.py#L65) →
[PerspectiveClusterer.cluster](../../cdm/perspectives/clustering.py#L76).

The runner reads latest-model non-outlier bill assignments and one Congress's
policy corpus. It learns a Congress-wide boilerplate lexicon, groups bills by
topic, and builds selected topics. By default topics need at least 20 eligible
bills for selection. Explicit topic IDs select existing groups directly.

[CongressCorpusReader](../../cdm/perspectives/corpus.py) scans bills, constructs
topic documents for fallback text, and applies `MeasureFilter`.
Configured resolution types and ceremonial title patterns are excluded.
Analytical text is the first 30,000 characters of `full_text_lemma`, or the topic
document text if full text is missing.
`MemberPartyReader` attributes a bill to the first sponsor's indexed party;
`MemberNameReader` supplies name/state tokens to suppress sponsor-credit language.
Party labels are not reconstructed for the date of each bill.

[BoilerplateLearner](../../cdm/perspectives/boilerplate.py) derives common terms
across topics in addition to fixed drafting stopwords.
[Tokenizer](../../cdm/perspectives/terms.py#L138) removes boilerplate, normalizes
simple plurals, and builds two-to-three-word phrases without crossing configured
sentence/punctuation breaks. Sponsor names and name/place credits are filtered.

`PerspectiveClusterer.features` computes sublinear TF-IDF within the topic,
keeping terms in at least three documents but at most half the documents, with
up to 20,000 features. It applies normalized truncated SVD (default 20 dimensions).
`cluster` tries 2–6 KMeans groups, requires at least eight bills per cluster,
and chooses the best silhouette. Stability is mean adjusted Rand agreement
against five refits using different seeds.

`PerspectiveBuilder` skips a split below 40 bills or without a valid clustering.
A produced split passes only at silhouette >=0.05 and stability >=0.6 by default.
Failed splits can remain in persistence; `PartyService.topic` removes their
`perspectives` from the served response. Other party evidence is built before
the split checks and is not equivalent to a passing cluster split.

[DistinctiveTerms.top](../../cdm/perspectives/terms.py#L226) ranks binary phrase
presence using smoothed log-odds z-scores, rather than raw term frequency.
[TermEvidence.describe](../../cdm/perspectives/evidence.py#L25) records bill and
unique-sponsor support plus example bill references. Default requirements are
five bills and three sponsors; fewer than five surviving display phrases leaves
the party phrase cloud empty. Each major party needs ten bills for party contrast.

[SubjectContrast.top](../../cdm/perspectives/evidence.py#L69) separately ranks CRS
subjects overrepresented in a group, with minimum support and near-duplicate
suppression. `PerspectiveLabeler` names cluster approaches from terms/titles;
[ApproachSummarizer](../../cdm/perspectives/summarizer.py) summarizes supported
party/bipartisan evidence with Ollama. With LLMs disabled, generated prose is
empty and keyword labels remain. Neither labels nor summaries establish intent,
legislative effects, ideology, or factual policy outcomes.

### Bipartisanship and ranking denominators

`CongressCorpusReader` marks a bill bipartisan when its major-party sponsor has
at least two opposite-major-party cosponsors **or** `BipartisanVoteReader` finds a
matching passage-question vote with more than 50% yea among voting members of
each major party. The vote path requires a linked `legislation_id`; the question
regex is a heuristic. Present/nonvoting people are not in its yea/nay denominator.

`PerspectiveBuilder._bilateral` considers major-party-sponsored bills only.
With at least ten such bills, a topic is bilateral at a bipartisan share >=25%.
This differs from the perspective-cluster party lean, which is a smoothed
log-odds difference against the entire topic's known-party bills.

[PartyService.overview](../../cdm/backend/services/party_service.py#L25) defaults
to the newest available analyzed Congress, not necessarily today's Congress.
Party rankings are by sponsor-party bill count among the persisted analyzed
topics. `share_of_party` uses that analyzed set, not every bill in Congress.
The API shows at most 25 ranked topics per party by default.

### Perspective persistence

[scripts/build_perspectives.py](../../scripts/build_perspectives.py) submits a
durable request. `--all-topics` removes the default five-topic limit; normal
minimum-corpus and stability gates still apply.
[PerspectiveBuildJob](../../cdm/perspectives/job.py) captures each Congress's
publication snapshot before fitting.
[`PerspectiveRepository.replace`](../../cdm/store/perspective_repository.py)
publishes one validated, refreshable document per Congress in the shared
analysis index, containing the model version, build time and entire result set.
An absent snapshot uses a create-only write; an existing snapshot requires the
captured sequence number and primary term. Stale publication fails explicitly.
Readers cannot observe a deleted/partially rewritten topic set. Publication is
atomic per Congress, not a transaction spanning multiple Congresses.

[`PerspectiveRepository.read`](../../cdm/store/perspective_repository.py)
prefers that canonical snapshot and falls back to untouched legacy `party_topic`
records only when no snapshot exists. Legacy selection uses the newest returned
`built_at` version. Rebuilding with selected topics still replaces the Congress's
entire published set, not just those individual topics. A topic retrain does not
itself rebuild perspectives. Old legacy rows are not deleted by publication;
analysis retention must account separately for current snapshot model lineage.

## 5. Three separate member-graph signals

[BillSignatureReader / RollCallReader](../../cdm/graph/store.py) default to
Congress 113 onward. Graph scores summarize loaded records, not all historical
relationships. Each builder retains the union of each member's top 50 positive
neighbors overall and per Congress, preserving candidates for filtered reads.
Storage uses directed member→neighbor rows even for symmetric scoring formulas.

### Collaboration

[CongressMatrices.add_bill](../../cdm/graph/collaboration.py#L47) counts sponsor
to cosponsor links in each Congress and increments member activity.
Shared cosigners contribute `1/(number_of_cosigners-1)` per pair for bills with
2–100 cosigners; the default cosigning multiplier is 0.25.

[CollaborationGraphBuilder._score](../../cdm/graph/collaboration.py#L85) divides
symmetrized sponsor/cosponsor plus weighted cosigning counts by
`sqrt(activity_i * activity_j) + 3`, capped at 1.
Edges retain directional sponsored counts and shared-cosigning evidence by
Congress. Co-sponsorship is evidence of recorded legislative collaboration,
not proof of personal relationships or endorsement of every final provision.

### Voting

[AgreementCounts.add_votes](../../cdm/graph/voting.py#L37) counts shared yea/nay
votes and agreements; non-cast positions are zeros.
[VotingGraphBuilder._score](../../cdm/graph/voting.py#L88) ranks **party-split**
agreement, shrunk toward 0.5 with ten prior votes:
`(agreed_split + 10 * 0.5) / (shared_split + 10)`.
Pairs without shared split votes get zero. Edge evidence separately records
all-vote shared/agreed counts and split-vote shared/agreed counts.
The builder consumes the stored `party_split` flag rather than rederiving it.

### Topic-profile similarity

[TopicGraphBuilder](../../cdm/graph/topics.py#L87) uses non-outlier assignments
from the latest topic model. Sponsorship contributes 1, cosponsorship 0.25.
Counts become `log1p(count) * IDF`, then normalized member vectors.
IDF is derived from all-time member topic incidence and reused for Congress views.
Cosine similarity is discounted by the geometric mean of each member's
`volume/(volume+5)` confidence. Up to three high-overlap topic labels explain
an edge. Similar subject matter is not agreement about a policy approach.

### Publication, API blending, and visualization

[GraphBuildJob.run](../../cdm/graph/job.py#L62) builds requested signals, writes
versioned edges, then publishes each signal's pointer through
[GraphStore.publish](../../cdm/graph/store.py#L103).
The graph index is the configured-name helper's `analysis_graph` family.
Publication retains prior versions rather than implicitly pruning them; cleanup
requires an explicit lineage/recovery disposition. A later signal failure can leave earlier signals
successfully updated: all three are not published as one transaction.

[GraphService](../../cdm/backend/services/graph_service.py) reads active pointers
and nested Congress scores, capped at 10,000 edge hits.
[SignalScaler](../../cdm/backend/services/neighborhood_service.py#L51) rescales
collaboration by the candidate maximum, voting above a 0.5 floor, and topic above
a 0.2 floor. Weighted sums divide by all enabled weights, including an enabled
signal missing on a pair. This blended score is request-relative, not a universal
similarity probability or directly comparable to raw per-signal scores.

`NeighborhoodService.neighborhood` gathers bounded candidates, applies neighbor
party/chamber filters, retains up to the requested limit per seed, and optionally
adds member-topic, CRS-subject, and metasubject overlays.
Those overlays use sponsored bills, unlike the broader sponsored/cosponsored
member-topic profile. `TopicNeighborhoodService` instead selects members with
at least two sponsored bills in a topic/group/subject and links that selected set.

[MemberGraphView](../../frontend/app/src/components/MemberGraphView.tsx) performs
ForceAtlas2 layout and optional Louvain community coloring in the browser.
Community colors and geometric proximity are presentation calculations on the
returned subgraph, not persisted party classifications or causal relationships.

### Schema and source coverage gates

`GraphStore` validates declared field presence, types, nested structure, explicit
dynamic policy and indexing/enabled flags before writing edges or publishing a
pointer. Existing-index preflight is read-only and never adds fields or repairs
aliases. Both edges and pointers target the same configured physical index;
an existing write alias cannot silently redirect only the edges elsewhere.
Extra fields are allowed; this check does not certify analyzer/query equivalence.
`shared_topics` is explicitly keyword-mapped, not merely retained in `_source`.
Adding mappings alone does not retroactively index old stored values: approved
rebuild/reindex verification is still necessary.

Health reports incompatible mappings as failed and missing pointer Congress
scope as unknown coverage. An empty legacy graph response without known scope is
`unknown`, not proof of no relationships, including unfiltered requests.
Observed Congress lists, active edge counts and top-k output are not global
source-coverage certificates.

The current graph readers consume bill sponsor/cosponsor arrays and Voteview
roll-call voter arrays directly. The declared `sponsorship` and `vote_position`
bridge indices have no implemented population path and are not dependencies of
these builders; their zero counts must not trigger invented bridge rows.
Retain them pending an explicit schema-scope decision.

<!-- wiki:repository-only:start -->
The original read-only live audit found 109,691 scoped bill inputs (11 without sponsor
IDs), 12,621 roll calls and active collaboration/voting/topic edge counts of
114,566/110,341/125,086. At that audit, voting omitted Congress 114: all 1,824 source
roll calls then had no linked member positions.
<!-- wiki:repository-only:end -->

Voteview vote CSVs represent
ICPSR IDs as integral decimals while member CSVs use integer strings. Typed
integer IDs now join these representations exactly and reject fractional or
invalid values; unknown non-President links and mismatched roll-call sets fail
before replacement output. Presidents remain explicitly excluded.
<!-- wiki:repository-only:start -->
Offline reconstruction recovers all 1,322 House and 502 Senate roll calls,
including 984/310 party-split votes, without requests or live writes.
<!-- wiki:repository-only:end -->

The source reader refuses records with no linked positions, but accepts valid
present/not-voting-only records; the scorer still uses only yea/nay.
Topic source scans reject partial search results. New topic graph generations
record their exact source-model version; legacy generations without that
metadata remain unknown, not retrospectively assigned a model from timestamps
or labels.

<!-- wiki:repository-only:start -->
Approved gate two added all eight mapping paths, including `shared_topics`, and
repaired exactly those 1,824 sources with CAS and per-write receipts. Complete
12,621-record source verification and a full 1,148,223-document graph backup/
isolated restore passed; unrelated source versions and all graph bodies,
versions, pointers and aliases were unchanged at gate two. Existing graph values are not
retroactively indexed merely by the mapping additions.
Approved gate three subsequently published only voting:
`20261103T091601Z-4b9d26b3167844a790a5f1aded61143f`, with **116,450 edges** and
explicit Congress **113-119** scope, including **48,655** searchable Congress 114
edges. All old graph bodies/versions remain; only the voting pointer changed.
The physical graph now contains 1,264,673 documents, including historical
versions and pointers. Collaboration/topic remain on their original pointers;
topic lineage is still unknown. No workers have resumed.
<!-- wiki:repository-only:end -->

[VotingGraphPromotion](../../cdm/graph/promotion.py) verifies the applied repair
and sealed candidate, stages create-only edges, captures their exact versions,
and preserves the complete historical graph. `accept()` validates actual
desktop/narrow Playwright results and decodes each embedded typed API response
to prove candidate identity, Congress 114 availability and finite voting links.
`publish()` revalidates the evidence and CAS-switches only the voting pointer;
rollback restores the exact old raw pointer without removing either edge set.
<!-- wiki:repository-only:start -->
Real API/browser acceptance passed both against the pinned candidate and,
after publication, the ordinary unpinned serving API.
<!-- wiki:repository-only:end -->
See the [promotion procedure](../OPERATIONS_RUNBOOK.md#sealed-voting-only-graph-promotion).

### Sealed staging and rollback evidence

[GraphBuildJob.stage](../../cdm/graph/job.py) returns a typed `StagedGraph`
containing the candidate `GraphVersionPointer` and written count, without
publishing. Candidate edge writes are create-only and require complete
acknowledgements. The normal `run()` captures a typed pointer snapshot before
building, calls the same stage boundary, then conditionally publishes against
that snapshot. An absent pointer uses create-only publication; an existing
pointer uses its sequence number and primary term. Concurrent publication is an
explicit conflict, not a last-writer-wins overwrite. Staging alone is not a read-only operation:
use the repair CLI's isolated rehearsal, not a serving `GraphStore`.

[GraphRepairCapture](../../cdm/graph/repair.py) freezes all configured voting
inputs, raw pointer before-images, physical metadata and six retained CSVs.
Typed `StoredDocument` rows preserve IDs, raw source, sequence numbers and primary
terms. `RepairDiff` distinguishes absent fields from present nulls. Only
`VoteRepairField` voter arrays, party positions/split, defector IDs and yea/nay
counts may change; unexpected non-null reconstructed metadata fails capture.
The source capture is bounded at 20,000 documents by default.

[GraphRepairRehearsal](../../cdm/graph/repair.py) re-derives and verifies repairs,
rejects the captured cluster UUID, and creates fresh owned unaliased scratch
indices. It checks full source content and scope, unchanged staged pointers,
exact searchable edge/export counts and finite scores. After simulated isolated
promotion, rollback checks current contents and uses sequence/primary-term
preconditions. Exact original source bodies and raw pointers must be restored;
Elasticsearch sequence numbers themselves are not reversible. Owned indices
are removed before an acceptance marker is written, including on failure.

<!-- wiki:repository-only:start -->
The 2026-11-03 rehearsal captured 12,621 roll calls and exactly 1,824 repair
candidates (1,322 House, 502 Senate). The isolated candidate has 116,450 voting
edges over Congresses 113-119, including 48,655 with searchable Congress 114
evidence. Full cloned source/pointer rollback passed; this is not live
publication, corpus freshness or global completeness certification.
<!-- wiki:repository-only:end -->
See the [commands and artifact contract](../OPERATIONS_RUNBOOK.md#sealed-graph-repair-rehearsal).

## 6. Rebuilds, retention, and operational checks

Run commands from the repository root with the project's configured dependencies:

```bash
# Bounded experiment: computes embeddings without model/result/cache writes or LLM calls.
uv run python scripts/train_topic_model.py --max-docs 5000 --dry-run --no-llm-labels

# Persist a full default-corpus topic model, assignments, and metasubjects.
uv run python scripts/train_topic_model.py

# Rebuild all graph signals, or just a selected signal.
uv run python scripts/build_member_graph.py
uv run python scripts/build_member_graph.py topic

# Explicitly rebuild the complete eligible topic set for selected Congresses.
uv run python scripts/build_perspectives.py --congress 118 --congress 119 --all-topics

# Bounded perspective inspection without replacing saved party-topic documents.
uv run python scripts/build_perspectives.py --congress 119 --top-topics 5 --dry-run --no-llm-labels
```

The perspective CLI defaults to Congress 119 and the top five topics.
API and CLI submissions use typed durable analytics requests rather than
independent subprocess launchers.
Topic training `--dry-run` and every `--max-docs` run skip model saving,
analytical-result indexing, embedding-cache writes and LLM calls. The durable
job ledger and third-party model-download cache may still change. Submission
alone does not start an analytics consumer; respect the managed stack's capacity
checks rather than enabling an oversized profile.

For the approved local release closeout, a separate operator-owned host process
uses the existing durable runner and heartbeat, with a monitored 4 GiB RSS stop
threshold and no additional Celery worker. The full existing Congress 113+
corpus is frozen with source versions and code/configuration seals; exact
model/content-hash-matched legacy vectors can be reused in the model-isolated
cache without modifying the legacy cache. Publication rechecks the frozen scope
and original pointer before the ordinary validated compare-and-swap boundary.
These controllers and their receipts are retained operational evidence, not
another packaged worker or an automatically enabled scheduling path.

[AnalyticsJobs](../../cdm/jobs/analytics.py) submits durable jobs and
[AnalyticsJobRunner](../../cdm/workers/analytics_runner.py) owns worker execution.
The [topic](../../cdm/topics/training.py), [graph](../../cdm/graph/job.py) and
[perspective](../../cdm/perspectives/job.py) builders share that lifecycle.
SQLite ledger claims, heartbeats, progress and terminal states are authoritative;
removed PID/JSON status files are not current coordination mechanisms.

[RetirementReporter](../../cdm/topics/retirement.py) inventories published
references and retention candidates read-only. Unknown legacy references remain
explicit; this report does not automatically delete model directories, topic
versions or embedding entries. Any destructive retention remains separately
gated.

[GraphHealthChecker.check](../../cdm/graph/health.py) checks published pointer
presence, edge count, age (warning after nine days), last-build state, and topic
model drift. Declared mapping compatibility and known Congress scope are
separate gates. Current pointers support explicit source-model lineage; legacy
pointers may still lack it. Age or a successful rebuild is not proof of source
freshness or complete historical coverage.

Operational interpretation:

1. Confirm required bill/member/roll-call inputs and source coverage separately.
2. Inspect model version/training time and assignment coverage, including outliers.
3. Rebuild topic-derived graphs and perspectives after topic changes.
4. Check status **and** persisted outputs; launches and status success do not
   independently prove complete source coverage or cross-index consistency.
5. Keep example bills, support counts, party attribution, model versions, and
   low-confidence flags visible when interpreting generated labels or summaries.
