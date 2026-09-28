#!/usr/bin/env python3
"""根据 data/papers.jsonl 与 data/preprints.jsonl 生成 papers/INDEX.md 浏览索引。"""
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
PAPERS_JSONL = ROOT / "data" / "papers.jsonl"
PREPRINTS_JSONL = ROOT / "data" / "preprints.jsonl"
INDEX = ROOT / "papers" / "INDEX.md"

NAMES = {"lancet": "The Lancet（柳叶刀）",
         "nejm": "NEJM（新英格兰医学杂志）",
         "jama": "JAMA（美国医学会杂志）",
         "medrxiv": "medRxiv（预印本）",
         "biorxiv": "bioRxiv（预印本）"}


def load():
    papers = []
    if PAPERS_JSONL.exists():
        for line in PAPERS_JSONL.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            p["_section"] = p["journal_slug"]
            p["_link"] = f"{p['journal_slug']}/{p['month']}/{p['pmid']}.md"
            papers.append(p)
    if PREPRINTS_JSONL.exists():
        for line in PREPRINTS_JSONL.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            p["_section"] = p["server"]
            p["_link"] = f"preprints/{p['server']}/{p['month']}/{p['file']}"
            papers.append(p)
    return papers


def main():
    papers = load()
    papers.sort(key=lambda p: (p["_section"], p["date"]), reverse=True)
    grouped = defaultdict(lambda: defaultdict(list))
    for p in papers:
        grouped[p["_section"]][p["month"] or "undated"].append(p)

    n_journal = sum(1 for p in papers if not p.get("is_preprint"))
    n_pre = sum(1 for p in papers if p.get("is_preprint"))
    out = ["# 论文索引", "",
           f"共收录 {len(papers)} 篇（期刊 {n_journal} 篇 ＋ 预印本 {n_pre} 篇）", ""]
    for slug in ("lancet", "nejm", "jama", "medrxiv", "biorxiv"):
        months = grouped.get(slug, {})
        if not months:
            continue
        n = sum(len(v) for v in months.values())
        out += [f"## {NAMES[slug]}（{n} 篇）", ""]
        for month in sorted(months, reverse=True):
            out += [f"### {month}", ""]
            for p in months[month]:
                if p.get("is_preprint"):
                    tag = f"（{p.get('category', '')}）" if p.get("category") else ""
                    extra = " ⚠️预印本"
                else:
                    tags = " · ".join(p.get("concepts", [])[:3])
                    tag = f"（{tags}）" if tags else ""
                    extra = " 🆓" if p.get("is_oa") else ""
                out += [f"- [{p['title']}]({p['_link']})"
                        f" — {p['date']}{extra}{tag}"]
            out += [""]
    INDEX.write_text("\n".join(out), encoding="utf-8")
    print(f"INDEX.md 已生成，共 {len(papers)} 篇（期刊 {n_journal}，预印本 {n_pre}）")


if __name__ == "__main__":
    main()
