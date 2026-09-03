# Topic Analysis Implementation Plan

## Status

Planning only. This document defines the topic taxonomy, NLP pipeline, storage
model, evaluation protocol, and rollout needed to produce explainable topic
associations for congressional records.

## Goals

- Assign stable, human-readable policy topics to legislation and other
  searchable congressional records.
- Distinguish broad concepts from narrower issues and from merely related
  concepts. For example, a document about abortion should not automatically be
  labeled only as human rights, and a document about LGBTQ+ discrimination
  should not be labeled as abortion because both may mention civil rights.
- Preserve the evidence, model version, confidence, and source of every
  generated association.
- Support document, Congress, committee, and member-level analysis without
  running NLP during dashboard requests.
- Make results reproducible and replaceable while keeping canonical source
  records authoritative.

## Non-goals

- Inferring a legislator's personal beliefs from topic associations alone.
- Treating a topic label as a position, sentiment, vote recommendation, or
  legal conclusion.
- Replacing Congress.gov subject metadata with an opaque unsupervised topic
  model.
- Letting an LLM generate unreviewed production labels or alter source data.

## Architectural Fit

The existing data model already provides the intended boundaries:

- Canonical records remain in the entity indices and are read from OpenSearch
  by the application.
- `analysis_chunk` stores bounded passages for retrieval and evidence.
- `analysis_annotation` stores versioned NLP output.
- `analysis_aggregate` stores dashboard-ready facts.
- `sponsorship` and `vote_position` remain explicit relationship indices.
- SQLite/archive storage remains for ingestion, replay, and job metadata.
- API contracts are defined in `cdm/contracts/api.py`; generated frontend types
  must continue to come from that source.

Topic processing is an asynchronous derived-data job. A record update queues
analysis; the job reads the canonical document, writes chunks and annotations
idempotently, and refreshes aggregates after successful bulk writes.

## Recommended Approach

Use a hybrid, hierarchical, multilabel system:

1. Normalize source text and preserve character offsets.
2. Ingest authoritative Congress.gov subjects, policy areas, CRS topics, and
   other structured labels as separate evidence sources.
3. Match high-precision aliases and phrase rules.
4. Score candidate topics using a supervised multilabel classifier trained on
   reviewed examples and structured labels used as weak supervision.
5. Use sentence/document embeddings for semantic candidate retrieval and
   similarity to topic definitions, not as the sole decision rule.
6. Apply parent/child consistency, exclusions, and minimum evidence rules.
7. Store every accepted and review-queue association with evidence spans.
8. Use BERTopic, LDA, NMF, TF-IDF, and keyphrase extraction for taxonomy
   discovery, drift detection, and review prioritization only.

This gives users stable labels while retaining the ability to discover issues
that the controlled vocabulary missed.

## Taxonomy Design

### Topic identity

Each topic is a stable canonical concept, not a display string:

```json
{
  "id": "rights.reproductive.abortion",
  "label": "Abortion",
  "definition": "Government policy, law, access, funding, or regulation concerning induced abortion.",
  "parents": ["rights.reproductive", "rights.civil"] ,
  "aliases": ["abortion", "termination of pregnancy", "right to choose"],
  "status": "active",
  "version": 1
}
```

Use lowercase dotted IDs for stable API and index values. Labels can change
without changing IDs. A topic may have multiple parents, so the taxonomy is a
DAG rather than a strict tree. Keep `broader_than`, `related_to`, and
`often_confused_with` relations distinct from `is_a` parentage.

Every topic should define:

- `id`, `label`, `definition`, and optional `description`.
- `parents` and explicit semantic relations.
- Aliases, spelling variants, historical terms, acronyms, and multilingual
  aliases where applicable.
- Positive examples and hard-negative examples.
- Inclusion and exclusion criteria.
- Required co-occurring terms or contextual cues for ambiguous aliases.
- Topic level, such as `domain`, `policy_area`, `issue`, or `subissue`.
- Effective dates when terminology or legal scope changes.
- Owner, review status, and taxonomy version.

### Initial taxonomy shape

Begin with a small reviewed vocabulary. Expand only when a topic has a clear
definition, enough examples, and a user-facing use case.

```text
rights
  civil
    discrimination
    voting_rights
    racial_justice
    disability_rights
  human
    international_human_rights
    refugees_and_asylum
    torture_and_detention
  reproductive
    abortion
    contraception
    fertility_and_assisted_reproduction
    maternal_health
  lgbtq
    sexual_orientation_discrimination
    gender_identity_and_expression
    same_sex_marriage
    transgender_healthcare

health
  public_health
  healthcare_access
  mental_health
  bioethics

economy
  labor_and_employment
  taxes
  housing
  trade

environment
  climate_change
  conservation
  pollution

justice_and_crime
  criminal_justice
  policing
  prisons_and_corrections
  firearms

immigration
  border_and_enforcement
  legal_status
  asylum

defense_and_foreign_policy
  national_security
  military_operations
  foreign_aid
```

The root concepts `human rights`, `civil rights`, and `reproductive rights`
are useful roll-up topics, but they must not be used as interchangeable labels.
A classifier may assign both a parent and a child when evidence supports both;
API presentation can show the most specific labels and calculate parents as
roll-ups.

### Required distinctions

#### Abortion

Definition: policy, law, access, funding, providers, medication, gestational
limits, fetal-personhood claims, or constitutional/legal disputes specifically
concerning induced abortion.

Positive cues include `abortion`, `termination of pregnancy`, `mifepristone`,
`misoprostol` when the context is abortion, abortion providers, gestational
limits, and post-*Dobbs* regulation. Do not assign abortion merely because a
document discusses pregnancy, maternal health, contraception, or a general
right to privacy. Use a hard negative for medication terms whose context is
not abortion.

Suggested labels: `rights.reproductive.abortion`, optionally its parents
`rights.reproductive` and `rights.civil` when parent propagation is enabled.

#### LGBTQ+ rights

Definition: government policy or law concerning people affected by sexual
orientation, gender identity, gender expression, or same-sex relationships.

Separate `sexual_orientation_discrimination`, `gender_identity_and_expression`,
`transgender_healthcare`, and `same_sex_marriage` when the evidence permits.
Do not collapse all references to `LGBTQ+ rights` into marriage or healthcare.
Terms such as `partner`, `identity`, or `civil rights` require LGBTQ-specific
context.

#### Human rights

Definition: internationally recognized rights and protections, or government
conduct assessed through an international human-rights framework.

Examples include torture, arbitrary detention, trafficking, refugee protection,
and international human-rights obligations. A domestic discrimination bill may
also be a civil-rights topic without being an international-human-rights topic.
Do not assign `rights.human` solely because a document uses the word `rights`.
Require a human-rights phrase, an international instrument/body, or a reviewed
policy pattern.

#### Related but non-equivalent labels

- `civil rights` is a broad domestic equality and anti-discrimination category;
  it is not a synonym for every human-rights or reproductive-rights document.
- `reproductive rights` is a broader policy domain. Abortion, contraception,
  fertility, and maternal health are separate children.
- `human rights` is a framework and subject area. It can co-occur with
  immigration, foreign policy, or detention topics.
- `LGBTQ+ rights` is a population and rights domain. A bill can concern
  LGBTQ+ rights and healthcare, education, employment, or marriage at once.
- Topic labels do not encode stance. Store stance separately only after a
  separately designed, validated position-analysis project.

### Avoiding hierarchy leakage

Store two concepts for each association:

- `direct`: evidence directly supports this exact topic.
- `inherited`: the label is a propagated parent or roll-up.

For example, a bill explicitly regulating abortion receives direct evidence for
`rights.reproductive.abortion`; `rights.reproductive` may be inherited. A broad
human-rights resolution receives direct evidence for `rights.human`, but no
abortion child unless abortion-specific evidence exists.

## Python Processing Methods

### Text normalization and linguistic preprocessing

- Use Unicode normalization, whitespace normalization, and controlled cleanup
  while retaining the original text and a mapping to original character spans.
- Preserve titles, summaries, action text, CRS topics, Congress subjects, and
  full text as separate fields. They have different signal and reliability.
- Segment long records into sentences and bounded chunks. Do not classify a
  complete multi-page document as one undifferentiated string.
- Use spaCy for tokenization, sentence segmentation, POS/lemma features, noun
  chunks, and optional named entities. The existing `.lemma` mapping fields
  are suitable for storing normalized lemma arrays.
- Add domain tokenizer exceptions for bill numbers, legal citations, acronyms,
  agency names, and terms such as `LGBTQ+`, `HIV/AIDS`, and `mifepristone`.
- Treat named entities as contextual signals, not topics. Entity linking can
  later normalize agencies, courts, treaties, and legislation IDs.

### Keyword and keyphrase extraction

Use multiple signals and retain the method that produced each keyword:

- Exact controlled-vocabulary aliases and n-gram phrase matching for precision.
- TF-IDF or BM25-like corpus statistics for terms that distinguish a topic from
  the rest of the congressional corpus.
- spaCy noun chunks filtered by POS, stop words, length, and punctuation.
- KeyBERT-style embedding similarity for candidate phrases after the baseline
  is stable.
- YAKE or RAKE as inexpensive unsupervised discovery tools, with manual review.
- c-TF-IDF topic terms from BERTopic for cluster interpretation.

Keywords are evidence and search facets, not canonical topic IDs. Store their
surface form, normalized form, offsets, method, and score. Do not infer a topic
from a single generic keyword such as `rights`, `health`, or `security`.

### Candidate generation

Generate a bounded candidate set from:

1. Source subjects and policy areas.
2. Exact aliases and phrase rules.
3. Keyphrase overlap with topic descriptors.
4. Embedding nearest neighbors between chunks and topic descriptions/examples.
5. Supervised classifier scores.

Limit scoring to candidates from the same taxonomy branch plus semantically
related branches. This improves precision and makes confusing siblings visible.

### Classification options

| Method | Use | Strength | Limitation |
|---|---|---|---|
| Rules and aliases | High-precision seed labels | Explainable and cheap | Misses paraphrases; ambiguous terms need context |
| TF-IDF + logistic regression/linear SVM | First supervised baseline | Fast, inspectable, strong on stable vocabulary | Weak on paraphrase and long-range context |
| spaCy text categorizer | Production multilabel baseline | Fits Python pipeline and can be trained with reviewed examples | Requires labeled data and retraining |
| Transformer sequence classifier | Mature high-accuracy classifier | Captures context and paraphrase | More compute, versioning, and calibration work |
| Sentence embeddings | Retrieval and similarity | Good candidate recall and synonym handling | Similarity is not classification; thresholds drift |
| LDA/NMF | Corpus discovery | Interpretable latent terms; batch-friendly | Topics are unstable and not canonical |
| BERTopic | Discovery and temporal exploration | Embeddings, clustering, c-TF-IDF, hierarchy, dynamic topics | Outliers, parameter sensitivity, generated topics need naming |
| LLM/zero-shot classifier | Triage and bootstrapping | Useful before labels exist | Cost, reproducibility, bias, and calibration concerns |

Start with rules plus TF-IDF/logistic regression. Add a transformer only if the
baseline misses paraphrases after error analysis. Use embeddings for candidate
retrieval and similarity to reviewed topic exemplars. Keep unsupervised topics
out of production topic IDs.

### Scoring and decision policy

Each direct association should include component scores such as:

```text
final_score = calibrated(
    0.35 * classifier_score
  + 0.25 * phrase_evidence_score
  + 0.20 * source_metadata_score
  + 0.15 * embedding_score
  + 0.05 * distinctiveness_score
)
```

The weights are initial configuration, not a permanent truth; tune them on a
validation set. Calibrate scores per topic where class imbalance requires it.
Require at least one strong signal for specific topics and use a review queue
for scores in the uncertainty band. Keep accepted thresholds separate from
search ranking thresholds.

Use an `abstain` outcome. A model that says "unknown" is preferable to a
confidently wrong label for sensitive or easily confused topics.

## Data Structures

### Topic definition

```json
{
  "id": "rights.reproductive.abortion",
  "label": "Abortion",
  "definition": "...",
  "level": "issue",
  "parents": ["rights.reproductive"],
  "relations": {
    "related_to": ["rights.reproductive.contraception"],
    "often_confused_with": ["health.maternal_health"]
  },
  "aliases": [
    {"text": "abortion", "kind": "exact", "weight": 1.0},
    {"text": "termination of pregnancy", "kind": "phrase", "weight": 0.9}
  ],
  "inclusion_rules": [],
  "exclusion_rules": ["pregnancy care without abortion context"],
  "positive_examples": ["..."],
  "hard_negative_examples": ["..."],
  "status": "active",
  "taxonomy_version": "2026-01-01",
  "reviewed_at": "2026-01-01T00:00:00Z"
}
```

### Evidence span

```json
{
  "text": "medication abortion access",
  "normalized": "medication abortion access",
  "start": 482,
  "end": 513,
  "unit": "chunk",
  "method": "alias_rule",
  "score": 0.98
}
```

Offsets refer to the preserved text of the chunk or source field. Every span
must identify that field and its chunk ID so the UI can display evidence.

### Document-topic association

```json
{
  "id": "topic-edge:legislation:bill-119-hr-123:rights.reproductive.abortion:topic-v3",
  "source_id": "bill-119-hr-123",
  "source_index": "legislation",
  "topic_id": "rights.reproductive.abortion",
  "topic_version": "2026-01-01",
  "direct": true,
  "inherited": false,
  "score": 0.93,
  "confidence": 0.91,
  "decision": "accepted",
  "evidence": [],
  "source_signals": ["congress_subject", "phrase_rule", "classifier"],
  "model_id": "topic-linear-v1",
  "analysis_version": "topic-v3",
  "generated_at": "2026-01-01T00:00:00Z"
}
```

Use one association per source record and topic, with nested evidence or a
separate evidence index if span volume becomes large. Preserve rejected and
reviewed decisions in an audit/review store or append-only job output rather
than silently deleting them.

### Member topic profile

Compute member topics from explicit relationships, not from the member's name
or biography text:

```json
{
  "bioguide_id": "B001234",
  "topic_id": "rights.reproductive.abortion",
  "congress": 119,
  "sponsored_count": 3,
  "cosponsored_count": 17,
  "related_bill_count": 20,
  "weighted_activity": 11.4,
  "coverage": 0.82,
  "analysis_version": "topic-v3"
}
```

This is an activity profile. It must be labeled clearly and must not be
presented as a position estimate. Keep sponsor and cosponsor counts separate;
do not hide the aggregation formula behind a single `weight` field.

## OpenSearch Design

### `topic_catalog`

One document per canonical topic:

```text
id                  keyword, document ID
label               text + keyword
definition          text
level               keyword
parents             keyword array
related_topics      keyword array
confused_topics     keyword array
aliases             nested: {text, normalized, kind, weight}
status              keyword
taxonomy_version    keyword
reviewed_at         date
```

Use a versioned physical index and read alias. The catalog is application data,
so it should be searchable and accessible through an API.

### `analysis_annotation` additions

Retain the existing analysis metadata and add:

```text
topics              nested: {
  topic_id, direct, inherited, score, confidence, decision,
  model_id, topic_version, evidence_count
}
keywords            nested: {
  text, normalized, score, method, field, start, end
}
```

Nested mapping is required so topic fields and scores remain associated within
one topic result. Also store `topic_ids` as a flattened keyword array only if
simple filtering is needed and its denormalization is acceptable.

### Optional `topic_edge`

Prefer a dedicated association index once associations need pagination, review,
or member aggregation at scale:

```text
id                  keyword
source_id           keyword
source_index        keyword
topic_id            keyword
congress            integer
bioguide_ids        keyword array, optional denormalized activity targets
score               float
confidence          float
decision             keyword
direct              boolean
inherited           boolean
evidence             nested
model_id             keyword
analysis_version     keyword
generated_at         date
```

The edge index makes topic-to-document and topic-to-member queries explicit and
avoids treating OpenSearch as a relational join engine. Hydrate source records
with bounded `terms` queries.

### Queries and aggregates

- Filter legislation by `topic_id` and `decision=accepted`.
- Aggregate counts by Congress, chamber, committee, and date.
- Query `topic_edge` by `bioguide_id` plus Congress, then aggregate linked
  legislation through sponsorship edges.
- Store `analysis_aggregate` facts for trend charts, with source watermark and
  analysis version.
- Use exact topic IDs for filters and labels for display/search.

## Label Sources and Training Data

Use a source reliability hierarchy:

1. Human-reviewed labels with adjudication.
2. Congress.gov subjects, policy areas, and CRS topics as weak labels.
3. High-precision phrase rules.
4. Model predictions and embedding similarity.
5. Unsupervised cluster membership.

Do not treat weak labels as ground truth during evaluation. Build a stratified
review set containing:

- Each initial topic and its parents.
- Confusing pairs: abortion vs maternal health, LGBTQ+ rights vs general civil
  rights, human rights vs domestic civil rights, contraception vs abortion.
- Documents with generic terms and no target topic.
- Multiple-topic documents.
- Different source types, Congresses, chambers, and time periods.
- Long documents where only a small passage is relevant.

Annotators assign zero or more direct topics, optional parent topics, and
highlight evidence spans. They also mark `uncertain`, `out_of_scope`, and
`needs_new_topic`. Resolve disagreements with a second reviewer and maintain a
small adjudication guide with examples.

## Evaluation

Evaluate per topic and globally:

- Precision, recall, F1, and support for each topic.
- Micro, macro, and weighted multilabel F1.
- Precision at the chosen acceptance threshold.
- Recall at the review-queue threshold.
- Hamming loss, subset accuracy, and label ranking average precision where
  appropriate.
- Calibration error and reliability plots for confidence scores.
- Confusion matrices for known confusing pairs.
- Evidence-span precision: whether highlighted text actually supports the label.
- Hierarchical metrics that give partial credit for a correct parent but do not
  count it as a correct specific child.
- Temporal holdout evaluation to detect terminology drift.
- Slice metrics by source type, Congress, chamber, document length, and topic
  prevalence.

Set launch gates before training. An initial example target is at least 0.90
precision for sensitive specific topics, at least 0.80 recall on the reviewed
set, and no unresolved high-severity confusion pattern. The exact thresholds
must be agreed with reviewers; metrics should never be averaged in a way that
hides poor performance on a small topic.

## Implementation Phases

### Phase 0: Contract and corpus inventory

- Add topic-analysis configuration and analysis version constants.
- Inventory populated text fields and structured subject/topic fields per index.
- Define chunk sizes, field weights, language assumptions, and retention rules.
- Add an optional dependency group for spaCy, scikit-learn, and embedding tools;
  keep the base application install lean.
- Decide whether topic edges live in `analysis_annotation` initially or in a
  dedicated `topic_edge` index from the start.

Acceptance: a deterministic corpus manifest and a frozen v1 taxonomy schema.

### Phase 1: Taxonomy and deterministic baseline

- Add versioned taxonomy data and Pydantic models in `cdm/models/taxonomy.py`.
- Seed aliases, exclusions, positive examples, and hard negatives for the
  required distinctions.
- Implement normalization, phrase matching, source-label ingestion, and
  evidence offsets.
- Add unit tests for exact matches, ambiguous aliases, exclusions, parent
  propagation, and idempotent association IDs.

Acceptance: the baseline produces explainable associations and abstains on
ambiguous examples.

### Phase 2: Annotation and review workflow

- Create a review export containing source text, candidate topics, scores, and
  evidence.
- Build a small adjudicated dataset across source types and confusing pairs.
- Record reviewer decisions and taxonomy change requests.
- Add data-quality reports for orphan topic IDs, missing evidence, and stale
  model versions.

Acceptance: reviewers can accept, reject, or request a new topic without editing
canonical records.

### Phase 3: Supervised baseline

- Train TF-IDF n-gram plus one-vs-rest logistic regression as the transparent
  baseline.
- Combine title, subject, policy area, summary, and chunk text with explicit
  field weights.
- Calibrate thresholds per topic and implement abstention.
- Compare classifier output with deterministic and source-label signals.

Acceptance: baseline metrics meet the agreed launch gates on a held-out set.

### Phase 4: Semantic candidate retrieval

- Add sentence-transformer embeddings for chunks and topic descriptions or
  reviewed exemplars.
- Store embeddings only where OpenSearch vector search is justified; otherwise
  batch candidate retrieval can remain offline.
- Use embeddings to improve recall and route uncertain candidates to review.
- Measure ANN recall and latency before making vector search an application
  dependency.

Acceptance: semantic retrieval improves recall without unacceptable precision
loss or unexplained sensitive-topic errors.

### Phase 5: Production annotation and backfill

- Add an asynchronous analysis job with checkpoints, retries, and idempotent
  bulk upserts.
- Process high-value legislation, summaries, CRS reports, and committee
  materials first, then expand to records and communications.
- Write versioned annotations and topic edges; refresh aggregates only after
  successful writes.
- Backfill by Congress in bounded batches and record counts, failures, and
  source watermarks.

Acceptance: repeat runs produce the same IDs and values for the same source and
analysis versions, and partial failures resume safely.

### Phase 6: API and frontend integration

- Expand `TopicItem` in `cdm/contracts/api.py` with stable `topic_id`, label,
  score/confidence, direct/inherited state, and optional evidence summary.
- Add topic catalog, topic-filtered search, topic detail, and member activity
  topic endpoints to the backend.
- Keep frontend reads backend-only and regenerate frontend contracts from the
  API source.
- Present member topics as activity derived from sponsorship/cosponsorship and
  make the aggregation grain and Congress filter visible.

Acceptance: UI topic filters, document evidence, and member topic summaries
  agree with direct OpenSearch queries and expose analysis version metadata.

## Operational Controls

- Pin model packages and model artifact checksums.
- Store taxonomy, tokenizer, vectorizer, classifier, embedding model, and
  threshold versions with every result.
- Keep source text immutable in canonical records; derived annotations can be
  replaced by version.
- Add dead-letter handling for malformed documents and missing text.
- Log counts by source, topic, decision, confidence band, and model version.
- Monitor topic prevalence and keyword drift by Congress. Large unexplained
  changes trigger review rather than automatic taxonomy edits.
- Protect sensitive-topic evidence from unnecessary exposure in logs.
- Avoid generating labels from protected characteristics of members; topic
  associations describe records and activity only.

## Dependencies

Initial optional analysis group:

```text
spacy
scikit-learn
sentence-transformers
bertopic       # discovery workflow, not required by production inference
```

Use spaCy for linguistic annotations, scikit-learn for a transparent baseline,
and sentence-transformers only after a benchmark demonstrates value. BERTopic
and LDA/NMF should run in an offline research command or notebook, not in an API
request or the critical ingest path.

## Research Basis

The implementation choices are grounded in the following current references:

- spaCy linguistic features: tokenization, sentence segmentation, lemmatization,
  noun chunks, named entities, entity linking, and custom rule components:
  https://spacy.io/usage/linguistic-features
- scikit-learn decomposition and LDA/NMF topic extraction:
  https://scikit-learn.org/stable/modules/decomposition.html
- BERTopic architecture and documented variations, including embeddings,
  clustering, c-TF-IDF, guided/supervised/dynamic modes, and outlier handling:
  https://maartengr.github.io/BERTopic/
- Sentence Transformers semantic search, asymmetric query/document encoding,
  OpenSearch vector search, and retrieve-then-rerank patterns:
  https://www.sbert.net/examples/applications/semantic-search/README.html
- NLTK WordNet lexical relations and similarity methods, useful for exploratory
  synonym and hierarchy analysis but not sufficient as a congressional policy
  taxonomy:
  https://www.nltk.org/howto/wordnet.html
- Congress.gov subject terms should be treated as source metadata and weak
  supervision; exact endpoint availability and semantics must be verified
  against captured API payloads because the public help page is access-limited
  in some environments.

## Definition Of Done

- The v1 taxonomy is reviewed, versioned, and includes hard negatives for the
  required distinctions.
- Every accepted topic association has a stable ID, evidence, score/confidence,
  provenance, and model/taxonomy version.
- The pipeline is asynchronous, idempotent, resumable, and regenerable.
- A held-out multilabel evaluation set and confusion-pair report exist.
- OpenSearch mappings, aliases, API contracts, and aggregate queries are tested.
- Member topic profiles are activity aggregates and never unsupported position
  claims.
- Topic discovery methods can identify candidate taxonomy changes without
  silently changing production labels.
