"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from src.application.dedup import deduplicate_articles
from src.application.summarize import summarize_article_content
from src.llm.chains import (
    get_classify_chain,
    get_layer_summary_chain,
    get_topic_title_chain,
    get_translate_chain,
)
from src.storage import list_articles_for_llm, update_article_llm
from src.storage.vector import get_chroma_collection

logger = logging.getLogger(__name__)

# Five-layer cake taxonomy (internal keys are always zh)
LAYER_KEYS = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"]

# Localized layer names
LAYER_NAMES = {
    "zh": ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"],
    "en": ["AI Application", "AI Model", "AI Infrastructure", "Chip", "Energy"],
}

LANG_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}


def _lang_name(code: str) -> str:
    """Return human-readable language name for LLM prompts."""
    return LANG_NAMES.get(code, "Chinese")


def _layer_names(lang: str) -> list[str]:
    """Return layer category names in the specified language."""
    return LAYER_NAMES.get(lang, LAYER_NAMES["zh"])


# ---------------------------------------------------------------------------
# v2 report helpers — topic clustering
# ---------------------------------------------------------------------------

# Keywords for Section B (signals) rule-based classification
_LEVERAGE_KEYWORDS = [
    "tool",
    "platform",
    "api",
    "framework",
    "open source",
    "library",
    "sdk",
    "model",
    "release",
    "launch",
    "github",
    "npm",
    "pypi",
    "runtime",
    "compiler",
    "assistant",
    "agent",
    "claude",
    "gpt",
    "gemini",
    "openai",
    "anthropic",
]
_BUSINESS_KEYWORDS = [
    "startup",
    "funding",
    "raise",
    "series",
    "ipo",
    "business model",
    "revenue",
    "unicorn",
    "vc",
    "venture",
    "investor",
    "seed round",
    " Series A",
    " Series B",
    "acqui-hire",
    "acquisition",
    "merger",
    "profit",
]

# Keywords for Section C (creation) rule-based classification
_CREATION_KEYWORDS = [
    "how to",
    "tutorial",
    "review",
    "top",
    "best",
    "vs",
    "comparison",
    "guide",
    "introduction",
    "beginner",
    "getting started",
    "101",
    "cheat sheet",
    "tips",
    "master",
    "learn",
    "course",
    "workshop",
]


def _keyword_overlap(title1: str, title2: str) -> float:
    """Compute simple keyword overlap between two titles (0.0–1.0)."""
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


async def _cluster_articles_into_topics(
    articles: list[dict],
    target_lang: str,
) -> list[dict]:
    """Group articles into topics by theme within a layer.

    Clustering strategy (embedding-based, replacing keyword overlap):
      1. Fetch ChromaDB embeddings for all articles.
      2. K-Means clustering with dynamic k = max(5, min(sqrt(n/2), 50)).
      3. Merge small clusters (<=2) with nearest neighbour by cosine similarity.
      4. Generate a short topic title via get_topic_title_chain.

    Each topic dict has keys: title, sources (list of article dicts),
    sources_count, insight (empty str, filled later by caller).
    """

    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity

    if not articles:
        return []

    # Step 1 — fetch ChromaDB embeddings
    ids = [a["id"] for a in articles]

    try:
        collection = get_chroma_collection()
        existing = collection.get(ids=ids, include=["embeddings"])
        chroma_ids = existing.get("ids", [])
        embeddings_list: list[list[float] | None] = existing.get("embeddings", [])
        id_to_embedding: dict[str, list[float]] = {}
        for i, cid in enumerate(chroma_ids):
            emb = embeddings_list[i] if i < len(embeddings_list) else None
            if cid is not None and emb is not None:
                id_to_embedding[cid] = emb
    except Exception as e:
        logger.warning(
            "ChromaDB fetch for clustering failed: %s. Falling back to feed_id grouping.",
            e,
        )
        id_to_embedding = {}

    articles_with_emb: list[dict] = []
    emb_matrix: list[list[float]] = []
    for a in articles:
        e = id_to_embedding.get(a["id"])
        if e is not None:
            articles_with_emb.append(a)
            emb_matrix.append(e)

    n = len(articles_with_emb)

    if n >= 5 and emb_matrix:
        # Step 2 — dynamic k selection: k = max(10, n // 5)
        k = max(10, n // 5)
        k = min(k, n)  # can't have more clusters than articles

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=3)
        cluster_labels = kmeans.fit_predict(emb_matrix)

        # Build initial cluster groups
        clusters: list[list[dict]] = [[] for _ in range(k)]
        for i, a in enumerate(articles_with_emb):
            clusters[cluster_labels[i]].append(a)

        # Step 3 — merge small clusters (<=2) with nearest neighbour
        changed = True
        while changed:
            changed = False
            new_clusters: list[list[dict]] = []
            skip = set()
            for i, group in enumerate(clusters):
                if i in skip:
                    continue
                if len(group) <= 3 and len(clusters) > 1:
                    # Find nearest neighbour cluster by centroid cosine similarity
                    if emb_matrix and len(emb_matrix) == len(articles_with_emb):
                        # Recompute cluster centroids
                        centroids: list[list[float]] = []
                        for g in clusters:
                            if not g:
                                centroids.append(
                                    [0.0] * len(emb_matrix[0]) if emb_matrix else []
                                )
                            else:
                                indices = [
                                    articles_with_emb.index(a)
                                    for a in g
                                    if a in articles_with_emb
                                ]
                                if indices:
                                    vecs = [emb_matrix[idx] for idx in indices]
                                    centroid = [
                                        sum(v[j] for v in vecs) / len(vecs)
                                        for j in range(len(vecs[0]))
                                    ]
                                    centroids.append(centroid)
                                else:
                                    centroids.append(
                                        [0.0] * len(emb_matrix[0]) if emb_matrix else []
                                    )

                    best_score = -1.0
                    best_j = -1
                    for j, _other in enumerate(clusters):
                        if j == i or j in skip:
                            continue
                        if not centroids[i] or not centroids[j]:
                            continue
                        try:
                            sim = cosine_similarity([centroids[i]], [centroids[j]])[0][
                                0
                            ]
                            if sim > best_score:
                                best_score = sim
                                best_j = j
                        except Exception:
                            pass
                    if best_j >= 0:
                        clusters[best_j].extend(group)
                        skip.add(i)
                        skip.add(best_j)
                        new_clusters.append(clusters[best_j])
                        changed = True
                    else:
                        new_clusters.append(group)
                else:
                    new_clusters.append(group)
            if changed:
                clusters = [c for i, c in enumerate(clusters) if i not in skip]
            else:
                break

        # Deduplicate new_clusters to fix report-004: after merging, clusters[best_j]
        # and group are the SAME list object. Both get appended to new_clusters,
        # causing duplicate topic entries. Deduplicate by object id (same pattern as
        # the v1 fallback branch at lines 341-350).
        seen: set[int] = set()
        deduped_clusters: list[list[dict]] = []
        for c in new_clusters:
            key = id(c)
            if key not in seen:
                seen.add(key)
                deduped_clusters.append(c)
        new_clusters = deduped_clusters

        topics: list[dict] = [
            {
                "title": "",
                "sources": g,
                "sources_count": len(g),
                "insight": "",
            }
            for g in clusters
            if g
        ]

        # Articles without embeddings: group by feed_id fallback
        articles_no_emb = [a for a in articles if a["id"] not in id_to_embedding]
        if articles_no_emb:
            feed_groups: dict[str, list[dict]] = {}
            for a in articles_no_emb:
                fid = a.get("feed_id") or "unknown"
                feed_groups.setdefault(fid, []).append(a)
            for arts in feed_groups.values():
                topics.append(
                    {
                        "title": "",
                        "sources": arts,
                        "sources_count": len(arts),
                        "insight": "",
                    }
                )
    else:
        # Fallback: feed_id grouping + keyword overlap (original behaviour)
        feed_groups: dict[str, list[dict]] = {}
        for a in articles:
            fid = a.get("feed_id") or "unknown"
            feed_groups.setdefault(fid, []).append(a)

        topics: list[dict] = []
        for _fid, arts in feed_groups.items():
            topics.append(
                {
                    "title": "",
                    "sources": arts,
                    "sources_count": len(arts),
                    "insight": "",
                }
            )

        # Merge small clusters
        merged = True
        while merged:
            merged = False
            new_topics: list[dict] = []
            skip = set()
            for i, t1 in enumerate(topics):
                if i in skip:
                    continue
                if t1["sources_count"] <= 3:
                    best_score = 0.2
                    best_j = -1
                    for j, t2 in enumerate(topics):
                        if j == i or j in skip:
                            continue
                        titles_i = " ".join(a.get("title", "") for a in t1["sources"])
                        titles_j = " ".join(a.get("title", "") for a in t2["sources"])
                        score = _keyword_overlap(titles_i, titles_j)
                        if score > best_score:
                            best_score = score
                            best_j = j
                    if best_j >= 0:
                        t2 = topics[best_j]
                        t2["sources"].extend(t1["sources"])
                        t2["sources_count"] = len(t2["sources"])
                        skip.add(i)
                        skip.add(best_j)
                        new_topics.append(t2)
                        merged = True
                    else:
                        new_topics.append(t1)
                else:
                    new_topics.append(t1)
            if merged:
                seen = set()
                filtered = []
                for t in new_topics:
                    key = id(t)
                    if key not in seen:
                        seen.add(key)
                        filtered.append(t)
                topics = filtered
                merged = True

    # Step 4 — generate topic titles via LLM
    semaphore = asyncio.Semaphore(5)

    async def title_for(topic: dict) -> dict:
        async with semaphore:
            article_list = "\n".join(
                f"- {a.get('title', 'Untitled')}" for a in topic["sources"][:8]
            )
            try:
                chain = get_topic_title_chain()
                title = await chain.ainvoke(
                    {
                        "article_list": article_list,
                        "target_lang": _lang_name(target_lang),
                    }
                )
                topic["title"] = title.strip()
            except Exception as e:
                logger.warning("Topic title generation failed: %s", e)
                topic["title"] = (
                    topic["sources"][0].get("title", "Misc")[:20]
                    if topic["sources"]
                    else "Misc"
                )
        return topic

    titled = await asyncio.gather(
        *[title_for(t) for t in topics], return_exceptions=True
    )
    result: list[dict] = []
    for t in titled:
        if isinstance(t, Exception):
            logger.warning("Topic title task failed: %s", t)
            continue
        result.append(t)

    return result


def _classify_signal_leverage(article: dict) -> bool:
    """Rule-based check if article is about developer tools / AI platforms."""
    text = (
        article.get("title", "")
        + " "
        + article.get("summary", "")
        + " "
        + article.get("description", "")
    ).lower()
    return any(kw in text for kw in _LEVERAGE_KEYWORDS)


def _classify_signal_business(article: dict) -> bool:
    """Rule-based check if article is about startups / funding / business."""
    text = (
        article.get("title", "")
        + " "
        + article.get("summary", "")
        + " "
        + article.get("description", "")
    ).lower()
    return any(kw in text for kw in _BUSINESS_KEYWORDS)


def _classify_creation(article: dict) -> bool:
    """Rule-based check if article is a tutorial / how-to / review / best-of."""
    text = (
        article.get("title", "")
        + " "
        + article.get("summary", "")
        + " "
        + article.get("description", "")
    ).lower()
    return any(kw in text for kw in _CREATION_KEYWORDS)


def _is_chinese(text: str) -> bool:
    """Detect if text contains Chinese characters."""
    return bool(re.search(r"[\u4e00-\u9fff]", text))


# In-memory cache for title translations to avoid repeated LLM calls
_title_translate_cache: dict[tuple[str, str], str] = {}


def _translate_title_sync(title: str, target_lang: str) -> str:
    """Translate article title to target language (sync, for template use).

    Titles should be pre-translated by render_report/render_report_v2
    before template rendering. This function only performs cache lookup
    to avoid asyncio.run_until_complete() misuse in async context.
    """
    if target_lang == "zh":
        return title
    cache_key = (title, target_lang)
    if cache_key in _title_translate_cache:
        return _title_translate_cache[cache_key]

    # Cache miss — pre-translation should have populated the cache.
    # Return original title as fallback to avoid blocking on LLM call.
    logger.warning(
        "Title translation cache miss for '%s' -> %s. "
        "Pre-translation may not have run correctly.",
        title[:50],
        target_lang,
    )
    return title


async def _translate_titles_batch_async(
    titles: list[str], target_lang: str
) -> dict[str, str]:
    """Pre-translate all titles in batch to avoid per-title event loop creation (Fix #5).

    Returns a dict mapping original title -> translated title.
    """
    if target_lang == "zh" or not titles:
        return {}
    chain = get_translate_chain()
    semaphore = asyncio.Semaphore(5)  # max 5 concurrent LLM calls

    async def translate_one(title: str) -> tuple[str, str]:
        async with semaphore:
            result = await chain.ainvoke({"text": title, "target_lang": target_lang})
            return (title, result)

    results = await asyncio.gather(
        *[translate_one(t) for t in titles], return_exceptions=True
    )
    return {
        title: translated
        for title, translated in results
        if not isinstance(translated, Exception)
    }


def _format_article_title(title: str, target_lang: str) -> str:
    """Format article title with translation if needed.

    Returns:
        - title (if target_lang == zh or title is not Chinese)
        - title（translated）if title is Chinese and target_lang != zh
    """
    if target_lang == "zh" or not _is_chinese(title):
        return title
    translated = _translate_title_sync(title, target_lang)
    return f"{title}（{translated}）"


# Template directory
DEFAULT_TEMPLATE_DIR = Path("~/.config/feedship/templates").expanduser()
DEFAULT_TEMPLATE_NAME = "default"


async def classify_article_layer(text: str, title: str = "") -> str:
    """Classify an article into one of the AI five-layer cake categories.

    Returns one of: AI应用, AI模型, AI基础设施, 芯片, 能源
    """
    sample = " ".join(text.split()[:300])
    try:
        chain = get_classify_chain()
        result = await chain.ainvoke({"title": title, "content": sample})
        # Match against known categories
        for cat in LAYER_KEYS:
            if cat in result:
                return cat
        # Fallback: return first match or default
        for cat in LAYER_KEYS:
            if cat.split("(")[0].strip() in result:
                return cat
        logger.warning("Could not classify article layer from: %s", result.strip())
        return "AI应用"  # Default fallback
    except Exception as e:
        logger.warning("Failed to classify article layer: %s", e)
        return "AI应用"


async def classify_cluster_layer(articles: list[dict], target_lang: str = "zh") -> str:
    """Classify a cluster of articles into one of the AI five-layer cake categories.

    Instead of calling LLM per article, combines all article texts and classifies once.

    Args:
        articles: List of article dicts with 'title' and 'summary' keys.
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        One of: AI应用, AI模型, AI基础设施, 芯片, 能源
    """
    if not articles:
        return "AI应用"

    # Build combined text from first 15 articles (avoid prompt bloat)
    texts = []
    for a in articles[:15]:
        title = a.get("title", "")
        summary = a.get("summary", "") or ""
        texts.append(f"{title}: {summary[:200]}")
    cluster_text = "\n".join(texts)

    sample = " ".join(cluster_text.split()[:500])
    try:
        chain = get_classify_chain()
        result = await chain.ainvoke(
            {"title": "Cluster Classification", "content": sample}
        )
        for cat in LAYER_KEYS:
            if cat in result:
                return cat
            for c in LAYER_KEYS:
                if c.split("(")[0].strip() in result:
                    return c
        logger.warning("Could not classify cluster layer from: %s", result.strip())
        return "AI应用"
    except Exception as e:
        logger.warning("Failed to classify cluster layer: %s", e)
        return "AI应用"


async def generate_cluster_summary(
    articles: list[dict], layer: str, target_lang: str = "zh"
) -> str:
    """Generate a 2-3 paragraph summary for a cluster of articles.

    Args:
        articles: List of article dicts with title, summary, link, quality_score.
        layer: The layer category name.
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        A paragraph summarizing the articles in this cluster.
    """
    if not articles:
        return ""

    # Build article list for prompt
    article_list = "\n".join(
        f"- {a.get('title', 'Untitled')} (q={a.get('quality_score') or 0:.2f})"
        for a in articles[:10]  # Max 10 articles in prompt
    )

    # Retry with exponential backoff: 2s, 4s, 8s
    delays = [2, 4, 8]
    for attempt, delay in enumerate(delays):
        try:
            chain = get_layer_summary_chain()
            return await chain.ainvoke(
                {
                    "layer": layer,
                    "article_list": article_list,
                    "target_lang": _lang_name(target_lang),
                }
            )
        except Exception as e:
            if attempt < len(delays) - 1:
                logger.warning(
                    "Cluster summary attempt %d failed: %s. Retrying in %ds...",
                    attempt + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    "Cluster summary all %d attempts failed: %s. Returning fallback.",
                    len(delays),
                    e,
                )

    # After 3 failures, return language-aware fallback
    fallbacks = {
        "zh": "（本周暂无重大进展）",
        "en": "(No significant developments this week)",
        "ja": "（今週の重大な展開なし）",
        "ko": "（이번 주 중요한 발전 없음）",
    }
    return fallbacks.get(target_lang, fallbacks["zh"])


def cluster_articles_for_report(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Fetch and cluster articles for a report date range.

    Args:
        since: Start date YYYY-MM-DD
        until: End date YYYY-MM-DD
        limit: Max articles to process
        auto_summarize: If True, summarize unsummarized articles on-demand
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        dict with keys: articles_by_layer (dict of layer -> list),
        layer_summaries (dict of layer -> summary text), date_range,
        summarized_on_demand (count of articles summarized during generation)
    """
    # Fetch ALL articles in date range (unsummarized_only=False)
    # On-demand summarize handles weight-based gating inside _cluster_articles_async
    articles = list_articles_for_llm(
        limit=limit,
        since=since,
        until=until,
        unsummarized_only=False,
    )

    return asyncio.run(
        _cluster_articles_async(articles, since, until, auto_summarize, target_lang)
    )


async def _cluster_articles_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Async helper to cluster articles by layer."""
    # Use pre-fetched articles directly (from cluster_articles_for_report)
    articles = pre_fetched_articles

    # Classify each article into a layer
    results: dict[str, list] = {cat: [] for cat in LAYER_KEYS}
    summarized_on_demand: int = 0

    # Collect pending DB writes to execute after gather (Fix #3)
    pending_writes_v1: list[tuple] = []

    async def process_one(article: dict) -> tuple[str, dict]:
        # Use article fields directly from pre-fetched list (no redundant DB query)
        full = article
        summary = full.get("summary") or ""
        title = full.get("title", "")
        feed_weight = full.get("feed_weight", 0)

        # On-demand summarize if missing AND feed weight >= 0.7
        nonlocal summarized_on_demand
        if not summary and auto_summarize and feed_weight >= 0.7:
            content = full.get("content") or full.get("description") or ""
            if content:
                try:
                    summary, _, quality, _ = await summarize_article_content(
                        content, title
                    )
                    full["summary"] = summary
                    full["quality_score"] = quality
                    summarized_on_demand += 1
                    # Collect write params for post-gather batch (Fix #3: no sync DB inside gather)
                    pending_writes_v1.append((article["id"], summary, quality, [], []))
                except Exception as e:
                    logger.warning(
                        "On-demand summarize failed for %s: %s", article["id"], e
                    )

        text = summary or full.get("content") or full.get("description") or ""
        layer = await classify_article_layer(text, title)
        return layer, {
            "id": article["id"],
            "title": title,
            "link": full.get("link", ""),
            "summary": full.get("summary", ""),
            "quality_score": full.get("quality_score"),
            "published_at": full.get("published_at"),
        }

    semaphore = asyncio.Semaphore(10)

    async def bounded_process(a: dict) -> tuple[str, dict]:
        async with semaphore:
            return await process_one(a)

    if articles:
        classified = await asyncio.gather(
            *[bounded_process(a) for a in articles],
            return_exceptions=True,
        )
        for item in classified:
            if isinstance(item, Exception):
                continue
            layer, article_dict = item
            if layer in results:
                results[layer].append(article_dict)

    # Execute pending DB writes sequentially after gather (Fix #3)
    for params in pending_writes_v1:
        update_article_llm(*params)

    # Generate summaries for each layer
    layer_summaries: dict[str, str] = {}
    for layer, arts in results.items():
        if arts:
            layer_summaries[layer] = await generate_cluster_summary(
                arts, layer, target_lang
            )

    return {
        "articles_by_layer": results,
        "layer_summaries": layer_summaries,
        "date_range": {"since": since, "until": until},
        "summarized_on_demand": summarized_on_demand,
    }


# ---------------------------------------------------------------------------
# v2 report — topic clustering + signals + creation
# ---------------------------------------------------------------------------


async def _cluster_articles_v2_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
) -> dict[str, Any]:
    """Async implementation of v2 clustering with topic grouping.

    NEW FLOW: process all (no LLM layer classify) -> deduplicate ->
    cluster all -> classify per cluster -> group by layer -> Section B/C
    """
    articles = pre_fetched_articles

    # Collect pending DB writes to execute after gather (Fix #3)
    pending_writes_v2: list[tuple] = []

    async def process_one(article: dict) -> dict:
        """Process article: on-demand summarize if needed. No layer classification."""
        full = article
        summary = full.get("summary") or ""
        title = full.get("title", "")
        feed_weight = full.get("feed_weight", 0)
        feed_id = full.get("feed_id", "unknown")

        if not summary and auto_summarize and feed_weight >= 0.7:
            content = full.get("content") or full.get("description") or ""
            if content:
                try:
                    summary, _, quality, _ = await summarize_article_content(
                        content, title
                    )
                    full["summary"] = summary
                    full["quality_score"] = quality
                    # Collect write params for post-gather batch (Fix #3: no sync DB inside gather)
                    pending_writes_v2.append((article["id"], summary, quality, [], []))
                except Exception as e:
                    logger.warning(
                        "On-demand summarize failed for %s: %s", article["id"], e
                    )

        processed = {
            "id": article["id"],
            "title": title,
            "link": full.get("link", ""),
            "summary": full.get("summary", ""),
            "quality_score": full.get("quality_score"),
            "published_at": full.get("published_at"),
            "feed_id": feed_id,
        }
        return processed

    # Process all articles (no LLM layer classification yet)
    all_processed: list[dict] = []
    semaphore = asyncio.Semaphore(10)

    async def bounded_process(a: dict) -> dict:
        async with semaphore:
            return await process_one(a)

    if articles:
        results = await asyncio.gather(
            *[bounded_process(a) for a in articles],
            return_exceptions=True,
        )
        for item in results:
            if isinstance(item, Exception):
                continue
            processed = item
            all_processed.append(processed)

    # Execute pending DB writes sequentially after gather (Fix #3)
    for params in pending_writes_v2:
        update_article_llm(*params)

    # Three-level deduplication FIRST (before any clustering)
    all_processed = deduplicate_articles(all_processed)

    # Cluster ALL deduplicated articles together (not per-layer)
    all_topics = await _cluster_articles_into_topics(all_processed, target_lang)

    # Classify each cluster into a layer (1 LLM call per cluster)
    for topic in all_topics:
        topic["layer"] = await classify_cluster_layer(topic["sources"], target_lang)

    # Group topics by layer for template rendering
    articles_by_layer: dict[str, list[dict]] = {cat: [] for cat in LAYER_KEYS}
    for topic in all_topics:
        layer = topic.get("layer", "AI应用")
        if layer in articles_by_layer:
            articles_by_layer[layer].append(topic)

    layers_data: list[dict] = []
    for layer_name in LAYER_KEYS:
        layers_data.append(
            {
                "name": layer_name,
                "topics": articles_by_layer.get(layer_name, []),
            }
        )

    # Section B/C — signal classification uses clustered articles
    # Build flat list of all clustered articles for signal matching
    clustered_articles = [a for topic in all_topics for a in topic["sources"]]
    leverage_topics: list[dict] = []
    business_topics: list[dict] = []
    for article in clustered_articles:
        if _classify_signal_leverage(article):
            leverage_topics.append(article)
        elif _classify_signal_business(article):
            business_topics.append(article)

    # Section C — creation
    creation_sections: list[dict] = []
    creation_arts = [a for a in clustered_articles if _classify_creation(a)]
    if creation_arts:
        creation_topics = await _cluster_articles_into_topics(
            creation_arts, target_lang
        )
        creation_sections.append(
            {
                "name": "创作选题",
                "topics": creation_topics,
            }
        )

    return {
        "layers": layers_data,
        "signals": {
            "leverage": leverage_topics,
            "business": business_topics,
        },
        "creation": creation_sections,
        "date_range": {"since": since, "until": until},
    }


def cluster_articles_for_report_v2(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Fetch and cluster articles for a v2 report with topic clustering.

    Returns:
        dict with keys: layers (list of {name, topics}), signals
        ({leverage, business}), creation (list of {name, topics}),
        date_range ({since, until}).
    """
    articles = list_articles_for_llm(
        limit=limit,
        since=since,
        until=until,
        unsummarized_only=False,
    )
    return asyncio.run(
        _cluster_articles_v2_async(articles, since, until, auto_summarize, target_lang)
    )


async def render_report_v2(
    data: dict[str, Any],
    template_name: str = "v2",
    target_lang: str = "zh",
) -> str:
    """Render a v2 report using Jinja2 template (async, Fix #3)."""
    # Pre-translate all titles before template rendering (Fix #5)
    if target_lang != "zh":
        all_titles: list[str] = []
        # Collect from layers -> topics -> sources
        for layer_data in data.get("layers", []):
            for topic in layer_data.get("topics", []):
                for article in topic.get("sources", []):
                    title = article.get("title", "")
                    if title and _is_chinese(title):
                        all_titles.append(title)
        # Collect from signals
        for sig_type in ["leverage", "business"]:
            for article in data.get("signals", {}).get(sig_type, []):
                title = article.get("title", "")
                if title and _is_chinese(title):
                    all_titles.append(title)
        # Collect from creation
        for creation_data in data.get("creation", []):
            for topic in creation_data.get("topics", []):
                for article in topic.get("sources", []):
                    title = article.get("title", "")
                    if title and _is_chinese(title):
                        all_titles.append(title)

        if all_titles:
            # Deduplicate titles to avoid redundant LLM calls
            unique_titles = list(dict.fromkeys(all_titles))
            pre_translated = await _translate_titles_batch_async(
                unique_titles, target_lang
            )
            # Populate cache for template filters
            for orig, translated in pre_translated.items():
                _title_translate_cache[(orig, target_lang)] = translated

    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        logger.error("Jinja2 not installed: pip install jinja2")
        raise

    template_path = DEFAULT_TEMPLATE_DIR / f"{template_name}.md"
    if template_path.exists():
        env = Environment(
            loader=FileSystemLoader(template_path.parent),
            autoescape=False,
        )
        env.filters["format_title"] = lambda title: _format_article_title(
            title, target_lang
        )
        template = env.get_template(template_path.name)
    else:
        logger.error("v2 template not found at %s", template_path)
        raise FileNotFoundError(
            f"Template '{template_name}' not found at {template_path}"
        )

    return template.render(
        layers=data.get("layers", []),
        signals=data.get("signals", {}),
        creation=data.get("creation", []),
        date_range=data.get("date_range", {}),
        target_lang=target_lang,
    )


async def render_report(
    data: dict[str, Any],
    template_name: str = DEFAULT_TEMPLATE_NAME,
    target_lang: str = "zh",
) -> str:
    """Render a report using Jinja2 template (async, Fix #3).

    Args:
        data: Report data from cluster_articles_for_report()
        template_name: Template name (without extension)
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        Rendered markdown string.
    """
    # Pre-translate all titles before template rendering (Fix #5)
    if target_lang != "zh":
        all_titles: list[str] = []
        for layer_articles in data.get("articles_by_layer", {}).values():
            for article in layer_articles:
                title = article.get("title", "")
                if title and _is_chinese(title):
                    all_titles.append(title)
        if all_titles:
            unique_titles = list(dict.fromkeys(all_titles))
            pre_translated = await _translate_titles_batch_async(
                unique_titles, target_lang
            )
            for orig, translated in pre_translated.items():
                _title_translate_cache[(orig, target_lang)] = translated

    try:
        from jinja2 import Environment, FileSystemLoader, Template
    except ImportError:
        logger.error("Jinja2 not installed: pip install jinja2")
        raise

    # Find template
    template_path = DEFAULT_TEMPLATE_DIR / f"{template_name}.md"
    if not template_path.exists():
        # Create default template
        _create_default_template()
        template_path = DEFAULT_TEMPLATE_DIR / f"{template_name}.md"

    if template_path.exists():
        env = Environment(
            loader=FileSystemLoader(template_path.parent),
            autoescape=False,
        )
        env.filters["format_title"] = lambda title: _format_article_title(
            title, target_lang
        )
        template = env.get_template(template_path.name)
    else:
        # Fallback to built-in template
        template = Template(_DEFAULT_TEMPLATE_MARKDOWN)

    return template.render(
        articles_by_layer=data["articles_by_layer"],
        layer_summaries=data["layer_summaries"],
        date_range=data["date_range"],
        categories=_layer_names(target_lang),
        target_lang=target_lang,
    )


def _create_default_template() -> None:
    """Create the default template if it doesn't exist."""
    DEFAULT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    template_path = DEFAULT_TEMPLATE_DIR / f"{DEFAULT_TEMPLATE_NAME}.md"
    if not template_path.exists():
        template_path.write_text(_DEFAULT_TEMPLATE_MARKDOWN)
        logger.info("Created default template at %s", template_path)


async def _translate_report_async(report_text: str, target_lang: str) -> str:
    """Internal async translation implementation with batched LLM calls (Fix #4).

    Batches 10 lines per LLM call instead of O(n) calls for a 200-line report.
    """
    if target_lang == "zh":
        return report_text

    chain = get_translate_chain()
    lines = report_text.splitlines()
    translated_lines = []
    batch_size = 10

    i = 0
    while i < len(lines):
        batch = lines[i : i + batch_size]
        non_link_lines: list[tuple[int, str]] = []

        # Separate link lines from content lines
        for j, line in enumerate(batch):
            if "]((" in line or "](http" in line or "](https" in line:
                # Link line: skip translation, preserve as-is
                translated_lines.append(line)
            else:
                non_link_lines.append((j, line))

        # Translate non-link lines in batch
        if non_link_lines:
            # Format as numbered list for LLM
            prompt_lines = [f"{idx + 1}. {line}" for idx, line in non_link_lines]
            prompt = "\n".join(prompt_lines)

            try:
                result = await chain.ainvoke(
                    {
                        "text": f"Translate the following lines to {target_lang}. Keep line numbers as reference:\n{prompt}",
                        "target_lang": target_lang,
                    }
                )
                # Parse result — extract translated lines by stripping numbered prefix
                result_lines = result.strip().split("\n")
                for rline in result_lines:
                    rline = rline.strip()
                    if rline and rline[0].isdigit() and ". " in rline:
                        rline = rline.split(". ", 1)[1]
                    translated_lines.append(rline)
            except Exception as e:
                logger.warning(
                    "Batch translation failed, falling back to original: %s", e
                )
                # Fallback: append original lines
                for _, line in non_link_lines:
                    translated_lines.append(line)

        i += batch_size

    return "\n".join(translated_lines)


async def translate_report_async(report_text: str, target_lang: str) -> str:
    """Async translate report text to target language (Fix #3).

    Args:
        report_text: The rendered report text.
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        Translated report text, or original if target_lang is "zh".
    """
    if target_lang == "zh":
        return report_text

    return await _translate_report_async(report_text, target_lang)


# Built-in default template (used when file not found)
_DEFAULT_TEMPLATE_MARKDOWN = """\
# AI 日报 — {{ date_range.since }} ~ {{ date_range.until }}

{% set layer_keys = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"] %}
{% for layer_name in categories %}
{% set layer = layer_keys[loop.index0] %}
{% set articles = articles_by_layer.get(layer, []) %}
{% set summary = layer_summaries.get(layer, "") %}
{% if articles and summary and summary|trim %}
### {{ loop.index }}. {{ layer_name }}

{{ summary }}

{% for article in articles[:10] %}
- [{{ article.title | format_title }}]({{ article.link }}) (q={{ "%.2f"|format(article.quality_score or 0) }})
{% endfor %}

{% endif %}
{% endfor %}
"""
