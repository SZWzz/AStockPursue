"""Integration tests for src.db.sentiment_store — news & sentiment persistence.

Mocks psycopg2 connections via ``mock_conn`` fixture.  Verifies SQL, params,
deserialisation and error paths.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

import src.db.sentiment_store as mod
from tests.db.conftest import mock_get_connection_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_get_connection(monkeypatch, conn):
    monkeypatch.setattr(mod, "get_connection", mock_get_connection_factory(conn))


def _mock_execute_values(monkeypatch):
    """Mock psycopg2.extras.execute_values so save_news_items works without PG."""
    mock_ev = MagicMock()
    monkeypatch.setattr(sys.modules["psycopg2.extras"], "execute_values", mock_ev)
    return mock_ev


# ---------------------------------------------------------------------------
# save_news_items
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSaveNewsItems:
    def test_saves_list_of_articles_returns_count(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)
        mock_ev = _mock_execute_values(monkeypatch)

        cursor.rowcount = 3

        articles = [
            {"title": "News 1", "url": "http://a.com", "source": "web_search",
             "summary": "Summary 1", "published_at": "2024-06-01", "sentiment_score": 0.8,
             "sentiment_label": "positive", "matched_symbols": ["000001"], "topics": ["tech"]},
            {"title": "News 2", "url": "http://b.com", "source": "web_search",
             "summary": "Summary 2", "published_at": "2024-06-01", "sentiment_score": 0.3,
             "sentiment_label": "negative", "matched_symbols": ["000002"], "topics": ["finance"]},
            {"title": "News 3", "url": "http://c.com", "source": "official",
             "summary": "Summary 3", "published_at": "2024-06-01", "sentiment_score": 0.5,
             "sentiment_label": "neutral", "matched_symbols": [], "topics": []},
        ]

        count = mod.save_news_items(articles)

        assert count == 3
        assert mock_ev.called

    def test_empty_list_returns_zero(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        result = mod.save_news_items([])

        assert result == 0
        cursor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# get_recent_news
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetRecentNews:
    def test_returns_list_of_dicts_filtered_by_symbol(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = [
            ("Title", "http://x.com", "web", "Summary", "2024-06-01",
             0.7, "positive", ["000001"], ["tech"]),
        ]

        results = mod.get_recent_news(symbol="000001")

        assert isinstance(results, list)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Title"
        assert r["sentiment_score"] == 0.7
        assert r["sentiment_label"] == "positive"

        sql = cursor.execute.call_args[0][0]
        assert "ANY(matched_symbols)" in sql

    def test_respects_max_age_minutes(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = []

        mod.get_recent_news(symbol="000001", max_age_minutes=60)

        params = cursor.execute.call_args[0][1]
        assert params[0] == "60 minutes"


# ---------------------------------------------------------------------------
# save_stock_sentiment / get_stock_sentiment
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestStockSentiment:
    def test_save_stock_sentiment_upserts_returns_true(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        result = mod.save_stock_sentiment(
            symbol="000001", date="2024-06-01",
            sentiment_mean=0.75, sentiment_std=0.15,
            news_count=10, trending_score=2.5,
        )

        assert result is True
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT INTO vt_stock_sentiment" in sql
        assert "ON CONFLICT" in sql

    def test_get_stock_sentiment_returns_dict_with_expected_keys(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = ("000001", "2024-06-01", 0.75, 0.15, 10, 2.5)

        result = mod.get_stock_sentiment("000001")

        assert result is not None
        assert result["symbol"] == "000001"
        assert result["sentiment_mean"] == 0.75
        assert result["sentiment_std"] == 0.15
        assert result["news_count"] == 10
        assert result["trending_score"] == 2.5
        assert "date" in result

    def test_get_stock_sentiment_returns_none_for_unknown_symbol(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = None

        result = mod.get_stock_sentiment("UNKNOWN")
        assert result is None


# ---------------------------------------------------------------------------
# get_cached_news_by_source
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCachedNewsBySource:
    def test_filters_by_source(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchall.return_value = [
            ("Title", "http://x.com", "official", "Summary", "2024-06-01", 0.7, "positive"),
        ]

        results = mod.get_cached_news_by_source(source="official", symbol="000001")

        assert len(results) == 1
        assert results[0]["source"] == "official"

        params = cursor.execute.call_args[0][1]
        assert params[1] == "official"
        assert params[2] == "official"


# ---------------------------------------------------------------------------
# is_source_fresh
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIsSourceFresh:
    def test_returns_true_when_source_updated_recently(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = (1,)

        result = mod.is_source_fresh("official")

        assert result is True
        sql = cursor.execute.call_args[0][0]
        assert "published_at > now()" in sql

    def test_returns_false_when_not_fresh(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        cursor.fetchone.return_value = None

        result = mod.is_source_fresh("stale_source")
        assert result is False


# ---------------------------------------------------------------------------
# get_source_freshness
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetSourceFreshness:
    def test_returns_dict_with_source_keys(self, monkeypatch, mock_conn):
        conn, cursor = mock_conn
        _patch_get_connection(monkeypatch, conn)

        # Mock SOURCE_META and SOURCE_TTL imports
        sys.modules.setdefault("backtest", MagicMock())
        sys.modules.setdefault("backtest.loaders", MagicMock())
        sys.modules.setdefault("backtest.loaders.news_sources", MagicMock())
        mock_base = MagicMock()
        mock_base.SOURCE_META = {
            "src_a": {"label": "Source A", "category": "news"},
            "src_b": {"label": "Source B", "category": "market"},
        }
        mock_base.SOURCE_TTL = {"src_a": 300, "src_b": 600}
        sys.modules["backtest.loaders.news_sources.base"] = mock_base

        # fetchone returns: (published_at,) for last_update, (count,) for count_24h
        # Use None (not a tuple) for never-fetched sources
        cursor.fetchone.side_effect = [
            ("2024-06-01T12:00:00",),   # last_update for src_a
            (5,),                        # count_24h for src_a
            None,                        # last_update for src_b (never fetched)
            (0,),                        # count_24h for src_b
        ]

        result = mod.get_source_freshness()

        assert isinstance(result, dict)
        assert "src_a" in result
        assert "src_b" in result
        assert result["src_a"]["label"] == "Source A"
        assert result["src_a"]["count_24h"] == 5
        assert result["src_b"]["fresh"] is None
        assert result["src_b"]["category"] == "market"
