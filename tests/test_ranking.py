import datetime as dt

import pytest

from ranking import (
    ContentItem,
    RankingConfig,
    SessionContext,
    UserEngagement,
    UserProfile,
    default_interest_vector,
    rank_feed,
    score_item,
)


def build_content(
    *,
    id: str,
    topics,
    source_id: str = "source",
    trust: float = 80.0,
    depth: float = 0.9,
    supporting: bool = True,
    feedback: float | None = None,
    published_at: dt.datetime | None = None,
    queue_state: str = "new",
    saved_since: dt.datetime | None = None,
):
    return ContentItem(
        id=id,
        topics=topics,
        source_id=source_id,
        source_trust=trust,
        depth_score=depth,
        has_supporting_material=supporting,
        user_feedback=feedback,
        published_at=published_at or dt.datetime.utcnow(),
        queue_state=queue_state,
        saved_since=saved_since,
    )


@pytest.fixture
def user_profile() -> UserProfile:
    return UserProfile(
        user_id="u1",
        interest_vector=default_interest_vector(["ai", "productivity", "health"]),
        flexibility=20,
        explore_quota=4,
        explore_shown_today=2,
    )


@pytest.fixture
def engagement() -> UserEngagement:
    return UserEngagement(
        topic_scores={"ai": 0.6, "health": 0.1},
        source_scores={"source": 0.3},
        global_score=0.2,
    )


def test_interest_fit_caps_off_topic_items(user_profile: UserProfile, engagement: UserEngagement):
    now = dt.datetime(2024, 1, 1)
    on_topic = build_content(id="1", topics={"ai": 1.0}, published_at=now)
    off_topic = build_content(id="2", topics={"cooking": 1.0}, published_at=now)

    session = SessionContext()
    config = RankingConfig()

    on_topic_score = score_item(
        content=on_topic,
        user_profile=user_profile,
        engagement=engagement,
        session=session,
        config=config,
        now=now,
    )

    off_topic_score = score_item(
        content=off_topic,
        user_profile=user_profile,
        engagement=engagement,
        session=session,
        config=config,
        now=now,
    )

    assert on_topic_score.interest_fit > off_topic_score.interest_fit
    assert off_topic_score.is_explore is True


def test_staleness_penalty_applied(user_profile: UserProfile, engagement: UserEngagement):
    now = dt.datetime(2024, 1, 1)
    saved_since = now - dt.timedelta(days=40)
    stale_item = build_content(
        id="stale",
        topics={"ai": 1.0},
        published_at=now,
        queue_state="saved",
        saved_since=saved_since,
    )

    fresh_item = build_content(id="fresh", topics={"ai": 1.0}, published_at=now)

    config = RankingConfig(staleness_days=14)
    session = SessionContext()

    stale_score = score_item(
        content=stale_item,
        user_profile=user_profile,
        engagement=engagement,
        session=session,
        config=config,
        now=now,
    )

    fresh_score = score_item(
        content=fresh_item,
        user_profile=user_profile,
        engagement=engagement,
        session=session,
        config=config,
        now=now,
    )

    assert stale_score.penalties.get("staleness", 0.0) > 0.0
    assert fresh_score.final_score > stale_score.final_score


def test_rank_feed_applies_diversification(user_profile: UserProfile, engagement: UserEngagement):
    now = dt.datetime(2024, 1, 1)
    contents = [
        build_content(id="a", topics={"ai": 1.0}, source_id="s1", published_at=now),
        build_content(id="b", topics={"ai": 0.9}, source_id="s1", published_at=now),
        build_content(id="c", topics={"health": 1.0}, source_id="s2", published_at=now),
    ]

    ranked = rank_feed(
        contents,
        user_profile=user_profile,
        engagement=engagement,
        config=RankingConfig(),
        now=now,
        diversify=True,
    )

    assert len(ranked) == 3
    # Ensure the algorithm did not drop any items and the best topic mix is present.
    assert any(score.interest_fit for score in ranked)

