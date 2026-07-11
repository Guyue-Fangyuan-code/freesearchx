# FreeSearchX workflow notes

## Why search and fetch are separate

| Phase | Cost | What you get |
|-------|------|----------------|
| **Search** | Low (one SERP call) | Many candidates: title, tag, URL, short snippet |
| **Fetch / `--read`** | High (one HTTP+parse per URL) | Full page text or clean arXiv abstract |

Agents that always deep-fetch every hit waste time, burn rate limits, and flood
the context window with irrelevant HTML. The intended loop:

1. `search` → scan **all** rows and tags  
2. pick 1–3 URLs that actually answer the question  
3. `--read` those only  

`--deep` exists for the case where you already know “top-K is enough” (e.g.
academic survey with `--academic --deep --deep-n 3`). It is a convenience
stitch, not a replacement for judgment.

## When to use which mode

| Situation | Command |
|-----------|---------|
| Open-ended “what exists on X?” | `"X"` (dynamic) |
| Need a fixed shortlist | `"X" -n 10` |
| Literature / PEFT / venues | `"X" --academic` |
| Writing related work, need abstracts now | `"X" --academic --deep` |
| User pasted a link | `--read URL` |
| Paper draft citations look suspicious | `--verify "full title…"` |
| UI / diagram assets | `"X" --images` |
| Pipelines / tools that parse stdout | add `--json` |

## Academic tips

- Prefer `[paper]` and `[primary]` over `[aggregator]` reposts.
- arXiv `--read` returns title, authors, date, abstract via the **official API**
  (modern ids like `2303.10512v2` and legacy ids like `hep-th/9901001`).
- `--verify` first tries arXiv title search, then the web. High confidence
  `VERIFIED` is usable; `UNSURE` is a lead, not a green light.

## Ranking (short)

Score ≈ source tier + title/query token overlap (whitespace tokens and CJK
character bigrams). Dynamic mode keeps up to 20 hits but stops early when scores
fall off, with a floor of 5.

## Caching

- TTL 7 days, SHA-256 keys, atomic writes under skill-root `cache/`.
- `--no-cache` for live-only calls.
- Cache stores rendered text or JSON payloads; bump of internal key version
  invalidates old shapes automatically.
