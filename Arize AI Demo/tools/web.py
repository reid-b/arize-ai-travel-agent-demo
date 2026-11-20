"""Web search tool for general travel information (not fares).

Search engines rate-limit and block automated clients, so a single DuckDuckGo
call fails often enough to break a demo. This tool tries several search backends
in turn, then falls back to Wikivoyage (a free travel guide with a public API).
It returns JSON with a fixed schema, and returns failures as data
(status="error") with the reason from each attempt, so the agent can explain
what happened instead of guessing.
"""

import json
from typing import Literal

import requests
from langchain_core.tools import tool
from pydantic import BaseModel

MAX_RESULTS = 5
BACKENDS = ["auto", "duckduckgo", "bing", "brave", "mojeek"]  # tried in order
MAX_BACKEND_TRIES = 3
WIKIVOYAGE_API = "https://en.wikivoyage.org/w/api.php"
USER_AGENT = "SojournsTravelAgent/0.1 (demo; contact: local)"


class WebResult(BaseModel):
    title: str
    snippet: str
    url: str | None = None


class WebSearchResult(BaseModel):
    status: Literal["ok", "no_results", "error"]
    source: str | None = None        # which backend answered
    query: str
    results: list[WebResult] = []
    attempts: list[str] = []         # what was tried and why it failed
    error: str | None = None


def _search_ddgs(query: str, backend: str) -> list[WebResult]:
    from ddgs import DDGS

    rows = DDGS(timeout=10).text(query, max_results=MAX_RESULTS, backend=backend)
    return [
        WebResult(title=r.get("title", ""), snippet=r.get("body", "")[:400], url=r.get("href"))
        for r in rows or []
    ]


def _search_wikivoyage(query: str) -> list[WebResult]:
    resp = requests.get(
        WIKIVOYAGE_API,
        params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrlimit": 3, "prop": "extracts",
            "exintro": 1, "explaintext": 1, "exchars": 600,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    pages = (resp.json().get("query") or {}).get("pages") or {}
    ordered = sorted(pages.values(), key=lambda p: p.get("index", 99))
    return [
        WebResult(
            title=p["title"],
            snippet=(p.get("extract") or "").strip(),
            url="https://en.wikivoyage.org/wiki/" + p["title"].replace(" ", "_"),
        )
        for p in ordered
        if p.get("extract")
    ]


@tool
def web_search(query: str) -> str:
    """Search the web for general travel information.

    Use this for things like what to know before visiting a place, weather and
    seasons, customs, neighborhoods, visas, or what to see. Never use it for
    fares, flight availability or rental car prices.

    Args:
        query: A short search query, e.g. "Tokyo travel tips spring".

    Returns:
        A JSON object: {status: "ok"|"no_results"|"error", source, query,
        results: [{title, snippet, url}], attempts: [...], error}. If status is
        "error", tell the user the search failed and answer from general knowledge,
        saying so plainly.
    """
    query = query.strip()
    if not query:
        return WebSearchResult(status="error", query=query, error="query is empty").model_dump_json()

    attempts: list[str] = []
    for backend in BACKENDS[:MAX_BACKEND_TRIES]:
        try:
            results = _search_ddgs(query, backend)
        except Exception as e:  # rate limit, timeout, blocked, missing package
            attempts.append(f"{backend}: {type(e).__name__}: {str(e)[:120]}")
            print(f"[sojourns] web search via {backend} failed: {type(e).__name__}: {str(e)[:200]}",
                  flush=True)
            continue
        if results:
            return WebSearchResult(status="ok", source=f"ddgs:{backend}", query=query,
                                   results=results, attempts=attempts).model_dump_json()
        attempts.append(f"{backend}: no results")

    try:
        results = _search_wikivoyage(query)
        if results:
            return WebSearchResult(status="ok", source="wikivoyage", query=query,
                                   results=results, attempts=attempts).model_dump_json()
        attempts.append("wikivoyage: no results")
    except Exception as e:
        attempts.append(f"wikivoyage: {type(e).__name__}: {str(e)[:120]}")
        print(f"[sojourns] wikivoyage fallback failed: {type(e).__name__}: {str(e)[:200]}", flush=True)

    all_empty = all(a.endswith("no results") for a in attempts)
    return WebSearchResult(
        status="no_results" if all_empty else "error",
        query=query,
        attempts=attempts,
        error=None if all_empty else "Every search source failed: " + "; ".join(attempts),
    ).model_dump_json()


if __name__ == "__main__":
    # Quick manual test:  python -m tools.web
    print(json.dumps(json.loads(web_search.invoke({"query": "Tokyo travel tips spring"})), indent=2))
