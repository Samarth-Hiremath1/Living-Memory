"""The creepy-line filter. Every insight must pass through here before reaching staff."""

from pathlib import Path
import anthropic
from ..config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_PROMPT = (Path(__file__).parent.parent / "prompts" / "friend_filter.md").read_text()


def filter_insight(raw_insight: str) -> str:
    """Rewrite a raw AI insight into warm, friend-test-passing language."""
    response = _client.messages.create(
        model=settings.fast_model,
        max_tokens=256,
        system=_PROMPT,
        messages=[{"role": "user", "content": raw_insight}],
    )
    return response.content[0].text.strip()


def filter_insights(insights: list[str]) -> list[str]:
    """Batch filter a list of insights."""
    return [filter_insight(i) for i in insights]


def demo_filter_comparison(raw: str) -> dict[str, str]:
    """Return both raw and filtered for the live demo comparison beat."""
    return {
        "raw": raw,
        "filtered": filter_insight(raw),
    }
