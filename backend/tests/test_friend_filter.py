"""Tests for the friend filter — verifies the creepy-line rewrite works."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_claude():
    with patch("src.agents.friend_filter._client") as mock:
        mock.messages.create.return_value = MagicMock(
            content=[MagicMock(text="She tends to reach for a rosé — especially in the warmer months.")]
        )
        yield mock


def test_filter_removes_percentages(mock_claude):
    from src.agents.friend_filter import filter_insight
    raw = "Guest shows 73% preference for rosé based on 5 past stays."
    result = filter_insight(raw)
    assert "73%" not in result
    assert len(result) > 0


def test_filter_passes_warm_insight_unchanged(mock_claude):
    mock_claude.messages.create.return_value = MagicMock(
        content=[MagicMock(text="She lights up around anything outdoors.")]
    )
    from src.agents.friend_filter import filter_insight
    result = filter_insight("She lights up around anything outdoors.")
    assert "outdoors" in result


def test_demo_comparison_returns_both():
    from src.agents.friend_filter import demo_filter_comparison
    with patch("src.agents.friend_filter._client") as mock:
        mock.messages.create.return_value = MagicMock(
            content=[MagicMock(text="She enjoys rosé in summer.")]
        )
        result = demo_filter_comparison("Based on 73% preference data...")
        assert "raw" in result
        assert "filtered" in result
