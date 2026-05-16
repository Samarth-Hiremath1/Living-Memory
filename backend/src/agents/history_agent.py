"""History agent: extracts warm, actionable patterns from past stay observations."""

from __future__ import annotations
import json
from pathlib import Path
import anthropic

from ..config import settings
from ..graph.schema import Guest, Observation
from ..graph.store import graph

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
_PROMPT = (Path(__file__).parent.parent / "prompts" / "history_agent.md").read_text()


def run_history_agent(guest: Guest) -> dict:
    """Extract patterns from all past observations for this guest."""
    observations = graph.get_observations_for_guest(guest.id)

    if not observations:
        return {
            "patterns": [],
            "occasions": [],
            "interests": [],
            "sensitivities": [],
            "cross_property_signals": [],
            "standout_moment": None,
        }

    obs_texts = [
        f"[{obs.property_id}, {obs.timestamp.strftime('%Y-%m')}] {obs.raw_text}"
        for obs in observations
    ]
    obs_block = "\n".join(obs_texts)

    response = _client.messages.create(
        model=settings.orchestrator_model,
        max_tokens=1024,
        system=_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Guest: {guest.name}\n\nObservations:\n{obs_block}",
        }],
    )

    try:
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return {
            "patterns": [],
            "occasions": [],
            "interests": [],
            "sensitivities": [],
            "cross_property_signals": [],
            "standout_moment": None,
        }
