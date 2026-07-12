---
name: freesearchx
description: >
  Free web search, page fetch, arXiv abstracts, and citation verification
  (DuckDuckGo + arXiv API). No API key. Use this skill whenever the user or
  the task needs to look something up online, find papers or docs, fetch a URL
  or arXiv abstract, check whether a citation is real (not AI-fabricated), or
  search images — even if they only say "search", "google", "look up", "find
  papers", "read this link", or "verify this reference". Prefer this over
  guessing from memory when fresh or source-backed information matters.
license: MIT
---

# FreeSearchX

Agent skill for free web search + fetch + citation checks. The executable is a
black-box CLI under `scripts/`; call it via Bash — do not load the whole script
into context unless you are debugging the tool itself.

## Layout

```text
freesearchx/
├── SKILL.md                 # this file (workflow for the agent)
├── scripts/
│   └── freesearchx.py       # CLI — invoke with python, pass --help first if unsure
└── references/
    ├── cli.md               # full flag reference
    └── workflow.md          # when to search vs deep-fetch vs verify
```

## Setup (once per machine)

```bash
pip install -r requirements.txt
# optional global CLI entrypoint:
pip install -e .
```

Resolve `SCRIPT` to this skill's `scripts/freesearchx.py` (skill install dir).
Examples below use `$SCRIPT`.

## Decision tree

```text
Need information from the web?
├─ Know the exact URL / arXiv id  →  --read URL
├─ Check if a citation is real    →  --verify "title or ref"
├─ Need images                    →  "query" --images
└─ Need to discover sources
   ├─ Browse list first (default) →  "query"  [then --read top picks]
   ├─ Academic / primary only     →  "query" --academic
   └─ Already sure top hits matter →  "query" --deep [--deep-n 3]
```

**Default is two-phase on purpose:** search returns ranked titles + snippets
(cheap); `--read` pulls full text only for the URLs you select (expensive).
Use `--deep` only when you want top-K bodies in one shot.

## Commands

```bash
# 1) Discover (dynamic 5–20, source-tagged)
python "$SCRIPT" "python asyncio tutorial"
python "$SCRIPT" "attention mechanism survey" --academic -n 10
python "$SCRIPT" "query" --json          # structured for parsing

# 2) Deep-read selected hits
python "$SCRIPT" --read "https://arxiv.org/abs/1706.03762"
python "$SCRIPT" --read "https://docs.python.org/3/library/asyncio.html"

# 1+2 in one call (top 3 bodies by default)
python "$SCRIPT" "fastapi middleware order" --deep
python "$SCRIPT" "query" --deep --deep-n 5 --json

# Citation check (||| separates multiple refs)
python "$SCRIPT" --verify "Attention Is All You Need"
python "$SCRIPT" --verify "ref one|||ref two" --json

# Images / cache
python "$SCRIPT" "sql join types diagram" --images -n 5
python "$SCRIPT" --cache-info
python "$SCRIPT" --clear-cache
python "$SCRIPT" "query" --no-cache
```
If `pip install -e .` was used, `freesearchx ...` is equivalent to
`python "$SCRIPT" ...`.

## How to use results

1. **Read every search hit** (not only the first). Tags mean:
   - `[paper]` arXiv etc. · `[primary]` venues · `[code]` GitHub/HF
   - `[docs]` · `[blog]` · `[aggregator]` · `[other]`
2. **Then** `--read` the 1–3 most relevant URLs (or use `--deep` up front).
3. For papers, prefer arXiv / venue links over aggregator reposts.
4. On `--verify`: act on `VERIFIED` only when confidence is high; treat
   `UNSURE` / `NOT_FOUND` as **confirm manually** — never silently cite them.
5. Prefer `--json` when you will parse output programmatically.

## Failure handling

- Retries 3× and prints the exception type. Still failing → set `HTTPS_PROXY`
  and retry, or wait out DuckDuckGo rate limits.
- Image search is more fragile than text search in some regions (proxy helps).
- TLS is verified by default. Only set `FRESEARCHX_INSECURE=1` as a last resort.
- HuggingFace host rewrite is **off** unless `FRESEARCHX_HF_MIRROR` /
  `HF_ENDPOINT` is set.

## Progressive disclosure

| Need | Open |
|------|------|
| Full CLI flags & env vars | [references/cli.md](references/cli.md) |
| Why search≠fetch, deep mode, academic tips | [references/workflow.md](references/workflow.md) |
| Script behavior / debugging | run `python "$SCRIPT" --help`; read `scripts/freesearchx.py` only if needed |

## Dependencies

`ddgs`, `trafilatura`, `requests` (see `requirements.txt` / `pyproject.toml`).
