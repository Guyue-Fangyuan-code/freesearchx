# FreeSearchX CLI reference

Invoke:

```bash
python scripts/freesearchx.py [options] [query]
# or, after pip install -e .:
freesearchx [options] [query]
```

## Modes

| Invocation | Purpose |
|------------|---------|
| `"query"` | Web search (dynamic 5–20 by relevance) |
| `"query" -n N` | Fixed top-N search |
| `"query" --academic` | Prefer paper / primary / code / docs; drop aggregators & blogs |
| `"query" --images` | Image search |
| `"query" --deep` | Search, then fetch full text for top hits |
| `"query" --deep --deep-n K` | Deep-fetch K hits (default K=3) |
| `--read URL` | Fetch one page; arXiv URLs use the official API abstract |
| `--verify "ref1\|\|\|ref2"` | Citation existence check |
| `--clear-cache` / `--cache-info` | Cache maintenance |
| `-V` / `--version` | Print version |

## Global flags

| Flag | Meaning |
|------|---------|
| `--json` | Machine-readable JSON on stdout |
| `--no-cache` | Do not read or write the 7-day local cache |
| `-n N` | Result count (search/images; omit search N for dynamic 5–20) |

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `HTTPS_PROXY` / `HTTP_PROXY` | unset | Outbound proxy |
| `FRESEARCHX_HF_MIRROR` or `HF_ENDPOINT` | unset | Opt-in HuggingFace host rewrite |
| `FRESEARCHX_INSECURE` | off | Set `1` to disable TLS verification |

## Exit codes

- `0` — success (including empty-but-valid help)
- `1` — search/fetch failed or returned nothing usable

## JSON shapes (abridged)

**Search**

```json
{
  "ok": true,
  "query": "...",
  "mode": "dynamic|top-N",
  "academic": false,
  "count": 7,
  "results": [
    {"rank": 1, "tag": "paper", "title": "...", "url": "...", "snippet": "...", "score": 5}
  ]
}
```

**Deep search** — same as search, plus:

```json
{
  "deep_n": 3,
  "fetched": [
    {"rank": 1, "tag": "paper", "title": "...", "url": "...", "content": "...", "fetch_ok": true}
  ]
}
```

**Verify**

```json
{
  "ok": true,
  "count": 1,
  "results": [
    {
      "rank": 1,
      "ref": "...",
      "status": "VERIFIED|UNSURE|NOT_FOUND|SEARCH_FAILED",
      "confidence": 0.98,
      "similarity": 1.0,
      "best_match_title": "...",
      "best_match_url": "...",
      "note": "via arXiv API"
    }
  ]
}
```

## Source tags

| Tag | Typical hosts |
|-----|----------------|
| `paper` | arxiv.org |
| `primary` | openreview, ACL, PMLR, IEEE, ACM, … |
| `code` | github, gitlab, huggingface |
| `docs` | docs.*, readthedocs, `/docs/` |
| `blog` | medium, substack, dev.to, … |
| `aggregator` | csdn, juejin, zhihu, … |
| `other` | everything else |
