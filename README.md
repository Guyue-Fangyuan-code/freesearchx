# FreeSearchX

**English | [中文](README_zh.md)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![CI](https://img.shields.io/github/actions/workflow/status/Guyue-Fangyuan-code/freesearchx/ci.yml?branch=main&label=CI)](https://github.com/Guyue-Fangyuan-code/freesearchx/actions)

Free web search, page fetch, and citation checking for the terminal and AI coding tools. No API key, no signup.

```text
$ freesearchx "python asyncio tutorial" --academic

[1] [docs]  asyncio — Asynchronous I/O — Python documentation
    https://docs.python.org/3/library/asyncio.html
    asyncio is a library to write concurrent code using the async/await syntax...

[2] [code]  python/cpython
    https://github.com/python/cpython
    The Python programming language...

7 results (relevance-ranked). Fetch any with: freesearchx --read 'URL'
```

## What it can do

- Search the web via DuckDuckGo; results are ranked and tagged: paper, primary, code, docs, blog, aggregator, other.
- Fetch a page, or an arXiv abstract through the official API.
- Optional deep mode: search, then fetch the top few pages in one go.
- Check whether a citation title looks real (`--verify`).
- JSON output for scripts and agents.
- Works as a Claude Code skill or as a normal CLI.

Default flow is search first, then `--read` only what you need. Use `--deep` when you want top results fetched immediately.

## Requirements

- Python 3.9+
- Network access (and a proxy if your network needs one)

## Install

```bash
git clone https://github.com/Guyue-Fangyuan-code/freesearchx.git
cd freesearchx
pip install -r requirements.txt
pip install -e .
freesearchx -V
```

Without the entry point:

```bash
pip install -r requirements.txt
python scripts/freesearchx.py "query"
```

### Claude Code skill

Claude Code loads personal skills from your user skills directory. Clone or copy **this whole repository** into a folder named `freesearchx` under that directory:

```bash
# macOS / Linux
git clone https://github.com/Guyue-Fangyuan-code/freesearchx.git ~/.claude/skills/freesearchx

# Windows (PowerShell)
git clone https://github.com/Guyue-Fangyuan-code/freesearchx.git "$env:USERPROFILE\.claude\skills\freesearchx"
```

Equivalent paths:

| | Path |
|--|------|
| macOS / Linux | `~/.claude/skills/freesearchx` |
| Windows | `%USERPROFILE%\.claude\skills\freesearchx` |

For a **project-only** skill, put the same folder at:

```text
<your-project>/.claude/skills/freesearchx
```

Then install dependencies once:

```bash
pip install -r ~/.claude/skills/freesearchx/requirements.txt
```

The skill entry file is `SKILL.md`. The CLI script is `scripts/freesearchx.py`.

## Usage

```bash
# search (dynamic 5–20 results by relevance)
freesearchx "rust async runtime comparison"

# fixed count, academic-leaning sources only
freesearchx "attention mechanism survey" --academic -n 8

# fetch one URL (arXiv uses the official API)
freesearchx --read https://arxiv.org/abs/1706.03762

# search and fetch top 3 bodies
freesearchx "fastapi middleware order" --deep --deep-n 3

# citation check
freesearchx --verify "Attention Is All You Need"

# JSON
freesearchx "kubernetes ingress controller" -n 10 --json

# images / cache
freesearchx "sql join types diagram" --images -n 5
freesearchx --cache-info
freesearchx --clear-cache
```

## Environment

| Variable | Meaning |
|----------|---------|
| `HTTPS_PROXY` / `HTTP_PROXY` | Outbound proxy |
| `FRESEARCHX_CACHE_DIR` | Cache directory (default: skill `cache/` or user cache) |
| `FRESEARCHX_HF_MIRROR` / `HF_ENDPOINT` | Optional HuggingFace host rewrite (off by default) |
| `FRESEARCHX_INSECURE=1` | Disable TLS verification |

## Library

```python
import freesearchx as fs

fs.search("python asyncio tutorial", n=5, academic=True)
fs.fetch("https://docs.python.org/3/library/asyncio.html")
fs.verify("Attention Is All You Need")
```

## Notes

- DuckDuckGo may rate-limit; the tool retries a few times and prints the error if it still fails.
- `--verify` is a first pass. Confirm anything marked `UNSURE` yourself.
- Not affiliated with DuckDuckGo or arXiv.
- If this project helps you, a star is appreciated.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

```text
freesearchx/
├── SKILL.md
├── scripts/freesearchx.py
├── references/
├── tests/
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── .github/workflows/ci.yml
```

## License

MIT. See [LICENSE](LICENSE).
