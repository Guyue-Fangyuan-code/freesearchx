#!/usr/bin/env python3
"""
FreeSearchX — DuckDuckGo search, page fetch, arXiv abstracts, citation check.

    freesearchx "query" [-n N] [--academic] [--deep] [--json]
    freesearchx --read URL
    freesearchx --verify "ref1|||ref2"
    freesearchx --images "query"
    freesearchx --clear-cache | --cache-info

Proxy: HTTPS_PROXY / HTTP_PROXY
HF mirror (opt-in): FRESEARCHX_HF_MIRROR
Cache: FRESEARCHX_CACHE_DIR
Deps: ddgs, trafilatura, requests
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
from typing import Any, Optional
from urllib.parse import urlparse

__version__ = "0.1.1"
__all__ = [
    "search",
    "deep_search",
    "images",
    "fetch",
    "verify",
    "source_tag",
    "relevance_score",
    "main",
    "__version__",
]

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)
CACHE_TTL = 7 * 86400


def _default_cache_dir() -> str:
    """FRESEARCHX_CACHE_DIR, else skill-root/cache if SKILL.md exists, else user cache."""
    env = (os.environ.get("FRESEARCHX_CACHE_DIR") or "").strip()
    if env:
        return os.path.expanduser(env)
    if os.path.isfile(os.path.join(SKILL_ROOT, "SKILL.md")):
        return os.path.join(SKILL_ROOT, "cache")
    xdg = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg:
        return os.path.join(xdg, "freesearchx")
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return os.path.join(local, "freesearchx", "cache")
    return os.path.join(os.path.expanduser("~"), ".cache", "freesearchx")


CACHE_DIR = _default_cache_dir()
USER_AGENT = (
    f"FreeSearchX/{__version__} (+https://github.com/Guyue-Fangyuan-code/freesearchx; research/CLI)"
)
REQUEST_TIMEOUT = 20
MAX_FETCH_CHARS = 8000
RETRY_ATTEMPTS = 3
RETRY_SLEEP = 1.5

PAPER_HOSTS = (
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "ssrn.com",
)
PRIMARY_HOSTS = (
    "aclanthology.org",
    "sciencedirect.com",
    "semanticscholar.org",
    "openreview.net",
    "proceedings.mlr.press",
    "ieeexplore.ieee.org",
    "dl.acm.org",
    "papers.nips.cc",
    "jmlr.org",
    "pmlr.cc",
    "nature.com",
    "science.org",
    "neurips.cc",
    "aaai.org",
    "aclweb.org",
    "thecvf.com",
    "openaccess.thecvf.com",
    "springer.com",
    "link.springer.com",
    "plos.org",
    "frontiersin.org",
    "wiley.com",
    "tandfonline.com",
    "cambridge.org",
    "oup.com",
    "siam.org",
    "jstor.org",
)
CODE_HOSTS = ("github.com", "gitlab.com", "huggingface.co", "bitbucket.org")
AGGREGATOR_HOSTS = (
    "csdn.net",
    "blog.csdn",
    "juejin.cn",
    "51cto.com",
    "segmentfault.com",
    "zhihu.com",
    "jianshu.com",
    "cnblogs.com",
)
BLOG_MARKERS = ("medium.com", "substack", "wordpress", ".blog", "dev.to", "hashnode")
DOCS_MARKERS = ("docs.", "/docs/", "documentation", "readthedocs.")

ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf|html)/(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?",
    re.I,
)
ARXIV_BARE_RE = re.compile(
    r"^(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?$",
    re.I,
)


def get_proxy() -> Optional[str]:
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
    )


def _ssl_verify() -> bool:
    """True unless FRESEARCHX_INSECURE is set."""
    return os.environ.get("FRESEARCHX_INSECURE", "").strip() not in ("1", "true", "yes")


def _hf_mirror_base() -> Optional[str]:
    """Optional HF host from FRESEARCHX_HF_MIRROR / HF_ENDPOINT."""
    for key in ("FRESEARCHX_HF_MIRROR", "HF_ENDPOINT"):
        val = (os.environ.get(key) or "").strip().rstrip("/")
        if val:
            return val
    return None


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def source_tag(url: str) -> str:
    u = (url or "").lower()
    host = _host(url)
    if any(h in host or h in u for h in PAPER_HOSTS) or "arxiv.org" in u:
        return "[paper]"
    if any(h in host or h in u for h in PRIMARY_HOSTS):
        return "[primary]"
    if any(h in host or h in u for h in CODE_HOSTS):
        return "[code]"
    if any(h in host or h in u for h in AGGREGATOR_HOSTS):
        return "[aggregator]"
    if any(m in u for m in DOCS_MARKERS):
        return "[docs]"
    if any(m in u for m in BLOG_MARKERS):
        return "[blog]"
    return "[other]"


def _tokenize(text: str) -> set[str]:
    text = (text or "").lower()
    tokens: set[str] = set()
    for w in re.split(r"\s+", text):
        w = w.strip(".,;:!?()[]{}\"'`")
        if len(w) > 1:
            tokens.add(w)
    cjk = re.findall(r"[一-鿿]", text)
    for i in range(len(cjk) - 1):
        tokens.add(cjk[i] + cjk[i + 1])
    if len(cjk) == 1:
        tokens.add(cjk[0])
    return tokens


def relevance_score(tag: str, title: str, query: str) -> int:
    s = 0
    if tag in ("[paper]", "[primary]"):
        s += 3
    elif tag in ("[docs]", "[code]"):
        s += 2
    elif tag == "[blog]":
        s += 1
    elif tag == "[aggregator]":
        s -= 1
    q = _tokenize(query)
    t = _tokenize(title)
    if q and t:
        s += min(3, len(q & t))
    return s


def _clean_title(title: str, max_len: int = 120) -> str:
    """Normalize SERP titles; drop glued multi-site garbage."""
    t = re.sub(r"\s+", " ", (title or "")).strip()
    if not t:
        return ""
    brands = (
        "GitHub",
        "Hugging Face",
        "arXiv",
        "Semantic Scholar",
        "Wikipedia",
        "Medium",
        "知乎",
        "CSDN",
        "博客园",
        "OpenReview",
        "YouTube",
    )
    for b in brands:
        t = re.sub(re.escape(b) + r"(?=[A-Za-z一-鿿])", b + " | ", t)
    for sep in (" | ", " · ", " • ", " – ", " — "):
        if sep in t:
            parts = [x.strip() for x in t.split(sep) if x.strip()]
            if parts:
                t = parts[0]
                break
    t = re.sub(r"\.{2,}[A-Za-z一-鿿].*$", "...", t)
    if t.endswith("..."):
        t = t[:-3].rstrip()
    if t.lower().startswith("github - ") and ": " in t:
        left = t.split(": ", 1)[0].strip()
        if len(left) >= 12:
            t = left
    if len(t) > max_len:
        t = t[: max_len - 1].rstrip() + "…"
    return t


def _url_quality_bonus(url: str) -> int:
    """Prefer canonical arXiv abs pages over html/pdf mirrors."""
    u = (url or "").lower()
    if "arxiv.org/abs/" in u:
        return 2
    if "arxiv.org/pdf/" in u:
        return 1
    if "arxiv.org/html/" in u:
        return 0
    return 0


def _result_key(url: str) -> str:
    """Dedupe key: collapse all arXiv variants of the same paper."""
    aid = extract_arxiv_id(url)
    if aid:
        return "arxiv:" + aid.lower()
    return (url or "").split("#", 1)[0].rstrip("/").lower()


def extract_arxiv_id(url_or_id: str) -> Optional[str]:
    """Canonical arXiv id, or None. URL path or bare id only."""
    s = (url_or_id or "").strip()
    if not s:
        return None
    m = ARXIV_URL_RE.search(s)
    if m:
        return m.group("id")
    m = ARXIV_BARE_RE.match(s)
    if m:
        return m.group("id")
    return None


def _looks_like_arxiv_target(url_or_id: str) -> bool:
    s = (url_or_id or "").strip()
    if not s:
        return False
    if "arxiv.org" in s.lower():
        return extract_arxiv_id(s) is not None
    return ARXIV_BARE_RE.match(s) is not None


def _emit_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _format_error(action: str, err: BaseException) -> str:
    return f"{action} failed: {type(err).__name__}: {err}"


def _cache_path(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".json")


def cache_get(key: str) -> Optional[str]:
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data["time"]) < CACHE_TTL:
            return data["content"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return None


def cache_set(key: str, content: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(key)
    payload = {"time": time.time(), "content": content}
    try:
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass


def clear_cache(*, quiet: bool = False) -> int:
    n = 0
    if os.path.isdir(CACHE_DIR):
        for name in os.listdir(CACHE_DIR):
            if name.endswith(".json"):
                try:
                    os.remove(os.path.join(CACHE_DIR, name))
                    n += 1
                except OSError:
                    pass
    if not quiet:
        print(f"Cleared {n} cache entries.")
    return n


def cache_info() -> None:
    if not os.path.isdir(CACHE_DIR):
        print(f"Cache: empty at {CACHE_DIR}")
        return
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
    size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    print(f"Cache: {len(files)} entries, {size / 1024:.0f} KB at {CACHE_DIR}")


def _ddgs_client():
    from ddgs import DDGS

    proxy = get_proxy()
    kwargs = {"proxy": proxy} if proxy else {}
    return DDGS(**kwargs)


def _with_retries(action: str, fn, attempts: int = RETRY_ATTEMPTS):
    last_err: Optional[BaseException] = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:  # network / backend flakes
            last_err = e
            if attempt < attempts - 1:
                print(
                    f"  attempt {attempt + 1} failed ({type(e).__name__}: {e}); "
                    f"retrying in {RETRY_SLEEP}s..."
                )
                time.sleep(RETRY_SLEEP)
    raise RuntimeError(_format_error(action, last_err or RuntimeError("unknown")))

def _http_get(url: str, timeout: int = REQUEST_TIMEOUT):
    import requests

    proxies = None
    proxy = get_proxy()
    if proxy:
        proxies = {"http": proxy, "https": proxy}
    return requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        verify=_ssl_verify(),
        proxies=proxies,
    )


def fetch_arxiv(url_or_id: str) -> Optional[str]:
    aid = extract_arxiv_id(url_or_id)
    if not aid:
        return None
    api = f"https://export.arxiv.org/api/query?id_list={aid}"
    try:
        resp = _http_get(api)
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        return f"(arXiv API failed: {type(e).__name__}: {e})"

    titles = re.findall(r"<title[^>]*>(.*?)</title>", text, re.S)
    title = re.sub(r"\s+", " ", titles[1].strip()) if len(titles) > 1 else ""
    summ = re.search(r"<summary>(.*?)</summary>", text, re.S)
    summary = re.sub(r"\s+", " ", summ.group(1).strip()) if summ else ""
    pub = re.search(r"<published>(.*?)</published>", text)
    published = pub.group(1)[:10] if pub else ""
    authors = re.findall(r"<name>(.*?)</name>", text)
    return (
        f"[arXiv:{aid}] {title}\n"
        f"Authors: {', '.join(authors[:8])}\n"
        f"Published: {published}\n\n"
        f"Abstract:\n{summary}"
    )


def _arxiv_lookup_title(title_query: str) -> Optional[dict]:
    from urllib.parse import quote

    q = quote(f'ti:"{title_query[:120]}"')
    api = f"https://export.arxiv.org/api/query?search_query={q}&start=0&max_results=3"
    try:
        resp = _http_get(api)
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return None

    entries = re.findall(r"<entry>(.*?)</entry>", text, re.S)
    if not entries:
        q = quote(f"all:{title_query[:80]}")
        api = f"https://export.arxiv.org/api/query?search_query={q}&start=0&max_results=3"
        try:
            resp = _http_get(api)
            resp.raise_for_status()
            text = resp.text
            entries = re.findall(r"<entry>(.*?)</entry>", text, re.S)
        except Exception:
            return None
    if not entries:
        return None

    entry = entries[0]
    t = re.search(r"<title[^>]*>(.*?)</title>", entry, re.S)
    title = re.sub(r"\s+", " ", t.group(1).strip()) if t else ""
    i = re.search(r"<id>(.*?)</id>", entry)
    url = i.group(1).strip() if i else ""
    return {"title": title, "url": url}


def _rank_results(raw: list[dict], query: str, academic: bool) -> list[tuple]:
    best: dict[str, tuple] = {}
    for r in raw:
        url = r.get("href") or r.get("url") or ""
        if not url:
            continue
        tag = source_tag(url)
        if academic and tag in ("[aggregator]", "[blog]", "[other]"):
            continue
        title = _clean_title(r.get("title") or "")
        body = (r.get("body") or "")[:200]
        sc = relevance_score(tag, title, query) + _url_quality_bonus(url)
        item = (sc, tag, {"title": title, "body": body, "href": url}, url)
        key = _result_key(url)
        prev = best.get(key)
        if prev is None or item[0] > prev[0] or (
            item[0] == prev[0] and _url_quality_bonus(url) > _url_quality_bonus(prev[3])
        ):
            best[key] = item
    scored = list(best.values())
    scored.sort(key=lambda x: (x[0], _url_quality_bonus(x[3])), reverse=True)
    return scored


def _select_results(scored: list[tuple], n: Optional[int]) -> list[tuple]:
    if n is not None:
        return scored[: max(0, n)]
    kept: list[tuple] = []
    for sc, tag, r, url in scored:
        if len(kept) >= 20:
            break
        if sc <= 1 and len(kept) >= 5:
            break
        kept.append((sc, tag, r, url))
    return kept


def _result_records(shown: list[tuple]) -> list[dict]:
    out = []
    for i, (sc, tag, r, url) in enumerate(shown, 1):
        out.append(
            {
                "rank": i,
                "tag": tag.strip("[]"),
                "title": _clean_title(r.get("title") or "", max_len=100),
                "url": url,
                "snippet": (r.get("body") or "")[:200],
                "score": sc,
            }
        )
    return out


class SearchError(RuntimeError):
    pass


def _search_records(
    query: str,
    n: Optional[int] = None,
    academic: bool = False,
    use_cache: bool = True,
) -> list[dict]:
    """Structured search hits; raises SearchError after failed retries."""
    ckey = f"search|v3|{query}|{n}|{academic}"
    if use_cache:
        cached = cache_get(ckey)
        if cached is not None:
            try:
                payload = json.loads(cached)
                if isinstance(payload, dict) and "results" in payload:
                    return payload["results"]
            except json.JSONDecodeError:
                pass

    def _do():
        with _ddgs_client() as ddg:
            return list(ddg.text(query, max_results=40))

    try:
        raw = _with_retries("Search", _do)
    except RuntimeError as e:
        raise SearchError(str(e)) from e

    scored = _rank_results(raw, query, academic)
    shown = _select_results(scored, n)
    records = _result_records(shown)
    if use_cache:
        cache_set(
            ckey,
            json.dumps(
                {
                    "ok": True,
                    "query": query,
                    "mode": "dynamic" if n is None else f"top-{n}",
                    "academic": academic,
                    "count": len(records),
                    "results": records,
                },
                ensure_ascii=False,
            ),
        )
    return records

def search(
    query: str,
    n: Optional[int] = None,
    academic: bool = False,
    as_json: bool = False,
    use_cache: bool = True,
) -> Optional[list[dict]]:
    dynamic = n is None
    mode = "dynamic" if dynamic else f"top-{n}"
    proxy = get_proxy()
    label = (" [academic]" if academic else "") + (" (proxy)" if proxy else " (direct)")

    try:
        records = _search_records(query, n=n, academic=academic, use_cache=use_cache)
    except SearchError as e:
        hint = (
            "Set HTTPS_PROXY if behind a firewall, or retry later "
            "(DuckDuckGo rate-limits occasionally)."
        )
        if as_json:
            _emit_json({"ok": False, "error": str(e), "query": query, "hint": hint})
        else:
            print(f"{e}\nHint: {hint}")
        return None

    if as_json:
        payload = {
            "ok": True,
            "query": query,
            "mode": mode,
            "academic": academic,
            "count": len(records),
            "results": records,
        }
        _emit_json(payload)
        return records

    print(f"Search: {query}{label} [{mode}]")
    print("=" * 60)
    for rec in records:
        print()
        print(f"[{rec['rank']}] [{rec['tag']}] {rec['title']}")
        print(f"    {rec['url']}")
        print(f"    {rec['snippet']}")
    print()
    print(
        f"{len(records)} results (relevance-ranked). "
        "Fetch any with: freesearchx --read 'URL' "
        "(or re-run with --deep to auto-fetch top hits)"
    )
    return records


def deep_search(
    query: str,
    n: Optional[int] = None,
    academic: bool = False,
    deep_n: int = 3,
    as_json: bool = False,
    use_cache: bool = True,
) -> Optional[dict]:
    """Search then fetch bodies for the top deep_n hits."""
    deep_n = max(0, int(deep_n))
    try:
        records = _search_records(query, n=n, academic=academic, use_cache=use_cache)
    except SearchError as e:
        if as_json:
            _emit_json({"ok": False, "error": str(e), "query": query})
        else:
            print(f"Deep search failed: {e}")
        return None

    fetched = []
    for rec in records[:deep_n]:
        url = rec.get("url") or ""
        body = (
            fetch(url, as_json=False, use_cache=use_cache, quiet=True) if url else None
        )
        fetched.append({**rec, "content": body or "", "fetch_ok": bool(body)})

    payload = {
        "ok": True,
        "query": query,
        "academic": academic,
        "count": len(records),
        "deep_n": deep_n,
        "results": records,
        "fetched": fetched,
    }

    if as_json:
        _emit_json(payload)
        return payload

    proxy = get_proxy()
    label = (" [academic]" if academic else "") + (" (proxy)" if proxy else " (direct)")
    print(f"Deep search: {query}{label} [top-{deep_n} fetched]")
    print("=" * 60)
    for rec in records:
        print()
        print(f"[{rec['rank']}] [{rec['tag']}] {rec['title']}")
        print(f"    {rec['url']}")
        print(f"    {rec['snippet']}")
    print()
    print("-" * 60)
    print(f"Fetched full content for top {len(fetched)}:")
    for item in fetched:
        print()
        print(f"### [{item['rank']}] {item['title']}")
        print(item["url"])
        print()
        content = item.get("content") or "(fetch failed)"
        if len(content) > 4000:
            print(content[:4000])
            print("...(truncated)")
        else:
            print(content)
    print()
    print(f"{len(records)} results, {len(fetched)} deep-fetched.")
    return payload


def images(
    query: str,
    n: int = 10,
    as_json: bool = False,
    use_cache: bool = True,
) -> Optional[list[dict]]:
    ckey = f"images|v3|{query}|{n}"
    if use_cache:
        cached = cache_get(ckey)
        if cached is not None:
            if as_json:
                try:
                    payload = json.loads(cached)
                    _emit_json(payload)
                    return payload.get("results")
                except json.JSONDecodeError:
                    pass
            else:
                print(f"Images (cached): {query}\n{'=' * 60}")
                print(cached)
                return None

    proxy = get_proxy()

    def _do():
        with _ddgs_client() as ddg:
            return list(ddg.images(query, max_results=n))

    try:
        raw = _with_retries("Image search", _do)
    except RuntimeError as e:
        if as_json:
            _emit_json({"ok": False, "error": str(e), "query": query})
        else:
            print(
                f"{e}\n"
                "Hint: image search often needs HTTPS_PROXY in restricted regions."
            )
        return None

    records = []
    for i, r in enumerate(raw, 1):
        records.append(
            {
                "rank": i,
                "title": r.get("title") or "",
                "image": r.get("image") or r.get("url") or "",
                "thumbnail": r.get("thumbnail") or "",
                "source": r.get("url") or r.get("source") or "",
            }
        )

    if as_json:
        payload = {"ok": True, "query": query, "count": len(records), "results": records}
        _emit_json(payload)
        if use_cache and records:
            cache_set(ckey, json.dumps(payload, ensure_ascii=False))
        return records

    print(f"Images: {query}{' (proxy)' if proxy else ' (direct)'}\n{'=' * 60}")
    lines: list[str] = []
    for rec in records:
        line = (
            f"\n[{rec['rank']}] {rec['title']}\n"
            f"    image:   {rec['image']}\n"
            f"    thumb:   {rec['thumbnail']}"
        )
        print(line)
        lines.append(line)
    footer = f"\n{len(records)} images."
    print(footer)
    lines.append(footer)
    if use_cache and records:
        cache_set(ckey, "\n".join(lines))
    return records


def _maybe_rewrite_hf(url: str) -> str:
    mirror = _hf_mirror_base()
    if not mirror or "huggingface.co" not in url:
        return url
    return url.replace("https://huggingface.co", mirror).replace(
        "http://huggingface.co", mirror
    )


def fetch(url: str, as_json: bool = False, use_cache: bool = True, quiet: bool = False) -> Optional[str]:
    original = url
    rewritten = _maybe_rewrite_hf(url)
    if rewritten != url:
        if not quiet:
            print(f"  (HuggingFace mirror via env: {rewritten})")
        url = rewritten

    ckey = f"fetch|v2|{url}"
    if use_cache:
        cached = cache_get(ckey)
        if cached is not None:
            if as_json:
                _emit_json({"ok": True, "url": original, "cached": True, "content": cached})
            elif not quiet:
                print(f"Fetch (cached): {url}\n{'=' * 60}\n{cached}")
            return cached

    if _looks_like_arxiv_target(original):
        if not as_json and not quiet:
            print(f"Fetch (arXiv API): {original}\n{'=' * 60}")
        out = fetch_arxiv(original)
        if as_json:
            ok = bool(out) and not (out or "").startswith("(arXiv API failed")
            _emit_json(
                {
                    "ok": ok,
                    "url": original,
                    "source": "arxiv-api",
                    "content": out,
                }
            )
        else:
            if not quiet:
                print(out or "(nothing returned)")
        if out and not out.startswith("(arXiv API failed") and use_cache:
            cache_set(ckey, out)
        return out

    if not as_json and not quiet:
        print(f"Fetch: {url}\n{'=' * 60}")

    text_body: Optional[str] = None
    source = "trafilatura"
    html: Optional[str] = None
    try:
        resp = _http_get(url)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        msg = _format_error("Fetch", e)
        if as_json:
            _emit_json({"ok": False, "url": original, "error": msg})
        elif not quiet:
            print(msg)
        return None

    try:
        import trafilatura

        text_body = trafilatura.extract(html, favor_recall=True) if html else None
    except Exception as e:
        source = f"trafilatura-error:{type(e).__name__}"
        text_body = None

    if not text_body:
        source = "fallback-html"
        cleaned = re.sub(
            r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I
        )
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        text_body = cleaned

    if source == "fallback-html":
        body = text_body or ""
    else:
        lines = [ln.strip() for ln in (text_body or "").split("\n") if ln.strip()]
        lines = [
            ln
            for ln in lines
            if len(ln) > 10
            and not re.match(
                r"^(cookie|subscribe|sign in|login|register|ad)\b", ln, re.I
            )
        ]
        body = "\n".join(lines) if lines else (text_body or "")
    out = body[:MAX_FETCH_CHARS]
    truncated = len(body) > MAX_FETCH_CHARS

    if as_json:
        _emit_json(
            {
                "ok": True,
                "url": original,
                "source": source,
                "truncated": truncated,
                "content": out,
            }
        )
    elif not quiet:
        suffix = (
            f"\n\n...({len(body)} chars total, truncated to {MAX_FETCH_CHARS})"
            if truncated
            else ""
        )
        print(out + suffix)

    if use_cache and out:
        cache_set(ckey, out)
    return out


def _title_similarity(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _classify_verify(ref: str, match_title: str, match_url: str) -> dict:
    sim = _title_similarity(ref, match_title)
    host = _host(match_url)
    strong_host = any(
        h in host
        for h in (
            "arxiv.org",
            "doi.org",
            "semanticscholar.org",
            "aclanthology.org",
            "openreview.net",
            "ieee.org",
            "acm.org",
            "nature.com",
            "sciencedirect.com",
            "springer.com",
            "nih.gov",
            "biorxiv.org",
            "thecvf.com",
        )
    )
    if sim >= 0.45 and strong_host:
        status = "VERIFIED"
        confidence = round(min(0.95, 0.5 + sim / 2 + (0.15 if strong_host else 0)), 2)
    elif sim >= 0.55:
        status = "VERIFIED"
        confidence = round(min(0.9, 0.4 + sim / 2), 2)
    elif sim >= 0.25:
        status = "UNSURE"
        confidence = round(sim, 2)
    else:
        status = "NOT_FOUND"
        confidence = round(sim, 2)
    return {
        "status": status,
        "confidence": confidence,
        "similarity": round(sim, 3),
        "best_match_title": match_title,
        "best_match_url": match_url,
    }


def verify(
    refs_str: str,
    as_json: bool = False,
    use_cache: bool = True,
) -> list[dict]:
    refs = [r.strip() for r in refs_str.split("|||") if r.strip()]
    results: list[dict] = []

    if not as_json:
        print(f"Verifying {len(refs)} citation(s)\n{'=' * 60}")

    for i, ref in enumerate(refs, 1):
        ckey = f"verify|v2|{ref}"
        if use_cache:
            cached = cache_get(ckey)
            if cached:
                try:
                    item = json.loads(cached)
                    item["rank"] = i
                    item["ref"] = ref
                    results.append(item)
                    if not as_json:
                        print(
                            f"\n[{i}] {ref[:70]}\n"
                            f"  {item['status']} (confidence={item.get('confidence')}, cached)\n"
                            f"  best match: {item.get('best_match_title', '')}\n"
                            f"  {item.get('best_match_url', '')}"
                        )
                    continue
                except json.JSONDecodeError:
                    pass

        item: dict[str, Any] = {
            "rank": i,
            "ref": ref,
            "status": "SEARCH_FAILED",
            "confidence": 0.0,
            "similarity": 0.0,
            "best_match_title": "",
            "best_match_url": "",
            "note": "",
        }

        arx = _arxiv_lookup_title(ref)
        if arx and arx.get("title"):
            classified = _classify_verify(ref, arx["title"], arx.get("url") or "")
            if classified["status"] == "VERIFIED":
                classified["confidence"] = round(min(0.98, classified["confidence"] + 0.05), 2)
            item.update(classified)
            item["note"] = "via arXiv API"
        else:
            try:

                def _do():
                    with _ddgs_client() as ddg:
                        return list(ddg.text(ref, max_results=5))

                rs = _with_retries("Verify search", _do)
                if not rs:
                    item["status"] = "NOT_FOUND"
                    item["note"] = "no web hits (likely fabricated — confirm manually)"
                else:
                    best = None
                    best_sim = -1.0
                    for hit in rs:
                        t = hit.get("title") or ""
                        u = hit.get("href") or hit.get("url") or ""
                        sim = _title_similarity(ref, t)
                        if sim > best_sim:
                            best_sim = sim
                            best = (t, u)
                    if best:
                        item.update(_classify_verify(ref, best[0], best[1]))
                        if item["status"] == "NOT_FOUND":
                            item["note"] = "low title match — confirm manually"
                        elif item["status"] == "UNSURE":
                            item["note"] = "partial match — confirm manually"
                    else:
                        item["status"] = "NOT_FOUND"
            except RuntimeError as e:
                item["status"] = "SEARCH_FAILED"
                item["note"] = str(e)

        results.append(item)
        if use_cache and item["status"] != "SEARCH_FAILED":
            cache_set(
                ckey,
                json.dumps(
                    {
                        k: item[k]
                        for k in (
                            "status",
                            "confidence",
                            "similarity",
                            "best_match_title",
                            "best_match_url",
                            "note",
                        )
                    },
                    ensure_ascii=False,
                ),
            )

        if not as_json:
            print(
                f"\n[{i}] {ref[:70]}\n"
                f"  {item['status']} (confidence={item.get('confidence')}"
                f", similarity={item.get('similarity')})\n"
                f"  best match: {item.get('best_match_title', '')}\n"
                f"  {item.get('best_match_url', '')}"
                + (f"\n  note: {item['note']}" if item.get("note") else "")
            )

    if as_json:
        _emit_json({"ok": True, "count": len(results), "results": results})
    return results



def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="freesearchx",
        description=(
            "Free web search, image search, page fetch & citation verification "
            "(DuckDuckGo + arXiv). No API key required."
        ),
    )
    ap.add_argument(
        "query",
        nargs="?",
        help="search query (dynamic 5-20 results by default)",
    )
    ap.add_argument(
        "-n",
        type=int,
        default=None,
        help="fixed number of results (omit for dynamic 5-20 by relevance)",
    )
    ap.add_argument("--academic", action="store_true", help="primary / paper / code sources only")
    ap.add_argument("--images", action="store_true", help="image search")
    ap.add_argument(
        "--deep",
        action="store_true",
        help="after search, also fetch full content for the top hits (see --deep-n)",
    )
    ap.add_argument(
        "--deep-n",
        type=int,
        default=3,
        metavar="K",
        help="with --deep, how many top results to fetch (default: 3)",
    )
    ap.add_argument("--read", dest="fetch", metavar="URL", help="fetch one page/abstract")
    ap.add_argument(
        "--verify",
        dest="verify",
        metavar="REFS",
        help="verify citations (|||-separated)",
    )
    ap.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="machine-readable JSON output (for agents)",
    )
    ap.add_argument("--clear-cache", action="store_true", help="delete all cache entries")
    ap.add_argument("--cache-info", action="store_true", help="show cache size and path")
    ap.add_argument(
        "--no-cache",
        action="store_true",
        help="skip reading/writing the local cache",
    )
    ap.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"FreeSearchX {__version__}",
    )
    args = ap.parse_args(argv)
    use_cache = not args.no_cache

    if args.clear_cache:
        clear_cache()
        return 0
    if args.cache_info:
        cache_info()
        return 0
    if args.verify:
        verify(args.verify, as_json=args.as_json, use_cache=use_cache)
        return 0
    if args.fetch:
        out = fetch(args.fetch, as_json=args.as_json, use_cache=use_cache)
        return 0 if out else 1
    if args.query:
        if args.images:
            out = images(
                args.query,
                n=args.n or 10,
                as_json=args.as_json,
                use_cache=use_cache,
            )
            return 0 if out is not None else 1
        if args.deep:
            out = deep_search(
                args.query,
                n=args.n,
                academic=args.academic,
                deep_n=args.deep_n,
                as_json=args.as_json,
                use_cache=use_cache,
            )
            return 0 if out is not None else 1
        out = search(
            args.query,
            n=args.n,
            academic=args.academic,
            as_json=args.as_json,
            use_cache=use_cache,
        )
        return 0 if out is not None else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
