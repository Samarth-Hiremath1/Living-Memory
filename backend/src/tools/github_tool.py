"""
GitHub repository and user search via the public REST API.

No API key required for read-only search (60 unauthenticated requests/hour).
Set GITHUB_TOKEN in .env for 5,000 requests/hour and access to private data.
"""

from __future__ import annotations
import httpx
from ..config import settings

_BASE = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "LivingMemory-Agent/1.0",
}


def _auth_headers() -> dict:
    token = getattr(settings, "github_token", None)
    if token:
        return {**_HEADERS, "Authorization": f"Bearer {token}"}
    return _HEADERS


def search_github(query: str, search_type: str = "repositories") -> str:
    """
    Search GitHub for repositories or users.

    Args:
        query:       Full-text search query (e.g. "anthropic claude python sdk")
        search_type: "repositories" (default) or "users"

    Returns a plain-English summary of the top results.
    """
    if not query or not query.strip():
        return "Error: search query cannot be empty."

    endpoint_map = {
        "repositories": f"{_BASE}/search/repositories",
        "users": f"{_BASE}/search/users",
    }
    url = endpoint_map.get(search_type, endpoint_map["repositories"])

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                url,
                headers=_auth_headers(),
                params={"q": query.strip(), "per_page": 5, "sort": "stars"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return f"Error: GitHub request timed out for query '{query}'."
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 403:
            return "Error: GitHub rate limit exceeded. Try again in a minute."
        return f"Error: GitHub returned {exc.response.status_code}."
    except Exception as exc:
        return f"Error: GitHub search failed — {exc}"

    items = data.get("items", [])
    total = data.get("total_count", 0)

    if not items:
        return f"No GitHub {search_type} found for query: '{query}'"

    if search_type == "repositories":
        lines = []
        for repo in items:
            stars = repo.get("stargazers_count", 0)
            desc = (repo.get("description") or "No description").strip()
            # Truncate long descriptions
            if len(desc) > 80:
                desc = desc[:77] + "..."
            lang = repo.get("language") or ""
            lang_str = f" [{lang}]" if lang else ""
            lines.append(f"• {repo['full_name']}{lang_str} — {stars:,}★ — {desc}")
        header = f"Top GitHub repositories for '{query}' ({total:,} total results):"
        return header + "\n" + "\n".join(lines)

    else:  # users
        lines = [
            f"• {u['login']} — {u['html_url']} (score: {u.get('score', '?'):.0f})"
            for u in items
        ]
        header = f"GitHub users matching '{query}' ({total:,} total results):"
        return header + "\n" + "\n".join(lines)
