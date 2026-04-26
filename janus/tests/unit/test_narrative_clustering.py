"""Narrative clustering — TF-IDF + KMeans correctness on toy descriptions."""

from __future__ import annotations

import numpy as np

from janus.features.narrative_clustering import (
    cluster_descriptions,
    cluster_from_embeddings,
)


def test_cluster_descriptions_groups_similar_projects() -> None:
    descriptions = {
        "AAA": "decentralized AI compute marketplace for training and inference",
        "BBB": "AI agent infrastructure with verifiable computation",
        "CCC": "tokenized real-world assets and credit markets",
        "DDD": "real estate fractional tokens on chain",
        "EEE": "meme token community",
        "FFF": "viral meme coin",
    }
    clusters = cluster_descriptions(descriptions, n_clusters=3, min_df=1)
    assert len(clusters) == 3

    # Find which cluster each ticker landed in.
    tkr_to_cluster = {t: c.cluster_id for c in clusters for t in c.tickers}
    # AI projects should cluster together; RWA projects together; memes together.
    assert tkr_to_cluster["AAA"] == tkr_to_cluster["BBB"]
    assert tkr_to_cluster["CCC"] == tkr_to_cluster["DDD"]
    assert tkr_to_cluster["EEE"] == tkr_to_cluster["FFF"]
    # And cross-narrative pairs differ.
    assert tkr_to_cluster["AAA"] != tkr_to_cluster["CCC"]


def test_cluster_from_embeddings_shape() -> None:
    rng = np.random.default_rng(0)
    # Two distinct clusters in 8-dim space.
    a = rng.normal(0, 0.1, size=(10, 8))
    b = rng.normal(5, 0.1, size=(10, 8))
    embeddings = np.vstack([a, b])
    tickers = [f"T{i:02d}" for i in range(20)]
    clusters = cluster_from_embeddings(embeddings, tickers, n_clusters=2, seed=42)
    assert len(clusters) == 2
    sizes = sorted(len(c.tickers) for c in clusters)
    assert sizes == [10, 10]


def test_cluster_falls_back_to_smaller_k_when_few_descriptions() -> None:
    descriptions = {"A": "alpha", "B": "beta"}
    clusters = cluster_descriptions(descriptions, n_clusters=10, min_df=1)
    assert len(clusters) >= 2
