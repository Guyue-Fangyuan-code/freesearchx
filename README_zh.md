# FreeSearchX

**[English](README.md) | 中文**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![CI](https://img.shields.io/github/actions/workflow/status/Guyue-Fangyuan-code/freesearchx/ci.yml?branch=main&label=CI)](https://github.com/Guyue-Fangyuan-code/freesearchx/actions)

免费的命令行 / AI 助手联网搜索、网页抓取与引用核实。无需 API key，无需注册。

```text
$ freesearchx "python asyncio 教程"

[1] [docs]  asyncio — Asynchronous I/O — Python 文档
    https://docs.python.org/zh-cn/3/library/asyncio.html
    asyncio 是用来编写并发代码的库，使用 async/await 语法...

[2] [code]  python/cpython
    https://github.com/python/cpython
    The Python programming language...

7 results (relevance-ranked). Fetch any with: freesearchx --read 'URL'
```

## 它能做什么

- 通过 DuckDuckGo 搜索；结果会排序，并打上来源标签：paper / primary / code / docs / blog / aggregator / other。
- 抓取网页，或通过官方 API 读取 arXiv 摘要。
- 可选 deep：搜索后直接抓取前几条正文。
- 检查引用标题是否像真实文献（`--verify`）。
- 提供 JSON 输出，方便脚本和 Agent。
- 可作为 Claude Code skill，也可当普通 CLI。

默认是先搜索、再按需 `--read`。需要一次拿前几条正文时用 `--deep`。

## 环境要求

- Python 3.9+
- 可访问外网（必要时自行配置代理）

## 安装

```bash
git clone https://github.com/Guyue-Fangyuan-code/freesearchx.git
cd freesearchx
pip install -r requirements.txt
pip install -e .
freesearchx -V
```

不装入口命令时：

```bash
pip install -r requirements.txt
python scripts/freesearchx.py "查询"
```

### Claude Code skill

Claude Code 会从用户级 skills 目录加载个人 skill。把**整个仓库**克隆或复制到该目录下的 `freesearchx` 文件夹：

```bash
# macOS / Linux
git clone https://github.com/Guyue-Fangyuan-code/freesearchx.git ~/.claude/skills/freesearchx

# Windows（PowerShell）
git clone https://github.com/Guyue-Fangyuan-code/freesearchx.git "$env:USERPROFILE\.claude\skills\freesearchx"
```

对应路径：

| | 路径 |
|--|------|
| macOS / Linux | `~/.claude/skills/freesearchx` |
| Windows | `%USERPROFILE%\.claude\skills\freesearchx` |

如果只要**当前项目**可用，放到项目里：

```text
<你的项目>/.claude/skills/freesearchx
```

然后装一次依赖：

```bash
pip install -r ~/.claude/skills/freesearchx/requirements.txt
```

入口文件是 `SKILL.md`，脚本是 `scripts/freesearchx.py`。

## 用法

```bash
# 搜索（按相关度动态返回 5–20 条）
freesearchx "rust 异步运行时 对比"

# 指定条数，偏学术来源
freesearchx "attention mechanism survey" --academic -n 8

# 抓取单个 URL（arXiv 走官方 API）
freesearchx --read https://arxiv.org/abs/1706.03762

# 搜索并抓取前 3 条正文
freesearchx "fastapi 中间件 顺序" --deep --deep-n 3

# 引用核实
freesearchx --verify "Attention Is All You Need"

# JSON
freesearchx "kubernetes ingress controller" -n 10 --json

# 图片 / 缓存
freesearchx "sql join 示意图" --images -n 5
freesearchx --cache-info
freesearchx --clear-cache
```

## 环境变量

| 变量 | 含义 |
|------|------|
| `HTTPS_PROXY` / `HTTP_PROXY` | 出站代理 |
| `FRESEARCHX_CACHE_DIR` | 缓存目录（默认 skill 下 `cache/` 或用户缓存） |
| `FRESEARCHX_HF_MIRROR` / `HF_ENDPOINT` | 可选 HuggingFace 主机改写（默认关闭） |
| `FRESEARCHX_INSECURE=1` | 关闭 TLS 校验 |

## 作为库

```python
import freesearchx as fs

fs.search("python asyncio 教程", n=5)
fs.fetch("https://docs.python.org/3/library/asyncio.html")
fs.verify("Attention Is All You Need")
```

## 说明

- DuckDuckGo 可能限流；工具会重试几次，仍失败会打印错误。
- `--verify` 只是初筛，标 `UNSURE` 的请自己再确认。
- 与 DuckDuckGo、arXiv 无隶属关系。
- 如果这个项目对您有所帮助的话，欢迎点个 star。

## 开发

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

## 许可证

MIT，见 [LICENSE](LICENSE)。
