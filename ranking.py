"""Ranking engine for DeepFeed.

This module implements the ranking framework that was outlined during the
product discovery session.  The goal is to encapsulate the scoring logic in a
set of composable, well-documented functions so the rest of the application can
ask for ranked recommendations while also obtaining the intermediate factors
needed for transparency ("Why Recommended" labels) and analytics.

The implementation below intentionally keeps the primitives lightweight and
framework agnostic: the data structures are standard dataclasses and the core
functions are pure Python.  This keeps the module easy to unit test and
portable regardless of whether the surrounding stack uses Flask, FastAPI, or
Next.js.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, MutableMapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Data models


@dataclass(slots=True)
class ContentItem:
    """Representation of a single piece of long-form content.

    Attributes
    ----------
    id:
        Stable identifier that can be used to map back to the persistent
        storage layer.
    topics:
        Sparse topic vector keyed by topic identifier (e.g. "machine-learning").
        Each value is expected to be in the range [0, 1] and the vector does not
        have to be normalised – cosine similarity will take care of that.
    source_id:
        Identifier of the originating source (podcast, magazine, newsletter,…).
    source_trust:
        Raw Source Trust Score prior to normalisation.  The score can be any
        numeric value; the :func:`normalise_trust_score` helper maps it to
        0–1.
    depth_score:
        Normalised representation of how in-depth the content is (longer word
        counts / running times should produce values closer to 1).
    has_supporting_material:
        Boolean flag indicating whether the piece provides transcripts,
        citations or downloadable notes.
    user_feedback:
        Optional explicit feedback collected from DeepFeed users.  The value is
        expected in the range [0, 1], where higher is better.
    published_at:
        Timestamp of publication.  Used for the recency boost.
    queue_state:
        If the item is already in the user queue we can apply staleness
        penalties.  Allowed values: "new", "saved", "reading", "finished".
    saved_since:
        Timestamp marking when the content was saved by the user.  Required for
        staleness calculations when ``queue_state == "saved"``.
    custom_quality_override:
        Optional manual override.  This can be used by editorial tooling to
        tweak the quality composite; when ``None`` the automated computation is
        used.
    """

    id: str
    topics: Dict[str, float]
    source_id: str
    source_trust: float
    depth_score: float
    has_supporting_material: bool
    user_feedback: Optional[float]
    published_at: dt.datetime
    queue_state: str = "new"
    saved_since: Optional[dt.datetime] = None
    custom_quality_override: Optional[float] = None


@dataclass(slots=True)
class UserProfile:
    """Snapshot of a user's preference configuration."""

    user_id: str
    interest_vector: Dict[str, float]
    flexibility: float  # Slider value between 0 and 100.
    explore_quota: int
    explore_shown_today: int


@dataclass(slots=True)
class UserEngagement:
    """Aggregated behavioural signals over a recent time window."""

    topic_scores: Dict[str, float] = dataclasses.field(default_factory=dict)
    source_scores: Dict[str, float] = dataclasses.field(default_factory=dict)
    global_score: float = 0.0


@dataclass(slots=True)
class SessionContext:
    """State required to enforce diversity and redundancy penalties."""

    seen_topics: MutableMapping[str, int] = field(default_factory=dict)
    seen_sources: MutableMapping[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class RankingWeights:
    """Tunable weight configuration used during scoring."""

    interest: float = 0.45
    trust: float = 0.35
    quality: float = 0.20

    def __post_init__(self) -> None:
        total = self.interest + self.trust + self.quality
        if not math.isclose(total, 1.0, rel_tol=1e-6):
            raise ValueError(
                "RankingWeights must add up to 1.0; received "
                f"{self.interest:.3f} + {self.trust:.3f} + {self.quality:.3f} = {total:.3f}"
            )


@dataclass(slots=True)
class RankingConfig:
    """Configuration knobs used by :func:`score_item`."""

    weights: RankingWeights = field(default_factory=RankingWeights)
    recency_window_days: int = 7
    recency_boost: float = 0.10
    max_engagement_boost: float = 0.25
    engagement_weight: float = 0.25
    explore_penalty_weight: float = 0.35
    redundancy_penalty_weight: float = 0.30
    staleness_penalty_weight: float = 0.20
    trust_floor: float = 0.30
    trust_min: float = 0.0
    trust_max: float = 100.0
    staleness_days: int = 14


@dataclass(slots=True)
class ScoreBreakdown:
    """Container describing the contribution of each scoring component."""

    base_relevance: float
    interest_fit: float
    trust_norm: float
    quality: float
    boosts: Dict[str, float]
    penalties: Dict[str, float]
    final_score: float
    is_explore: bool


# ---------------------------------------------------------------------------
# Vector helpers


def _cosine_similarity(
    vector_a: MutableMapping[str, float],
    vector_b: MutableMapping[str, float],
) -> float:
    """Compute cosine similarity between two sparse vectors.

    The helper gracefully handles zero vectors and returns 0.0 in that case.
    """

    dot_product = 0.0
    for key, value in vector_a.items():
        dot_product += value * vector_b.get(key, 0.0)

    magnitude_a = math.sqrt(sum(value * value for value in vector_a.values()))
    magnitude_b = math.sqrt(sum(value * value for value in vector_b.values()))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


def _is_off_topic(
    user_profile: UserProfile,
    content: ContentItem,
    similarity: float,
    overlap_threshold: float = 1e-6,
) -> bool:
    """Determine whether a piece of content should be considered off-topic.

    Off-topic in this context means that the content does not meaningfully
    overlap with the user's declared interests.  We look at the raw overlap
    (before cosine normalisation) to avoid flagging low-similarity but still
    related items as explore content.
    """

    overlap = 0.0
    for topic, interest_weight in user_profile.interest_vector.items():
        overlap += interest_weight * content.topics.get(topic, 0.0)
    return overlap <= overlap_threshold or similarity <= overlap_threshold


# ---------------------------------------------------------------------------
# Score components


def interest_fit(user_profile: UserProfile, content: ContentItem) -> tuple[float, bool]:
    """Compute the interest fit and determine whether the item counts as explore."""

    similarity = _cosine_similarity(user_profile.interest_vector, content.topics)
    off_topic = _is_off_topic(user_profile, content, similarity)

    if not off_topic:
        return similarity, False

    # Flexibility controls the cap between 0.4 and 0.8.
    flexibility_ratio = max(0.0, min(user_profile.flexibility, 100.0)) / 100.0
    cap = 0.4 + (0.8 - 0.4) * flexibility_ratio
    return min(similarity, cap), True


def normalise_trust_score(config: RankingConfig, raw_score: float) -> float:
    """Map a raw trust score to the [0, 1] range using min-max scaling."""

    span = max(config.trust_max - config.trust_min, 1e-6)
    normalised = (raw_score - config.trust_min) / span
    clamped = max(config.trust_floor, min(1.0, normalised))
    return clamped


def compute_quality(content: ContentItem) -> float:
    """Blend depth, supporting material and feedback into a single score."""

    if content.custom_quality_override is not None:
        return content.custom_quality_override

    depth_component = max(0.0, min(1.0, content.depth_score))
    materials_component = 1.0 if content.has_supporting_material else 0.0
    feedback_component = content.user_feedback if content.user_feedback is not None else 0.5

    # Weighted average emphasising depth, but rewarding extra learning aids.
    return 0.6 * depth_component + 0.2 * materials_component + 0.2 * feedback_component


def engagement_boost(
    config: RankingConfig,
    engagement: UserEngagement,
    content: ContentItem,
) -> float:
    """Boost score when the user consistently engages with the topic/source."""

    topic_component = max(
        engagement.topic_scores.get(topic, 0.0) for topic in content.topics.keys()
    )
    source_component = engagement.source_scores.get(content.source_id, 0.0)
    aggregated = 0.5 * topic_component + 0.3 * source_component + 0.2 * engagement.global_score
    boost = config.engagement_weight * aggregated
    return min(config.max_engagement_boost, boost)


def recency_boost(config: RankingConfig, content: ContentItem, now: dt.datetime) -> float:
    """Boost new items so the feed stays fresh."""

    age = now - content.published_at
    if age <= dt.timedelta(days=config.recency_window_days):
        return config.recency_boost
    return 0.0


def explore_penalty(
    config: RankingConfig,
    user_profile: UserProfile,
    is_explore: bool,
) -> float:
    """Dynamic penalty ensuring explore content respects the daily quota."""

    if not is_explore or user_profile.explore_quota <= 0:
        return 0.0

    ratio = user_profile.explore_shown_today / max(1, user_profile.explore_quota)
    overflow = max(0.0, ratio - 1.0)
    return config.explore_penalty_weight * overflow


def redundancy_penalty(
    config: RankingConfig,
    session: SessionContext,
    content: ContentItem,
) -> float:
    """Penalty to avoid clustering identical topics or sources."""

    topic_overlap = max(session.seen_topics.get(topic, 0) for topic in content.topics.keys())
    source_overlap = session.seen_sources.get(content.source_id, 0)

    redundancy = 0.0
    if topic_overlap:
        redundancy += min(1.0, topic_overlap / 3)
    if source_overlap:
        redundancy += min(1.0, source_overlap / 2)

    return config.redundancy_penalty_weight * min(1.0, redundancy)


def staleness_penalty(config: RankingConfig, content: ContentItem, now: dt.datetime) -> float:
    """Penalty for items that were saved but never started."""

    if content.queue_state != "saved" or not content.saved_since:
        return 0.0

    age = now - content.saved_since
    if age <= dt.timedelta(days=config.staleness_days):
        return 0.0

    # Scale linearly after the threshold and clamp at the configured maximum.
    overdue_days = age.days - config.staleness_days
    scale = min(1.0, overdue_days / config.staleness_days)
    return config.staleness_penalty_weight * scale


# ---------------------------------------------------------------------------
# Ranking orchestration


def score_item(
    *,
    content: ContentItem,
    user_profile: UserProfile,
    engagement: UserEngagement,
    session: SessionContext,
    config: RankingConfig,
    now: Optional[dt.datetime] = None,
) -> ScoreBreakdown:
    """Compute the ranking score for a single content item.

    The function is intentionally verbose: instead of returning only the final
    score we expose the intermediate components so the caller can surface rich
    explanations alongside each feed card.
    """

    now = now or dt.datetime.utcnow()

    interest, is_explore = interest_fit(user_profile, content)
    trust_norm = normalise_trust_score(config, content.source_trust)
    quality = compute_quality(content)

    base_relevance = (
        config.weights.interest * interest
        + config.weights.trust * trust_norm
        + config.weights.quality * quality
    )

    boosts: Dict[str, float] = {}
    penalties: Dict[str, float] = {}

    eng_boost = engagement_boost(config, engagement, content)
    if eng_boost:
        boosts["engagement"] = eng_boost

    rec_boost = recency_boost(config, content, now)
    if rec_boost:
        boosts["recency"] = rec_boost

    exp_penalty = explore_penalty(config, user_profile, is_explore)
    if exp_penalty:
        penalties["explore"] = exp_penalty

    red_penalty = redundancy_penalty(config, session, content)
    if red_penalty:
        penalties["redundancy"] = red_penalty

    stale_penalty = staleness_penalty(config, content, now)
    if stale_penalty:
        penalties["staleness"] = stale_penalty

    boost_factor = 1.0 + sum(boosts.values())
    penalty_factor = max(0.0, 1.0 - sum(penalties.values()))
    final_score = base_relevance * boost_factor * penalty_factor

    return ScoreBreakdown(
        base_relevance=base_relevance,
        interest_fit=interest,
        trust_norm=trust_norm,
        quality=quality,
        boosts=boosts,
        penalties=penalties,
        final_score=final_score,
        is_explore=is_explore,
    )


def update_session_context(session: SessionContext, content: ContentItem) -> None:
    """Record that the content was surfaced so subsequent items can be penalised."""

    for topic in content.topics.keys():
        session.seen_topics[topic] = session.seen_topics.get(topic, 0) + 1
    session.seen_sources[content.source_id] = session.seen_sources.get(content.source_id, 0) + 1


def rank_feed(
    contents: Sequence[ContentItem],
    *,
    user_profile: UserProfile,
    engagement: UserEngagement,
    config: RankingConfig | None = None,
    now: Optional[dt.datetime] = None,
    diversify: bool = True,
) -> List[ScoreBreakdown]:
    """Return ranked content with score explanations.

    Parameters
    ----------
    contents:
        Collection of candidate items to be scored.
    user_profile / engagement:
        User-specific context that drives personalisation.
    config:
        Optional override for ranking parameters.
    now:
        Timestamp used for deterministic testing.
    diversify:
        When True a simple greedy diversification pass is applied to avoid
        presenting many cards from the same topic or source back-to-back.
    """

    config = config or RankingConfig()
    now = now or dt.datetime.utcnow()
    session = SessionContext()

    scored_items = [
        (content, score_item(
            content=content,
            user_profile=user_profile,
            engagement=engagement,
            session=session,
            config=config,
            now=now,
        ))
        for content in contents
    ]

    # Sort by final score (descending) while keeping deterministic tie-breaking.
    scored_items.sort(key=lambda item: item[1].final_score, reverse=True)

    if not diversify:
        for content, _ in scored_items:
            update_session_context(session, content)
        return [score for _, score in scored_items]

    diversified: List[ScoreBreakdown] = []
    temp_session = SessionContext()
    for content, score in scored_items:
        update_session_context(temp_session, content)

    # Greedy diversification: iteratively pick the best remaining item that does
    # not exceed topic/source repetition thresholds.  If none qualify we relax
    # the constraint.
    remaining = list(scored_items)
    session = SessionContext()
    while remaining:
        remaining.sort(key=lambda item: item[1].final_score, reverse=True)
        picked_index = None
        for idx, (candidate, _) in enumerate(remaining):
            topic_overlap = max(session.seen_topics.get(t, 0) for t in candidate.topics.keys())
            source_overlap = session.seen_sources.get(candidate.source_id, 0)
            if topic_overlap < 2 and source_overlap < 2:
                picked_index = idx
                break

        if picked_index is None:
            picked_index = 0

        content, score = remaining.pop(picked_index)
        diversified.append(score)
        update_session_context(session, content)

    return diversified


# ---------------------------------------------------------------------------
# Convenience helpers for onboarding defaults


def default_interest_vector(topics: Iterable[str]) -> Dict[str, float]:
    """Create a balanced interest vector from a list of topics."""

    topics = list(topics)
    if not topics:
        return {}
    weight = 1.0 / len(topics)
    return {topic: weight for topic in topics}


def derive_explore_quota(feed_size: int, flexibility: float) -> int:
    """Determine the daily explore quota based on feed size and flexibility."""

    flexibility_ratio = max(0.0, min(flexibility, 100.0)) / 100.0
    explore_cap = 0.20 * (0.5 + 0.5 * flexibility_ratio)  # up to the 20% limit
    return max(1, round(feed_size * explore_cap))


__all__ = [
    "ContentItem",
    "UserProfile",
    "UserEngagement",
    "SessionContext",
    "RankingWeights",
    "RankingConfig",
    "ScoreBreakdown",
    "default_interest_vector",
    "derive_explore_quota",
    "rank_feed",
    "score_item",
]

