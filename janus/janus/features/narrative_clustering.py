"""Embedding-based narrative clustering (UPGRADES §2.1).

Why this exists:
- Manual YAML tagging (Phase 0 starter) doesn't scale and introduces
  retrospective bias — we tag with knowledge that didn't exist at the time.
- A scalable approach: feed each project's *contemporaneous* description
  (CoinGecko / Messari / GitHub README at-the-time snapshots) into a text
  encoder and cluster. The clusters become the narrative tags.

Implementation:
- Phase 0 ships TF-IDF + KMeans (no heavy NLP deps; sklearn is already in deps).
- Phase 2 production swap-in: precompute Sentence-BERT embeddings offline,
  store in Parquet, load here. Same `cluster_descriptions()` interface.

The function returns a `narrative_id -> [tickers...]` mapping plus a
human-readable label per cluster (top TF-IDF tokens — useful for debugging).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True, slots=True)
class NarrativeCluster:
    cluster_id: int
    label: str          # human-readable: top 3 TF-IDF terms
    tickers: tuple[str, ...]


def cluster_descriptions(
    descriptions: Mapping[str, str],
    *,
    n_clusters: int = 12,
    min_df: int = 2,
    seed: int = 42,
) -> list[NarrativeCluster]:
    """Cluster projects by their textual descriptions.

    Args:
        descriptions: mapping of {ticker: description_text}
        n_clusters:   target number of narratives. The plan calls for "10-15
                       active narratives" — pick from this range.
    """
    tickers = list(descriptions.keys())
    texts = [descriptions[t] for t in tickers]
    if len(tickers) < n_clusters:
        n_clusters = max(2, len(tickers) // 2)

    vectorizer = TfidfVectorizer(
        max_features=2_000,
        stop_words="english",
        min_df=min_df,
        ngram_range=(1, 2),
    )
    X = vectorizer.fit_transform(texts)

    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init="auto")
    labels = km.fit_predict(X)

    feature_names = np.array(vectorizer.get_feature_names_out())
    centroids = km.cluster_centers_   # (n_clusters, n_terms)
    out: list[NarrativeCluster] = []
    for cid in range(n_clusters):
        members = tuple(t for t, c in zip(tickers, labels, strict=True) if c == cid)
        # Top 3 tokens by centroid weight.
        top_idx = centroids[cid].argsort()[::-1][:3]
        label = " / ".join(feature_names[top_idx])
        out.append(NarrativeCluster(cluster_id=cid, label=label, tickers=members))
    return out


def cluster_from_embeddings(
    embeddings: np.ndarray,
    tickers: Sequence[str],
    *,
    n_clusters: int = 12,
    seed: int = 42,
) -> list[NarrativeCluster]:
    """Cluster pre-computed embeddings (e.g. Sentence-BERT vectors).

    Use this in production once embeddings are precomputed offline. Same
    output shape as `cluster_descriptions`; labels are empty (the caller
    can label clusters with their semantic centroid).
    """
    if len(tickers) != embeddings.shape[0]:
        raise ValueError("len(tickers) must equal embeddings.shape[0]")
    if len(tickers) < n_clusters:
        n_clusters = max(2, len(tickers) // 2)
    km = KMeans(n_clusters=n_clusters, random_state=seed, n_init="auto")
    labels = km.fit_predict(embeddings)
    return [
        NarrativeCluster(
            cluster_id=cid, label="",
            tickers=tuple(t for t, c in zip(tickers, labels, strict=True) if c == cid),
        )
        for cid in range(n_clusters)
    ]
