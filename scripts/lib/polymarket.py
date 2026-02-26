"""Polymarket prediction market search via Gamma API (free, no auth required).

Uses gamma-api.polymarket.com for event/market discovery.
No API key needed - public read-only API with generous rate limits (350 req/10s).
"""

import json
import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

from . import http

GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"

DEPTH_CONFIG = {
    "quick": 5,
    "default": 10,
    "deep": 20,
}


def _log(msg: str):
    """Log to stderr (only in TTY mode to avoid cluttering Claude Code output)."""
    if sys.stderr.isatty():
        sys.stderr.write(f"[PM] {msg}\n")
        sys.stderr.flush()


def _extract_core_subject(topic: str) -> str:
    """Extract core subject from topic string.

    Strips common prefixes like 'last 7 days', 'what are people saying about', etc.
    """
    topic = topic.strip()
    # Remove common leading phrases
    prefixes = [
        r"^last \d+ days?\s+",
        r"^what(?:'s| is| are) (?:people saying about|happening with|going on with)\s+",
        r"^how (?:is|are)\s+",
        r"^tell me about\s+",
        r"^research\s+",
    ]
    for pattern in prefixes:
        topic = re.sub(pattern, "", topic, flags=re.IGNORECASE)
    return topic.strip()


def _expand_queries(topic: str) -> List[str]:
    """Generate 2-4 search queries to cast a wider net.

    Strategy:
    - Always include the core subject
    - Split multi-word topics into component searches
    - Include the full topic if different from core
    - Cap at 4 queries, dedupe
    """
    core = _extract_core_subject(topic)
    queries = [core]

    # Split multi-word topics into component searches
    words = core.split()
    if len(words) >= 2:
        # Try the first significant word alone (e.g., "Arizona" from "Arizona Basketball")
        queries.append(words[0])

    # Add the full topic if different from core
    if topic.lower().strip() != core.lower():
        queries.append(topic.strip())

    # Dedupe while preserving order, cap at 4
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q.strip())
    return unique[:4]


def _search_single_query(query: str, limit: int) -> Dict[str, Any]:
    """Run a single search query against Gamma API."""
    params = {
        "q": query,
        "limit": str(limit),
    }
    url = f"{GAMMA_SEARCH_URL}?{urlencode(params)}"

    try:
        response = http.request("GET", url, timeout=15, retries=2)
        return response
    except http.HTTPError as e:
        _log(f"Search failed for '{query}': {e}")
        return {"events": [], "error": str(e)}
    except Exception as e:
        _log(f"Search failed for '{query}': {e}")
        return {"events": [], "error": str(e)}


def search_polymarket(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> Dict[str, Any]:
    """Search Polymarket via Gamma API with smart query expansion.

    Runs 2-4 expanded queries in parallel, merges and dedupes by event ID.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD) - used for activity filtering
        to_date: End date (YYYY-MM-DD)
        depth: 'quick', 'default', or 'deep'

    Returns:
        Dict with 'events' list and optional 'error'.
    """
    limit_per_query = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])
    queries = _expand_queries(topic)

    _log(f"Searching for '{topic}' with queries: {queries} (limit={limit_per_query})")

    # Run all queries in parallel
    all_events = {}  # event_id -> (event_data, query_index)
    errors = []

    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as executor:
        futures = {
            executor.submit(_search_single_query, q, limit_per_query): i
            for i, q in enumerate(queries)
        }

        for future in as_completed(futures):
            query_idx = futures[future]
            try:
                response = future.result(timeout=15)
                if response.get("error"):
                    errors.append(response["error"])

                events = response.get("events", [])
                for event in events:
                    event_id = event.get("id", "")
                    if not event_id:
                        continue
                    # Keep the first occurrence (from highest-priority query)
                    if event_id not in all_events:
                        all_events[event_id] = (event, query_idx)
                    elif query_idx < all_events[event_id][1]:
                        # Replace with higher-priority query result
                        all_events[event_id] = (event, query_idx)
            except Exception as e:
                errors.append(str(e))

    # Sort by query priority, then by position
    merged_events = [ev for ev, _ in sorted(all_events.values(), key=lambda x: x[1])]
    _log(f"Found {len(merged_events)} unique events across {len(queries)} queries")

    result = {"events": merged_events}
    if errors and not merged_events:
        result["error"] = "; ".join(errors[:2])
    return result


def _format_price_movement(market: Dict[str, Any]) -> Optional[str]:
    """Pick the most significant price change and format it.

    Returns string like 'down 11.7% this month' or None if no significant change.
    """
    changes = [
        (abs(market.get("oneDayPriceChange") or 0), market.get("oneDayPriceChange"), "today"),
        (abs(market.get("oneWeekPriceChange") or 0), market.get("oneWeekPriceChange"), "this week"),
        (abs(market.get("oneMonthPriceChange") or 0), market.get("oneMonthPriceChange"), "this month"),
    ]

    # Pick the largest absolute change
    changes.sort(key=lambda x: x[0], reverse=True)
    abs_change, raw_change, period = changes[0]

    # Skip if change is less than 1% (noise)
    if abs_change < 0.01:
        return None

    direction = "up" if raw_change > 0 else "down"
    pct = abs_change * 100
    return f"{direction} {pct:.1f}% {period}"


def _parse_outcome_prices(market: Dict[str, Any]) -> List[tuple]:
    """Parse outcomePrices JSON string into list of (outcome_name, price) tuples."""
    outcomes_raw = market.get("outcomes") or []
    prices_raw = market.get("outcomePrices")

    if not prices_raw:
        return []

    # Both outcomes and outcomePrices can be JSON-encoded strings
    try:
        if isinstance(outcomes_raw, str):
            outcomes = json.loads(outcomes_raw)
        else:
            outcomes = outcomes_raw
    except (json.JSONDecodeError, TypeError):
        outcomes = []

    try:
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
    except (json.JSONDecodeError, TypeError):
        return []

    result = []
    for i, price in enumerate(prices):
        try:
            p = float(price)
        except (ValueError, TypeError):
            continue
        name = outcomes[i] if i < len(outcomes) else f"Outcome {i+1}"
        result.append((name, p))

    return result


def parse_polymarket_response(response: Dict[str, Any], topic: str = "") -> List[Dict[str, Any]]:
    """Parse Gamma API response into normalized item dicts.

    Each event becomes one item showing its title and top markets.

    Args:
        response: Raw Gamma API response
        topic: Original search topic (for relevance scoring)

    Returns:
        List of item dicts ready for normalization.
    """
    events = response.get("events", [])
    items = []

    for i, event in enumerate(events):
        event_id = event.get("id", "")
        title = event.get("title", "")
        slug = event.get("slug", "")

        # Filter: skip closed/resolved events
        if event.get("closed", False):
            continue
        if not event.get("active", True):
            continue

        # Get markets for this event
        markets = event.get("markets", [])
        if not markets:
            continue

        # Filter to active, open markets with liquidity (excludes resolved markets)
        active_markets = []
        for m in markets:
            if m.get("closed", False):
                continue
            if not m.get("active", True):
                continue
            # Must have liquidity (resolved markets have 0 or None)
            try:
                liq = float(m.get("liquidity", 0) or 0)
            except (ValueError, TypeError):
                liq = 0
            if liq > 0:
                active_markets.append(m)

        if not active_markets:
            continue

        # Sort markets by volume (most liquid first)
        def market_volume(m):
            try:
                return float(m.get("volume", 0) or 0)
            except (ValueError, TypeError):
                return 0
        active_markets.sort(key=market_volume, reverse=True)

        # Take top market for the event
        top_market = active_markets[0]

        # Parse outcome prices from top market
        outcome_prices = _parse_outcome_prices(top_market)

        # Format price movement
        price_movement = _format_price_movement(top_market)

        # Volume and liquidity
        try:
            volume24hr = float(top_market.get("volume24hr", 0) or 0)
        except (ValueError, TypeError):
            volume24hr = 0.0
        try:
            liquidity = float(top_market.get("liquidity", 0) or 0)
        except (ValueError, TypeError):
            liquidity = 0.0

        # Event URL
        url = f"https://polymarket.com/event/{slug}" if slug else f"https://polymarket.com/event/{event_id}"

        # Date: use updatedAt from event
        updated_at = event.get("updatedAt", "")
        date_str = None
        if updated_at:
            # Parse ISO format: "2026-02-20T15:30:00.000Z"
            try:
                date_str = updated_at[:10]  # YYYY-MM-DD
            except (IndexError, TypeError):
                pass

        # End date for the market
        end_date = top_market.get("endDate")
        if end_date:
            try:
                end_date = end_date[:10]
            except (IndexError, TypeError):
                end_date = None

        # Relevance: position-based decay
        rank_score = max(0.3, 1.0 - (i * 0.03))  # 1.0 -> 0.3 over ~23 items
        engagement_boost = min(0.15, math.log1p(volume24hr) / 60)
        relevance = min(1.0, rank_score * 0.75 + engagement_boost + 0.1)

        # Top 3 outcomes for multi-outcome markets
        top_outcomes = outcome_prices[:3]
        remaining = len(outcome_prices) - 3
        if remaining < 0:
            remaining = 0

        items.append({
            "event_id": event_id,
            "title": title,
            "question": top_market.get("question", title),
            "url": url,
            "outcome_prices": top_outcomes,
            "outcomes_remaining": remaining,
            "price_movement": price_movement,
            "volume24hr": volume24hr,
            "liquidity": liquidity,
            "date": date_str,
            "end_date": end_date,
            "relevance": round(relevance, 2),
            "why_relevant": f"Prediction market: {title[:60]}",
        })

    return items
