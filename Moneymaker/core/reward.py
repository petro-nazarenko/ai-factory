"""Reward computation and gradient-style weight update.

Reward function
---------------
Payments dominate — every other signal is secondary.

    R = 20·payments + 5·mrr + 2·signups - 1·time_to_first_payment

Weight update (online gradient descent, no ML framework needed)
---------------------------------------------------------------
    w[f] += lr * v   if R > 0   (reinforce winning features)
    w[f] -= lr * 0.5 if R <= 0  (penalise losing features)

Weights are clamped to [0.1, 10.0] to prevent collapse or explosion.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_LR = 0.05
_W_MIN = 0.1
_W_MAX = 10.0


def compute_reward(metrics: dict) -> float:
    """Return a scalar reward from a metrics dict.

    Expected keys (all optional, default 0):
        payments, mrr, signups, time_to_first_payment
    """
    return (
        20.0 * metrics.get("payments", 0)
        + 5.0 * metrics.get("mrr", 0)
        + 2.0 * metrics.get("signups", 0)
        - 1.0 * metrics.get("time_to_first_payment", 0)
    )


def update_weights(
    features: dict[str, float],
    reward: float,
    weights: dict[str, float],
    lr: float = _LR,
) -> dict[str, float]:
    """Return a new weights dict adjusted by *reward* over *features*.

    Parameters
    ----------
    features:
        Feature vector for the idea that generated *reward*
        (e.g. {"source_reddit": 1, "format_landing_page": 1, "niche_saas": 1}).
    reward:
        Scalar reward from :func:`compute_reward`.
    weights:
        Current weight dict. Not mutated.
    lr:
        Learning rate (default 0.05).
    """
    updated = dict(weights)
    for feature, value in features.items():
        current = updated.get(feature, 1.0)
        if reward > 0:
            delta = lr * value * (reward / max(1.0, reward))  # normalised positive push
            updated[feature] = min(_W_MAX, current + delta)
        else:
            updated[feature] = max(_W_MIN, current - lr * 0.5)

    logger.debug(
        "Weight update — reward=%.2f | changed=%d features",
        reward,
        len(features),
    )
    return updated


def idea_features(source: str, mvp_format: str, target_user: str) -> dict[str, float]:
    """Build a feature vector for an idea — used as input to :func:`update_weights`."""
    features: dict[str, float] = {
        f"source_{source}": 1.0,
        f"format_{mvp_format}": 1.0,
    }
    # Crude niche extraction from target_user text
    niche_keywords = ["saas", "freelance", "ecommerce", "agency", "developer", "recruiter"]
    for kw in niche_keywords:
        if kw in target_user.lower():
            features[f"niche_{kw}"] = 1.0
    return features
