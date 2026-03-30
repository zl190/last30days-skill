"""Tests for store.py column whitelist validation."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import store


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    """Use a temporary database for every test."""
    store._db_override = tmp_path / "test.db"
    store.init_db(store._db_override)
    yield
    store._db_override = None


@pytest.fixture
def topic_and_run(tmp_db):
    """Create a topic and run for update tests."""
    topic = store.add_topic("test-topic")
    run_id = store.record_run(topic["id"], status="running")
    return topic, run_id


class TestUpdateRunWhitelist:
    def test_valid_columns(self, topic_and_run):
        _, run_id = topic_and_run
        store.update_run(run_id, status="completed", duration_seconds=1.5)

    def test_rejects_invalid_column(self, topic_and_run):
        _, run_id = topic_and_run
        with pytest.raises(ValueError, match="Invalid column"):
            store.update_run(run_id, **{"status = 1; DROP TABLE findings; --": "x"})

    def test_rejects_unknown_column(self, topic_and_run):
        _, run_id = topic_and_run
        with pytest.raises(ValueError, match="Invalid column"):
            store.update_run(run_id, not_a_real_column="bad")

    def test_rejects_empty_kwargs(self, topic_and_run):
        _, run_id = topic_and_run
        with pytest.raises(ValueError, match="No columns specified"):
            store.update_run(run_id)


class TestUpdateFindingWhitelist:
    def test_valid_columns(self, topic_and_run):
        topic, run_id = topic_and_run
        store.store_findings(run_id, topic["id"], [
            {"source_url": "https://example.com/1", "source": "test", "summary": "s"}
        ])
        findings = store.get_new_findings(topic["id"])
        store.update_finding(findings[0]["id"], dismissed=1)

    def test_rejects_invalid_column(self, topic_and_run):
        with pytest.raises(ValueError, match="Invalid column"):
            store.update_finding(1, **{"id = 1; --": "x"})

    def test_rejects_empty_kwargs(self, topic_and_run):
        with pytest.raises(ValueError, match="No columns specified"):
            store.update_finding(1)

    def test_dismiss_uses_whitelist(self, topic_and_run):
        topic, run_id = topic_and_run
        store.store_findings(run_id, topic["id"], [
            {"source_url": "https://example.com/2", "source": "test"}
        ])
        findings = store.get_new_findings(topic["id"])
        store.dismiss_finding(findings[0]["id"])
