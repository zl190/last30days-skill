"""Tests for reddit_enrich.py — comment enrichment and parsing."""

from lib import reddit_enrich


class TestExtractRedditPath:
    """Tests for extract_reddit_path()."""

    def test_valid_url(self):
        url = "https://www.reddit.com/r/ClaudeAI/comments/abc123/post_title/"
        path = reddit_enrich.extract_reddit_path(url)
        assert path == "/r/ClaudeAI/comments/abc123/post_title/"

    def test_non_reddit_url(self):
        assert reddit_enrich.extract_reddit_path("https://example.com/foo") is None

    def test_empty_string(self):
        assert reddit_enrich.extract_reddit_path("") is None

    def test_old_reddit(self):
        url = "https://old.reddit.com/r/test/comments/xyz/"
        assert reddit_enrich.extract_reddit_path(url) is not None


class TestParseThreadData:
    """Tests for parse_thread_data() using fixture."""

    def test_parses_submission(self, load_fixture):
        data = load_fixture("reddit_thread_sample.json")
        result = reddit_enrich.parse_thread_data(data)
        assert result["submission"] is not None
        assert result["submission"]["score"] == 847
        assert result["submission"]["num_comments"] == 156

    def test_parses_comments(self, load_fixture):
        data = load_fixture("reddit_thread_sample.json")
        result = reddit_enrich.parse_thread_data(data)
        assert len(result["comments"]) == 8
        assert result["comments"][0]["author"] == "skill_expert"

    def test_empty_input(self):
        result = reddit_enrich.parse_thread_data([])
        assert result["submission"] is None
        assert result["comments"] == []

    def test_malformed_input(self):
        result = reddit_enrich.parse_thread_data("not a list")
        assert result["submission"] is None

    def test_none_input(self):
        result = reddit_enrich.parse_thread_data(None)
        assert result["submission"] is None


class TestGetTopComments:
    """Tests for get_top_comments()."""

    def test_sorted_by_score(self):
        comments = [
            {"score": 10, "author": "a"},
            {"score": 100, "author": "b"},
            {"score": 50, "author": "c"},
        ]
        top = reddit_enrich.get_top_comments(comments, limit=3)
        assert top[0]["score"] == 100
        assert top[1]["score"] == 50

    def test_filters_deleted(self):
        comments = [
            {"score": 100, "author": "[deleted]"},
            {"score": 50, "author": "[removed]"},
            {"score": 10, "author": "real_user"},
        ]
        top = reddit_enrich.get_top_comments(comments)
        assert len(top) == 1
        assert top[0]["author"] == "real_user"

    def test_respects_limit(self):
        comments = [{"score": i, "author": f"u{i}"} for i in range(20)]
        top = reddit_enrich.get_top_comments(comments, limit=5)
        assert len(top) == 5

    def test_empty_list(self):
        assert reddit_enrich.get_top_comments([]) == []


class TestExtractCommentInsights:
    """Tests for extract_comment_insights()."""

    def test_filters_short_comments(self):
        comments = [
            {"body": "yes"},
            {"body": "A" * 50 + " this is a substantive comment about the topic."},
        ]
        insights = reddit_enrich.extract_comment_insights(comments)
        assert len(insights) == 1

    def test_filters_low_value_patterns(self):
        comments = [
            {"body": "This."},
            {"body": "lol that's hilarious"},
            {"body": "A" * 50 + " Here's a real insight about how to approach this problem."},
        ]
        insights = reddit_enrich.extract_comment_insights(comments)
        assert len(insights) == 1

    def test_respects_limit(self):
        comments = [{"body": f"Comment number {i} " + "x" * 50} for i in range(20)]
        insights = reddit_enrich.extract_comment_insights(comments, limit=3)
        assert len(insights) <= 3
