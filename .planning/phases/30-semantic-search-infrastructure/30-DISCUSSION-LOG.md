# Phase 30: Semantic Search Infrastructure - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-03-26
**Phase:** 30-Semantic Search Infrastructure
**Mode:** assumptions
**Areas analyzed:** ChromaDB Client Location, ChromaDB Storage Directory, Embedding Function, Model Pre-Download, Coexistence with sqlite-vec

## Assumptions Presented

### ChromaDB Client Location and Singleton Pattern
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| ChromaDB PersistentClient will be instantiated in `src/storage/` as module-level singleton | Confident | src/storage/__init__.py (lines 1-33), src/storage/sqlite.py:74-89 (get_db() pattern) |

### ChromaDB Storage Directory
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| ChromaDB data will be stored in `~/.local/share/rss-reader/chroma/` alongside SQLite | Confident | src/storage/sqlite.py:37 (platformdirs.user_data_dir) |

### Embedding Function for ChromaDB (all-MiniLM-L6-v2)
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| ChromaDB will use `sentence_transformers.SentenceTransformer("all-MiniLM-L6-v2")` | Confident | src/tags/ai_tagging.py:33,45, pyproject.toml:36 |

### Model Pre-Download Mechanism
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Model pre-download triggered during CLI startup in `src/cli/__init__.py` | Confident | src/cli/__init__.py:23-29 (startup pattern) |

### Coexistence with sqlite-vec (Not Replacement)
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| ChromaDB added alongside existing sqlite-vec embedding storage, not replacing it | Confident | Phase 18 D-16, ROADMAP "coexist with SQLite (not replace)" |

## Corrections Made

No corrections — all assumptions confirmed.

## External Research

No external research performed — existing research in planning/research/SUMMARY.md covered ChromaDB API patterns, pitfalls, and integration approaches.
