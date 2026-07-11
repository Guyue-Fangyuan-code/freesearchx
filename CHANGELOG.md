# Changelog

## 0.1.1 — 2026-07-12

- Clean glued multi-site SERP titles
- Prefer arXiv /abs/ over /html/ and /pdf/; dedupe paper variants
- Soft-demote aggregator hosts in default ranking

## 0.1.0 — 2026-07-11

First public release.

- Agent-skill layout: SKILL.md + scripts/ + references/
- Dynamic 5-20 search with source tags and CJK-aware relevance
- Two-phase search->fetch; optional --deep / --deep-n
- arXiv official API fetch (modern + legacy ids)
- Citation verification with similarity + confidence
- Image search, local cache, --json
- TLS on by default; HuggingFace mirror opt-in only
