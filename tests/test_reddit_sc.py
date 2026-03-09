"""Tests for reddit.py — ScrapeCreators Reddit search module."""

from lib import reddit


class TestExtractCoreSubject:
    """Tests for _extract_core_subject()."""

    def test_strips_what_are_prefix(self):
        assert reddit._extract_core_subject("what are the best AI tools") == "ai tools"

    def test_strips_how_to_prefix(self):
        assert reddit._extract_core_subject("how to use cursor IDE") == "cursor ide"

    def test_strips_noise_words(self):
        result = reddit._extract_core_subject("latest trending updates")
        assert result == "latest trending updates"

    def test_preserves_product_name(self):
        assert reddit._extract_core_subject("cursor IDE") == "cursor ide"

    def test_strips_trailing_punctuation(self):
        result = reddit._extract_core_subject("what is Claude?")
        assert not result.endswith("?")

    def test_empty_string(self):
        result = reddit._extract_core_subject("")
        assert result == ""

    def test_strips_what_do_people_think(self):
        result = reddit._extract_core_subject("what do people think about React Server Components")
        assert result == "react server components"


class TestExpandRedditQueries:
    """Tests for expand_reddit_queries()."""

    def test_quick_returns_one_query(self):
        queries = reddit.expand_reddit_queries("cursor IDE", "quick")
        assert len(queries) >= 1

    def test_default_includes_review_variant(self):
        queries = reddit.expand_reddit_queries("cursor IDE", "default")
        assert any("worth it" in q or "review" in q for q in queries)

    def test_deep_includes_issues_variant(self):
        queries = reddit.expand_reddit_queries("cursor IDE", "deep")
        assert any("issues" in q or "problems" in q for q in queries)

    def test_deep_has_more_queries_than_quick(self):
        quick = reddit.expand_reddit_queries("cursor IDE", "quick")
        deep = reddit.expand_reddit_queries("cursor IDE", "deep")
        assert len(deep) > len(quick)


class TestDiscoverSubreddits:
    """Tests for discover_subreddits()."""

    def test_ranks_by_frequency(self):
        results = [
            {"subreddit": "programming", "score": 10},
            {"subreddit": "programming", "score": 20},
            {"subreddit": "python", "score": 5},
        ]
        subs = reddit.discover_subreddits(results, max_subs=5)
        assert subs[0] == "programming"

    def test_utility_sub_penalty(self):
        results = [
            {"subreddit": "tipofmytongue", "score": 100},
            {"subreddit": "tipofmytongue", "score": 100},
            {"subreddit": "python", "score": 10},
        ]
        subs = reddit.discover_subreddits(results, topic="python", max_subs=5)
        assert subs[0] == "python"

    def test_topic_name_bonus(self):
        results = [
            {"subreddit": "reactjs", "score": 10},
            {"subreddit": "webdev", "score": 10},
        ]
        subs = reddit.discover_subreddits(results, topic="react hooks", max_subs=5)
        assert subs[0] == "reactjs"

    def test_engagement_bonus(self):
        results = [
            {"subreddit": "AIsub", "ups": 500},
            {"subreddit": "OtherSub", "ups": 5},
        ]
        subs = reddit.discover_subreddits(results, max_subs=5)
        assert subs[0] == "AIsub"

    def test_max_subs_limit(self):
        results = [{"subreddit": f"sub{i}"} for i in range(20)]
        subs = reddit.discover_subreddits(results, max_subs=3)
        assert len(subs) <= 3

    def test_empty_results(self):
        assert reddit.discover_subreddits([]) == []

    def test_missing_subreddit_field(self):
        results = [{"title": "no sub field"}]
        assert reddit.discover_subreddits(results) == []


class TestParseDate:
    """Tests for _parse_date()."""

    def test_valid_timestamp(self):
        assert reddit._parse_date(1705363200) == "2024-01-16"

    def test_string_timestamp(self):
        assert reddit._parse_date("1705363200") == "2024-01-16"

    def test_none_returns_none(self):
        assert reddit._parse_date(None) is None

    def test_zero_returns_none(self):
        assert reddit._parse_date(0) is None


class TestDepthConfig:
    """Tests for DEPTH_CONFIG structure."""

    def test_all_depths_exist(self):
        for depth in ("quick", "default", "deep"):
            assert depth in reddit.DEPTH_CONFIG

    def test_required_keys(self):
        required = {"global_searches", "subreddit_searches", "comment_enrichments", "timeframe"}
        for depth, config in reddit.DEPTH_CONFIG.items():
            assert required.issubset(config.keys()), f"Missing keys in {depth}: {required - config.keys()}"

    def test_deep_has_more_searches(self):
        assert reddit.DEPTH_CONFIG["deep"]["global_searches"] > reddit.DEPTH_CONFIG["quick"]["global_searches"]
