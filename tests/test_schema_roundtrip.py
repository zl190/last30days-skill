"""Tests for schema.py — data class serialization roundtrips."""

from lib import schema


class TestEngagement:
    """Tests for Engagement.to_dict()."""

    def test_sparse_fields(self):
        eng = schema.Engagement(score=100, num_comments=50)
        d = eng.to_dict()
        assert d == {"score": 100, "num_comments": 50}
        assert "likes" not in d

    def test_all_none_returns_none(self):
        eng = schema.Engagement()
        assert eng.to_dict() is None

    def test_all_fields(self):
        eng = schema.Engagement(
            score=1, num_comments=2, upvote_ratio=0.9,
            likes=3, reposts=4, replies=5, quotes=6,
            views=7, shares=8, volume=9.0, liquidity=10.0,
        )
        d = eng.to_dict()
        assert len(d) == 11


class TestComment:
    def test_basic(self):
        c = schema.Comment(score=50, date="2026-03-01", author="user", excerpt="text", url="http://x")
        d = c.to_dict()
        assert d["score"] == 50
        assert d["author"] == "user"
        assert len(d) == 5


class TestRedditItem:
    def test_roundtrip(self):
        item = schema.RedditItem(
            id="R1", title="Test", url="http://reddit.com/r/test",
            subreddit="test", date="2026-03-01",
            engagement=schema.Engagement(score=100),
        )
        d = item.to_dict()
        assert d["id"] == "R1"
        assert d["subreddit"] == "test"
        assert d["engagement"] == {"score": 100}
        assert "cross_refs" not in d

    def test_cross_refs_included_when_present(self):
        item = schema.RedditItem(
            id="R1", title="T", url="u", subreddit="s",
            cross_refs=["X1", "HN2"],
        )
        d = item.to_dict()
        assert d["cross_refs"] == ["X1", "HN2"]


class TestXItem:
    def test_roundtrip(self):
        item = schema.XItem(
            id="X1", text="tweet", url="http://x.com/1",
            author_handle="user", date="2026-03-01",
        )
        d = item.to_dict()
        assert d["id"] == "X1"
        assert d["author_handle"] == "user"
        assert "cross_refs" not in d


class TestYouTubeItem:
    def test_roundtrip(self):
        item = schema.YouTubeItem(
            id="YT1", title="Video", url="http://youtube.com/1",
            channel_name="chan",
        )
        d = item.to_dict()
        assert d["channel_name"] == "chan"
        assert d["date_confidence"] == "high"


class TestTikTokItem:
    def test_roundtrip(self):
        item = schema.TikTokItem(
            id="TK1", text="caption", url="http://tiktok.com/1",
            author_name="creator", hashtags=["ai", "code"],
        )
        d = item.to_dict()
        assert d["hashtags"] == ["ai", "code"]
        assert d["author_name"] == "creator"


class TestInstagramItem:
    def test_roundtrip(self):
        item = schema.InstagramItem(
            id="IG1", text="caption", url="http://instagram.com/reel/1",
            author_name="creator",
        )
        d = item.to_dict()
        assert d["id"] == "IG1"


class TestWebSearchItem:
    def test_roundtrip(self):
        item = schema.WebSearchItem(
            id="W1", title="Article", url="http://example.com",
            source_domain="example.com", snippet="text",
        )
        d = item.to_dict()
        assert d["source_domain"] == "example.com"


class TestHackerNewsItem:
    def test_roundtrip(self):
        item = schema.HackerNewsItem(
            id="HN1", title="Show HN", url="http://example.com",
            hn_url="http://news.ycombinator.com/item?id=1", author="pg",
        )
        d = item.to_dict()
        assert d["hn_url"].startswith("http://news.ycombinator.com")


class TestPolymarketItem:
    def test_roundtrip(self):
        item = schema.PolymarketItem(
            id="PM1", title="Election", question="Who wins?",
            url="http://polymarket.com/1",
        )
        d = item.to_dict()
        assert d["question"] == "Who wins?"
