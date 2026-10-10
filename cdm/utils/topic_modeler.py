"""Batch BERTopic modeling over legislation titles and summaries.

Discovery-phase tooling per planning/TOPIC_ANALYSIS_IMPLEMENTATION_PLAN.md:
the model informs taxonomy work and drift detection; it does not produce
canonical production labels. The corpus is bounded (bills back to 1949 with a
small daily trickle), so a full batch fit plus ``topics_over_time`` gives far
better topics than online ``partial_fit`` (which forces a fixed cluster count
and loses HDBSCAN outlier handling). New documents are assigned with
``transform``; periodic refits (or ``merge_models``) pick up genuinely new
topics.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from bertopic import BERTopic
from bertopic.representation import MaximalMarginalRelevance
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

from cdm.store.embedding_store import EmbeddingStore
from cdm.utils.cached_embedder import EMBED_CHUNK_SIZE, CachedEmbedder, EmbeddingJob
from cdm.utils.metasubjects import TopicVector
from cdm.utils.topic_records import TopicSummaryRow, TopicTimeBin
from cdm.utils.topic_terms import dedupe_terms, keyword_label

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

# Legislative boilerplate that otherwise dominates c-TF-IDF representations.
BOILERPLATE_STOPWORDS = [
    "act",
    "acts",
    "amend",
    "amended",
    "amendment",
    "amendments",
    "bill",
    "code",
    "congress",
    "designate",
    "entitled",
    "expressing",
    "federal",
    "law",
    "prohibit",
    "provide",
    "public",
    "purposes",
    "recognizing",
    "relating",
    "require",
    "resolution",
    "section",
    "sense",
    "states",
    "title",
    "united",
    "authorize",
    "authorizes",
    "certain",
    "direct",
    "directs",
    "establish",
    "establishes",
    "fiscal",
    "make",
    "makes",
    "secretary",
    "shall",
    "year",
    "years",
]

TOP_N_WORDS = 15

# Alphabetic words of 3+ letters, so years and other numbers never become keywords.
ALPHA_TOKEN_PATTERN = r"(?u)\b[^\W\d_]{3,}\b"


@dataclass(frozen=True)
class TopicDocument:
    """One unit of text to model, tied back to a canonical document.

    ``text`` feeds the vectorizer (topic words) and should be lemmatized when
    available; ``embed_text`` feeds the sentence embedder and should stay
    natural language (embedders degrade on lemmatized text). When
    ``embed_text`` is empty, ``text`` is embedded instead.
    """

    doc_id: str
    text: str
    timestamp: datetime | None = None
    embed_text: str = ""

    @property
    def embedding_input(self) -> str:
        return self.embed_text or self.text


@dataclass(frozen=True)
class TopicAssignment:
    doc_id: str
    topic_id: int
    probability: float


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", _HTML_TAG.sub(" ", html.unescape(text))).strip()


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _latest_summary_text(source: dict[str, Any]) -> tuple[str, str]:
    """Return (raw, lemma) text of the summary with the latest action date."""
    summaries = source.get("summaries") or []
    dated = []
    for summary in summaries:
        text = _clean(str(summary.get("text") or ""))
        if text:
            lemma = _clean(str(summary.get("text_lemma") or ""))
            dated.append((str(summary.get("action_date") or ""), text, lemma))
    if not dated:
        return "", ""
    _, text, lemma = max(dated, key=lambda entry: entry[0])
    return text, lemma


def _join(first: str, second: str) -> str:
    return f"{first}. {second}" if first and second else (first or second)


def _subject_terms(source: dict[str, Any]) -> str:
    """CRS policy area + legislative subject names as a text fragment."""
    terms: list[str] = []
    policy_area = (source.get("policy_area") or {}).get("name")
    if policy_area:
        terms.append(str(policy_area))
    subjects = (source.get("subjects") or {}).get("legislative_subjects") or []
    for subject in subjects:
        name = (subject or {}).get("name")
        if name:
            terms.append(str(name))
    return "; ".join(dict.fromkeys(terms))


def build_topic_documents(hits: list[dict[str, Any]]) -> list[TopicDocument]:
    """Build model inputs (title + latest summary + CRS subjects) from hits.

    ``text`` prefers the ``*_lemma`` sibling fields (falling back to raw text
    per field) so topic words come from lemmas, while ``embed_text`` keeps the
    raw text for the embedder. Hits without any usable text are dropped. The
    timestamp prefers ``introduced_date`` and falls back to
    ``latest_action.action_date`` so topics-over-time bins reflect when the
    measure entered Congress.
    """
    documents = []
    for hit in hits:
        source = hit.get("_source") or {}
        title = _clean(str(source.get("title") or ""))
        title_lemma = _clean(str(source.get("title_lemma") or ""))
        summary, summary_lemma = _latest_summary_text(source)
        subjects = _subject_terms(source)
        raw_text = _join(_join(title, summary), subjects)
        lemma_text = _join(
            _join(title_lemma or title, summary_lemma or summary), subjects
        )
        if not lemma_text:
            continue
        latest_action = source.get("latest_action") or {}
        timestamp = _parse_date(source.get("introduced_date")) or _parse_date(
            latest_action.get("action_date")
        )
        documents.append(
            TopicDocument(
                doc_id=str(hit.get("_id")),
                text=lemma_text,
                timestamp=timestamp,
                embed_text=raw_text,
            )
        )
    return documents


class TopicModeler:
    """Fit, persist, and apply a BERTopic model over :class:`TopicDocument`s."""

    def __init__(
        self,
        *,
        embedding_model: str = "all-mpnet-base-v2",
        min_topic_size: int = 25,
        nr_topics: int | str | None = None,
        embedding_store: EmbeddingStore | None = None,
    ) -> None:
        self.embedding_model_name = embedding_model
        self.min_topic_size = min_topic_size
        self.nr_topics = nr_topics
        self.embedding_store = embedding_store
        self._model: Any = None
        self._embedding_model: Any = None
        self._documents: list[TopicDocument] = []
        self._topics: list[int] = []
        self._embeddings: np.ndarray | None = None

    def _embedder(self) -> Any:
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        return self._embedding_model

    def _embed(
        self,
        documents: list[TopicDocument],
        on_progress: Callable[[float], None] | None,
    ) -> np.ndarray:
        if self.embedding_store is not None:
            cached = CachedEmbedder(self.embedding_store, self._embedder)
            jobs = [EmbeddingJob(doc.doc_id, doc.embedding_input) for doc in documents]
            return cached.embed(jobs, on_progress)
        embedder = self._embedder()
        texts = [doc.embedding_input for doc in documents]
        batches = []
        for start in range(0, len(texts), EMBED_CHUNK_SIZE):
            batches.append(
                embedder.encode(
                    texts[start : start + EMBED_CHUNK_SIZE], show_progress_bar=False
                )
            )
            if on_progress:
                on_progress(min(1.0, (start + EMBED_CHUNK_SIZE) / len(texts)))
        return np.vstack(batches)

    def fit(
        self,
        documents: list[TopicDocument],
        on_embed_progress: Callable[[float], None] | None = None,
    ) -> list[TopicAssignment]:
        """Train on the full corpus and return per-document assignments."""
        if not documents:
            raise ValueError("no documents to fit")
        self._documents = documents
        stop_words = list(ENGLISH_STOP_WORDS.union(BOILERPLATE_STOPWORDS))
        embedder = self._embedder()
        self._model = BERTopic(
            embedding_model=embedder,
            vectorizer_model=CountVectorizer(
                stop_words=stop_words,
                ngram_range=(1, 2),
                min_df=5,
                token_pattern=ALPHA_TOKEN_PATTERN,
            ),
            representation_model=MaximalMarginalRelevance(diversity=0.4),
            min_topic_size=self.min_topic_size,
            nr_topics=self.nr_topics,
            top_n_words=TOP_N_WORDS,
            calculate_probabilities=False,
            verbose=True,
        )
        embeddings = self._embed(documents, on_embed_progress)
        self._embeddings = embeddings
        topics, probabilities = self._model.fit_transform(
            [doc.text for doc in documents], embeddings=embeddings
        )
        self._topics = [int(topic) for topic in topics]
        return _assignments(documents, topics, probabilities)

    def transform(self, documents: list[TopicDocument]) -> list[TopicAssignment]:
        """Assign topics to new documents without refitting."""
        self._require_model()
        embeddings = self._embedder().encode([doc.embedding_input for doc in documents])
        topics, probabilities = self._model.transform(
            [doc.text for doc in documents], embeddings=embeddings
        )
        return _assignments(documents, topics, probabilities)

    def topics_over_time(self, *, nr_bins: int = 60) -> list[TopicTimeBin]:
        """Topic frequency and evolving words across time bins of the fit corpus."""
        self._require_model()
        dated = [
            (doc, topic)
            for doc, topic in zip(self._documents, self._topics)
            if doc.timestamp is not None
        ]
        if not dated:
            raise ValueError("no fitted documents carry timestamps")
        frame = self._model.topics_over_time(
            [doc.text for doc, _ in dated],
            [doc.timestamp for doc, _ in dated],
            topics=[topic for _, topic in dated],
            nr_bins=nr_bins,
        )
        return [
            TopicTimeBin(
                topic_id=int(row.Topic),
                words=str(row.Words),
                frequency=int(row.Frequency),
                timestamp=row.Timestamp.isoformat(),
            )
            for row in frame.itertuples()
        ]

    def topic_summaries(self) -> list[TopicSummaryRow]:
        """One row per topic: id, generated name, size, and top words."""
        self._require_model()
        info = self._model.get_topic_info()
        summaries: list[TopicSummaryRow] = []
        for row in info.itertuples():
            topic_id = int(row.Topic)
            words = dedupe_terms(
                word for word, _ in (self._model.get_topic(row.Topic) or [])
            )
            name = str(row.Name)
            if topic_id != -1 and words:
                name = f"{topic_id}_{keyword_label(words).replace(' ', '_')}"
            summaries.append(
                TopicSummaryRow(
                    topic_id=topic_id, name=name, size=int(row.Count), top_words=words
                )
            )
        return summaries

    def document_embeddings(self) -> np.ndarray:
        """Embeddings of the fitted documents, in fit order."""
        self._require_model()
        if self._embeddings is None:
            raise RuntimeError(
                "embeddings are only available on a freshly fitted model"
            )
        return self._embeddings

    def topic_vectors(self, summaries: list[TopicSummaryRow]) -> list[TopicVector]:
        """Centroid embedding per topic, joined with the summaries' text fields."""
        self._require_model()
        embeddings = np.asarray(self._model.topic_embeddings_)
        rows = {
            topic_id: row
            for row, topic_id in enumerate(sorted(self._model.get_topics()))
        }
        return [
            TopicVector(
                topic_id=summary.topic_id,
                size=summary.size,
                label=summary.label or summary.name,
                top_words=summary.top_words,
                vector=embeddings[rows[summary.topic_id]],
            )
            for summary in summaries
        ]

    def representative_docs(self) -> dict[int, list[str]]:
        """Most representative document texts per topic (for labeling)."""
        self._require_model()
        docs = self._model.get_representative_docs() or {}
        return {int(topic_id): list(texts or []) for topic_id, texts in docs.items()}

    def save(self, path: Path | str) -> None:
        self._require_model()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._model.save(
            str(path),
            serialization="safetensors",
            save_ctfidf=True,
            save_embedding_model=False,
        )

    @classmethod
    def load(cls, path: Path | str, **kwargs: Any) -> TopicModeler:
        modeler = cls(**kwargs)
        modeler._model = BERTopic.load(str(path), embedding_model=modeler._embedder())
        return modeler

    def _require_model(self) -> None:
        if self._model is None:
            raise RuntimeError("model is not fitted or loaded")


def _assignments(
    documents: list[TopicDocument],
    topics: Any,
    probabilities: Any,
) -> list[TopicAssignment]:
    results = []
    for index, doc in enumerate(documents):
        probability = 0.0
        if probabilities is not None:
            value = probabilities[index]
            probability = float(value.max() if hasattr(value, "max") else value)
        results.append(
            TopicAssignment(
                doc_id=doc.doc_id,
                topic_id=int(topics[index]),
                probability=probability,
            )
        )
    return results
