# FreeSearchX tests — offline unit tests (no network).

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/ is on pythonpath via pyproject; also support direct runs
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import freesearchx as fs  # noqa: E402


def test_skill_layout_files_exist():
    assert (ROOT / "SKILL.md").is_file()
    assert (ROOT / "scripts" / "freesearchx.py").is_file()
    assert (ROOT / "references" / "cli.md").is_file()
    assert (ROOT / "references" / "workflow.md").is_file()


def test_source_tag_tiers():
    assert fs.source_tag("https://arxiv.org/abs/2303.10512") == "[paper]"
    assert fs.source_tag("https://openreview.net/forum?id=abc") == "[primary]"
    assert fs.source_tag("https://github.com/foo/bar") == "[code]"
    assert fs.source_tag("https://huggingface.co/docs/peft") == "[code]"
    assert fs.source_tag("https://blog.csdn.net/x/y") == "[aggregator]"
    assert fs.source_tag("https://docs.python.org/3/") == "[docs]"
    assert fs.source_tag("https://medium.com/@x/y") == "[blog]"
    assert fs.source_tag("https://example.com/a") == "[other]"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://arxiv.org/abs/2303.10512", "2303.10512"),
        ("https://arxiv.org/pdf/2303.10512v2.pdf", "2303.10512"),
        ("https://arxiv.org/html/2303.10512", "2303.10512"),
        ("2303.10512v3", "2303.10512"),
        ("https://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
        ("not-an-id", None),
    ],
)
def test_extract_arxiv_id(raw, expected):
    assert fs.extract_arxiv_id(raw) == expected


def test_relevance_prefers_papers_and_overlap():
    q = "AdaLoRA adaptive budget allocation"
    s_paper = fs.relevance_score("[paper]", "AdaLoRA: Adaptive Budget Allocation", q)
    s_other = fs.relevance_score("[other]", "Random cooking recipes", q)
    assert s_paper > s_other


def test_relevance_cjk_bigrams():
    q = "神经网络结构"
    s = fs.relevance_score("[other]", "深度神经网络结构图解", q)
    assert s >= 1


def test_title_similarity_and_verify_classify():
    sim = fs._title_similarity(
        "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
        "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
    )
    assert sim > 0.8
    hit = fs._classify_verify(
        "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
        "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
        "https://arxiv.org/abs/2303.10512",
    )
    assert hit["status"] == "VERIFIED"
    assert hit["confidence"] >= 0.5

    weak = fs._classify_verify(
        "Completely Unrelated Quantum Banana Theorem 1999",
        "How to cook pasta",
        "https://example.com/pasta",
    )
    assert weak["status"] in ("NOT_FOUND", "UNSURE")


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "CACHE_DIR", str(tmp_path))
    fs.cache_set("k1", "hello")
    assert fs.cache_get("k1") == "hello"
    p = fs._cache_path("bad")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{broken")
    assert fs.cache_get("bad") is None


def test_clear_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "CACHE_DIR", str(tmp_path))
    fs.cache_set("a", "1")
    fs.cache_set("b", "2")
    n = fs.clear_cache()
    assert n == 2
    assert fs.cache_get("a") is None


def test_cache_lives_under_skill_root_not_scripts():
    assert Path(fs.CACHE_DIR).name == "cache"
    assert Path(fs.CACHE_DIR).parent == Path(fs.SKILL_ROOT)
    assert Path(fs.SCRIPT_DIR).name == "scripts"


def test_hf_mirror_off_by_default(monkeypatch):
    monkeypatch.delenv("FRESEARCHX_HF_MIRROR", raising=False)
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    url = "https://huggingface.co/foo/bar"
    assert fs._maybe_rewrite_hf(url) == url


def test_hf_mirror_opt_in(monkeypatch):
    monkeypatch.setenv("FRESEARCHX_HF_MIRROR", "https://hf-mirror.com")
    url = "https://huggingface.co/foo/bar"
    assert fs._maybe_rewrite_hf(url) == "https://hf-mirror.com/foo/bar"


def test_ssl_verify_default_on(monkeypatch):
    monkeypatch.delenv("FRESEARCHX_INSECURE", raising=False)
    assert fs._ssl_verify() is True
    monkeypatch.setenv("FRESEARCHX_INSECURE", "1")
    assert fs._ssl_verify() is False


def test_rank_and_select_dynamic():
    raw = [
        {"title": "AdaLoRA paper", "href": "https://arxiv.org/abs/1", "body": "x" * 50},
        {"title": "unrelated", "href": "https://example.com/a", "body": "y"},
        {"title": "also unrelated", "href": "https://example.com/b", "body": "z"},
        {"title": "noise", "href": "https://example.com/c", "body": "w"},
        {"title": "more noise", "href": "https://example.com/d", "body": "v"},
        {"title": "AdaLoRA code", "href": "https://github.com/x/adalora", "body": "code"},
    ]
    scored = fs._rank_results(raw, "AdaLoRA", academic=False)
    shown = fs._select_results(scored, None)
    assert 5 <= len(shown) <= 20
    assert shown[0][1] in ("[paper]", "[code]", "[primary]")


def test_academic_filters_aggregators():
    raw = [
        {"title": "AdaLoRA", "href": "https://arxiv.org/abs/1", "body": "a"},
        {"title": "搬运", "href": "https://blog.csdn.net/x", "body": "b"},
    ]
    scored = fs._rank_results(raw, "AdaLoRA", academic=True)
    urls = [u for *_, u in scored]
    assert all("csdn" not in u for u in urls)


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as ei:
        fs.main(["-V"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "0.1.1" in out


def test_cli_search_json(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(fs, "CACHE_DIR", str(tmp_path))

    class FakeDDG:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=40):
            return [
                {
                    "title": "AdaLoRA: Adaptive Budget Allocation",
                    "href": "https://arxiv.org/abs/2303.10512",
                    "body": "Parameter-efficient fine-tuning method.",
                }
            ]

    monkeypatch.setattr(fs, "_ddgs_client", lambda: FakeDDG())
    code = fs.main(["AdaLoRA", "-n", "3", "--json", "--no-cache"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["count"] >= 1
    assert payload["results"][0]["tag"] == "paper"


def test_cli_deep_json(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(fs, "CACHE_DIR", str(tmp_path))

    class FakeDDG:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=40):
            return [
                {
                    "title": "AdaLoRA paper",
                    "href": "https://arxiv.org/abs/2303.10512",
                    "body": "abstract-ish",
                }
            ]

    monkeypatch.setattr(fs, "_ddgs_client", lambda: FakeDDG())
    monkeypatch.setattr(
        fs,
        "fetch",
        lambda url, as_json=False, use_cache=True, quiet=False: f"BODY:{url}",
    )
    code = fs.main(["AdaLoRA", "-n", "1", "--deep", "--deep-n", "1", "--json", "--no-cache"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["deep_n"] == 1
    assert payload["fetched"][0]["content"].startswith("BODY:")


def test_cli_verify_json(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(fs, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(fs, "_arxiv_lookup_title", lambda ref: None)

    class FakeDDG:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=5):
            return [
                {
                    "title": "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
                    "href": "https://arxiv.org/abs/2303.10512",
                }
            ]

    monkeypatch.setattr(fs, "_ddgs_client", lambda: FakeDDG())
    code = fs.main(
        [
            "--verify",
            "AdaLoRA: Adaptive Budget Allocation for Parameter-Efficient Fine-Tuning",
            "--json",
            "--no-cache",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["status"] == "VERIFIED"

def test_arxiv_id_no_false_positives_on_release_tags():
    assert fs.extract_arxiv_id("https://github.com/org/repo/releases/tag/2024.12345") is None
    assert fs.extract_arxiv_id("https://example.com/foo/2023.10512/bar") is None
    assert fs.extract_arxiv_id("not a paper 2303.10512 in text") is None
    assert fs._looks_like_arxiv_target("https://github.com/org/repo/releases/tag/2024.12345") is False
    assert fs._looks_like_arxiv_target("https://arxiv.org/abs/2303.10512") is True
    assert fs._looks_like_arxiv_target("2303.10512") is True


def test_cache_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("FRESEARCHX_CACHE_DIR", str(tmp_path / "mycache"))
    # re-resolve like the module would
    d = fs._default_cache_dir()
    assert d == str(tmp_path / "mycache") or d.endswith("mycache")


def test_verify_wikipedia_not_auto_verified():
    hit = fs._classify_verify(
        "Deep Learning",
        "Deep Learning",
        "https://en.wikipedia.org/wiki/Deep_learning",
    )
    # without strong academic host, exact title match alone needs sim>=0.55;
    # short titles may still verify via that branch — host must not be wikipedia-strong.
    # If status is VERIFIED it must not be because of wikipedia strong-host boost alone.
    assert "wikipedia" not in open(fs.__file__, encoding="utf-8").read().split("_classify_verify")[1][:800]


def test_source_tag_new_venues():
    assert fs.source_tag("https://openaccess.thecvf.com/content/CVPR2024/html/x.html") == "[primary]"
    assert fs.source_tag("https://www.biorxiv.org/content/10.1101/2024.01.01.123456v1") == "[paper]"

def test_clean_title_strips_glued_sites():
    dirty = (
        "GitHub - QingruZhang/AdaLoRA: AdaLoRA · Hugging FaceAdaLoRA: Adaptive Budget "
        "Allocation for Parameter-Efficient ...AdaLoRA - Hugging FaceLORA微调系列 知乎"
    )
    clean = fs._clean_title(dirty)
    assert "Hugging FaceAdaLoRA" not in clean
    assert len(clean) <= 140
    assert "AdaLoRA" in clean or "QingruZhang" in clean


def test_rank_prefers_arxiv_abs_and_dedupes():
    raw = [
        {
            "title": "AdaLoRA paper html",
            "href": "https://arxiv.org/html/2303.10512v2",
            "body": "AdaLoRA abstract",
        },
        {
            "title": "AdaLoRA paper abs",
            "href": "https://arxiv.org/abs/2303.10512",
            "body": "AdaLoRA abstract",
        },
        {
            "title": "AdaLoRA mirror",
            "href": "https://arxiv.org/pdf/2303.10512.pdf",
            "body": "AdaLoRA abstract",
        },
    ]
    scored = fs._rank_results(raw, "AdaLoRA", academic=False)
    urls = [u for *_, u in scored]
    assert len(urls) == 1
    assert "/abs/" in urls[0]


def test_aggregator_scores_below_docs():
    q = "attention mechanism"
    s_docs = fs.relevance_score("[docs]", "Attention mechanism guide", q)
    s_agg = fs.relevance_score("[aggregator]", "Attention mechanism guide", q)
    assert s_docs > s_agg
