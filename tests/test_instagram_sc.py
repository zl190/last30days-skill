"""Tests for instagram.py — ScrapeCreators Instagram search module."""

from lib import instagram


class TestTokenize:
    """Tests for _tokenize()."""

    def test_strips_stopwords(self):
        tokens = instagram._tokenize("how to use the AI tools")
        assert "how" not in tokens
        assert "the" not in tokens
        assert "to" not in tokens

    def test_expands_synonyms(self):
        tokens = instagram._tokenize("ai tools")
        assert "artificial" in tokens or "intelligence" in tokens

    def test_removes_single_char(self):
        tokens = instagram._tokenize("a b c python")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "python" in tokens

    def test_lowercases(self):
        tokens = instagram._tokenize("Python REACT")
        assert "python" in tokens
        assert "react" in tokens

    def test_strips_punctuation(self):
        tokens = instagram._tokenize("hello, world!")
        assert "hello" in tokens
        assert "world" in tokens


class TestComputeRelevance:
    """Tests for _compute_relevance()."""

    def test_exact_match_high(self):
        rel = instagram._compute_relevance("claude code", "Claude Code tricks and tips")
        assert rel >= 0.8

    def test_partial_match_lower(self):
        rel = instagram._compute_relevance("claude code tips", "Best AI tools for coding")
        assert rel < 0.5

    def test_hashtag_boost(self):
        base = instagram._compute_relevance("claude code", "random video about stuff")
        boosted = instagram._compute_relevance("claude code", "random video about stuff", ["claudecode", "ai"])
        assert boosted > base

    def test_floor_at_01(self):
        rel = instagram._compute_relevance("quantum physics", "cat dancing video")
        assert rel >= 0.1

    def test_empty_query_returns_default(self):
        rel = instagram._compute_relevance("", "Some video title")
        assert rel == 0.5


class TestInstagramDepthConfig:
    """Tests for DEPTH_CONFIG."""

    def test_all_depths_exist(self):
        for depth in ("quick", "default", "deep"):
            assert depth in instagram.DEPTH_CONFIG

    def test_required_keys(self):
        for depth, config in instagram.DEPTH_CONFIG.items():
            assert "results_per_page" in config
            assert "max_captions" in config

    def test_deep_has_more_results(self):
        assert instagram.DEPTH_CONFIG["deep"]["results_per_page"] > instagram.DEPTH_CONFIG["quick"]["results_per_page"]
