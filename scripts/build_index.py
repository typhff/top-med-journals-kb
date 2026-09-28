#!/usr/bin/env python3
"""根据 data/papers.jsonl 生成 papers/INDEX.md 浏览索引。"""
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "papers.jsonl"
INDEX = ROOT / "papers" / "INDEX.md"

NAMES = {"lancet": "The Lancet（柳叶刀）",
         "nejm": "NEJM（新英格兰医学杂志）",
         "jama": "JAMA（美国医学会杂志）"}


def main():
    papers = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines()]
    papers.sort(key=lambda p: (p["journal_slug"], p["date"]), reverse=True)
    grouped = defaultdict(lambda: defaultdict(list))
    for p in papers:
        grouped[p["journal_slug"]][p["month"] or "undated"].append(p)

    out = ["# 论文索引", "",
           f"共收录 {len(papers)} 篇（Lancet / NEJM / JAMA 近期实质性文献）", ""]
    for slug in ("lancet", "nejm", "jama"):
        months = grouped.get(slug, {})
        n = sum(len(v) for v in months.values())
        out += [f"## {NAMES[slug]}（{n} 篇）", ""]
        for month in sorted(months, reverse=True):
            out += [f"### {month}", ""]
            for p in months[month]:
                tags = " · ".join(p.get("concepts", [])[:3])
                oa = " 🆓" if p.get("is_oa") else ""
                out += [f"- [{p['title']}]({slug}/{month}/{p['pmid']}.md)"
                        f" — {p['date']}{oa}" + (f"（{tags}）" if tags else "")]
            out += [""]
    INDEX.write_text("\n".join(out), encoding="utf-8")
    print(f"INDEX.md 已生成，共 {len(papers)} 篇")


if __name__ == "__main__":
    main()
