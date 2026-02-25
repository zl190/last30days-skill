"""Near-duplicate detection for last30days skill."""

import re
from typing import List, Set, Tuple, Union

from . import schema


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    - Lowercase
    - Remove punctuation
    - Collapse whitespace
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_ngrams(text: str, n: int = 3) -> Set[str]:
    """Get character n-grams from text."""
    text = normalize_text(text)
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


AnyItem = Union[schema.RedditItem, schema.XItem, schema.YouTubeItem,
                schema.HackerNewsItem, schema.WebSearchItem]


def get_item_text(item: AnyItem) -> str:
    """Get comparable text from an item."""
    if isinstance(item, schema.RedditItem):
        return item.title
    elif isinstance(item, schema.HackerNewsItem):
        return item.title
    elif isinstance(item, schema.YouTubeItem):
        return f"{item.title} {item.channel_name}"
    elif isinstance(item, schema.WebSearchItem):
        return item.title
    else:
        return item.text


def _get_cross_source_text(item: AnyItem) -> str:
    """Get text for cross-source comparison.

    Same as get_item_text() but truncates X posts to 100 chars
    to level the playing field against short Reddit/HN titles.
    """
    if isinstance(item, schema.XItem):
        return item.text[:100]
    return get_item_text(item)


def find_duplicates(
    items: List[Union[schema.RedditItem, schema.XItem]],
    threshold: float = 0.7,
) -> List[Tuple[int, int]]:
    """Find near-duplicate pairs in items.

    Args:
        items: List of items to check
        threshold: Similarity threshold (0-1)

    Returns:
        List of (i, j) index pairs where i < j and items are similar
    """
    duplicates = []

    # Pre-compute n-grams
    ngrams = [get_ngrams(get_item_text(item)) for item in items]

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            similarity = jaccard_similarity(ngrams[i], ngrams[j])
            if similarity >= threshold:
                duplicates.append((i, j))

    return duplicates


def dedupe_items(
    items: List[Union[schema.RedditItem, schema.XItem]],
    threshold: float = 0.7,
) -> List[Union[schema.RedditItem, schema.XItem]]:
    """Remove near-duplicates, keeping highest-scored item.

    Args:
        items: List of items (should be pre-sorted by score descending)
        threshold: Similarity threshold

    Returns:
        Deduplicated items
    """
    if len(items) <= 1:
        return items

    # Find duplicate pairs
    dup_pairs = find_duplicates(items, threshold)

    # Mark indices to remove (always remove the lower-scored one)
    # Since items are pre-sorted by score, the second index is always lower
    to_remove = set()
    for i, j in dup_pairs:
        # Keep the higher-scored one (lower index in sorted list)
        if items[i].score >= items[j].score:
            to_remove.add(j)
        else:
            to_remove.add(i)

    # Return items not marked for removal
    return [item for idx, item in enumerate(items) if idx not in to_remove]


def dedupe_reddit(
    items: List[schema.RedditItem],
    threshold: float = 0.7,
) -> List[schema.RedditItem]:
    """Dedupe Reddit items."""
    return dedupe_items(items, threshold)


def dedupe_x(
    items: List[schema.XItem],
    threshold: float = 0.7,
) -> List[schema.XItem]:
    """Dedupe X items."""
    return dedupe_items(items, threshold)


def dedupe_youtube(
    items: List[schema.YouTubeItem],
    threshold: float = 0.7,
) -> List[schema.YouTubeItem]:
    """Dedupe YouTube items."""
    return dedupe_items(items, threshold)


def dedupe_hackernews(
    items: List[schema.HackerNewsItem],
    threshold: float = 0.7,
) -> List[schema.HackerNewsItem]:
    """Dedupe Hacker News items."""
    return dedupe_items(items, threshold)


def cross_source_link(
    *source_lists: List[AnyItem],
    threshold: float = 0.5,
) -> None:
    """Annotate items with cross-source references.

    Compares items across different source types using Jaccard similarity
    on char trigrams. When similarity exceeds threshold, adds bidirectional
    cross_refs with the related item's ID. Modifies items in-place.

    Args:
        *source_lists: Variable number of per-source item lists
        threshold: Similarity threshold for cross-linking (default 0.5)
    """
    all_items = []
    for source_list in source_lists:
        all_items.extend(source_list)

    if len(all_items) <= 1:
        return

    # Pre-compute trigrams using cross-source text extraction
    ngrams = [get_ngrams(_get_cross_source_text(item)) for item in all_items]

    for i in range(len(all_items)):
        for j in range(i + 1, len(all_items)):
            # Skip same-source comparisons (handled by per-source dedupe)
            if type(all_items[i]) is type(all_items[j]):
                continue

            similarity = jaccard_similarity(ngrams[i], ngrams[j])
            if similarity >= threshold:
                # Bidirectional cross-reference
                if all_items[j].id not in all_items[i].cross_refs:
                    all_items[i].cross_refs.append(all_items[j].id)
                if all_items[i].id not in all_items[j].cross_refs:
                    all_items[j].cross_refs.append(all_items[i].id)
