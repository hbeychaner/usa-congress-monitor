"""Clusters one topic's bills on the words that set their full text apart."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import normalize

from cdm.config import PerspectiveConfig
from cdm.perspectives.terms import Tokenizer

Matrix = NDArray[np.float32]
Labels = NDArray[np.intp]

MAX_DOCUMENT_SHARE = 0.5
MIN_DOCUMENTS = 3
MAX_FEATURES = 20000


@dataclass(frozen=True)
class ClusterResult:
    labels: Labels
    silhouette: float
    stability: float
    features: Matrix

    @property
    def count(self) -> int:
        return int(self.labels.max()) + 1

    def nearest(self, cluster: int, limit: int) -> list[int]:
        """Positions of the bills closest to the cluster's center."""
        members = np.flatnonzero(self.labels == cluster)
        center = self.features[members].mean(axis=0)
        distances = np.linalg.norm(self.features[members] - center, axis=1)
        return [int(members[position]) for position in np.argsort(distances)[:limit]]


class PerspectiveClusterer:
    """TF-IDF within the topic, reduced by SVD, split by the best KMeans silhouette."""

    def __init__(self, config: PerspectiveConfig, tokenizer: Tokenizer) -> None:
        self.config = config
        self.tokenizer = tokenizer

    def features(self, texts: Sequence[str]) -> Matrix | None:
        """Topic-relative word weights, so words every bill in the topic shares drop out."""
        vectorizer = TfidfVectorizer(
            analyzer=self.tokenizer.terms,  # pyright: ignore[reportArgumentType]
            sublinear_tf=True,
            min_df=MIN_DOCUMENTS,
            max_df=MAX_DOCUMENT_SHARE,
            max_features=MAX_FEATURES,
        )
        try:
            weights = vectorizer.fit_transform(texts)
        except ValueError:
            return None
        components = min(
            self.config.perspective_svd_dims, weights.shape[1] - 1, len(texts) - 1
        )
        if components < 2:
            return None
        reduced = TruncatedSVD(
            n_components=components, random_state=self.config.perspective_random_seed
        ).fit_transform(weights)
        return np.asarray(normalize(reduced), dtype=np.float32)

    def cluster(self, texts: Sequence[str]) -> ClusterResult | None:
        """The best-scoring split into 2+ sufficiently large clusters, or None if none exists."""
        config = self.config
        features = self.features(texts)
        if features is None:
            return None
        most = min(
            config.perspective_max_clusters,
            len(features) // config.perspective_min_cluster_bills,
        )
        best: tuple[int, Labels, float] | None = None
        for count in range(2, most + 1):
            labels = self._fit(features, count, config.perspective_random_seed)
            if np.bincount(labels).min() < config.perspective_min_cluster_bills:
                continue
            score = float(silhouette_score(features, labels))
            if best is None or score > best[2]:
                best = (count, labels, score)
        if best is None:
            return None
        count, labels, score = best
        return ClusterResult(
            labels=labels,
            silhouette=score,
            stability=self._stability(features, count, labels),
            features=features,
        )

    @staticmethod
    def _fit(features: Matrix, count: int, seed: int) -> Labels:
        model = KMeans(n_clusters=count, n_init=10, random_state=seed)  # pyright: ignore[reportArgumentType]
        return model.fit_predict(features).astype(np.intp)

    def _stability(self, features: Matrix, count: int, labels: Labels) -> float:
        """Mean agreement (adjusted Rand) between the chosen split and refits on other seeds."""
        seed = self.config.perspective_random_seed
        scores = [
            adjusted_rand_score(labels, self._fit(features, count, seed + offset))
            for offset in range(1, self.config.perspective_stability_runs + 1)
        ]
        return float(np.mean(scores))
