from __future__ import annotations
from typing import List, Dict

from ddgs import DDGS


def web_search(query: str, num_results: int = 6) -> List[Dict]:
    """
    Returns [{"title":..., "link":..., "snippet":...}, ...] using ddgs directly.
    This avoids the LangChain wrapper's occasional blob/JSON parsing issues.
    """
    results: List[Dict] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=num_results):
            results.append(
                {
                    "title": (r.get("title") or "").strip(),
                    "link": (r.get("href") or "").strip(),
                    "snippet": (r.get("body") or "").strip(),
                }
            )

    # Filter empties
    results = [r for r in results if r["title"] or r["link"] or r["snippet"]]
    return results
