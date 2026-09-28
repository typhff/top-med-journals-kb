#!/usr/bin/env python3
"""
抓取 bioRxiv / medRxiv 预印本，写入知识库。

API: https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}
  server: biorxiv | medrxiv，游标分页（每页 30 条）

medRxiv 全部收录（均为临床相关）；bioRxiv 只收录与医学相邻的分类。

用法：
  python3 scripts/fetch_preprints.py [--days 92]
输出：
  papers/preprints/{server}/{YYYY-MM}/{doi_slug}.md
  data/preprints.jsonl
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PAPERS = ROOT / "papers" / "preprints"

# bioRxiv 只保留这些与医学相邻的分类
MED_CATEGORIES = {
    "biochemistry", "bioengineering", "bioinformatics", "biophysics",
    "cancer biology", "cell biology", "genetics", "genomics",
    "immunology", "microbiology", "molecular biology", "neuroscience",
    "pathology", "pharmacology and toxicology", "physiology",
    "systems biology",
}

UA = {"User-Agent": "top-med-journals-kb/1.0 (personal knowledge base)"}


def api_get(url, retries=3):
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2)
    raise RuntimeError(f"API 失败: {url} ({last})")


def fetch_server(server, start, end):
    """游标分页拉取全部记录，按 DOI 去重（保留最高版本）。"""
    seen, cursor, pages = {}, 0, 0
    while True:
        url = f"https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}"
        d = None
        for attempt in range(4):
            d = api_get(url)
            msgs = d.get("messages", [{}])[0]
            if msgs.get("status") == "ok":
                break
            # "no posts found" 在 cursor>0 时表示翻到底；cursor=0 时可能是瞬时限流，重试
            if msgs.get("status") == "no posts found" and cursor > 0:
                d = None
                break
            time.sleep(5 * (attempt + 1))
        if d is None:
            break
        msgs = d["messages"][0]
        if msgs.get("status") != "ok":
            raise RuntimeError(f"API 返回异常: {msgs}")
        batch = d.get("collection", [])
        if not batch:
            break
        for rec in batch:
            doi = (rec.get("doi") or "").lower()
            if not doi:
                continue
            ver = int(rec.get("version") or 1)
            if doi not in seen or ver > seen[doi]["_ver"]:
                rec["_ver"] = ver
                seen[doi] = rec
        cursor += len(batch)
        pages += 1
        if pages % 20 == 0:
            print(f"  {server}: 已拉取 {len(seen)} 篇（{pages} 页）…", flush=True)
        time.sleep(0.6)
    print(f"  {server}: 拉取 {len(seen)} 篇不重复预印本", flush=True)
    return list(seen.values())


def doi_slug(doi):
    return re.sub(r"[^a-z0-9.]+", "_", doi.lower()).strip("_")


def write_preprint(rec, server):
    doi = rec["doi"].lower()
    d = PAPERS / server / rec["date"][:7]
    d.mkdir(parents=True, exist_ok=True)
    authors = rec.get("authors", "")
    cat = rec.get("category", "")
    pub = rec.get("published", "")
    lines = ["---",
             json.dumps({"doi": doi, "server": server, "date": rec.get("date"),
                         "category": cat, "version": rec.get("version"),
                         "is_preprint": True}, ensure_ascii=False, indent=2),
             "---", "",
             f"# {rec.get('title', '').strip()}", "",
             "> ⚠️ 预印本：尚未经过同行评审，引用时请注意。", "",
             f"**来源**: {'medRxiv' if server == 'medrxiv' else 'bioRxiv'} · {rec.get('date')}",
             ""]
    if authors:
        lines += [f"**作者**: {authors}", ""]
    lines += [f"**DOI**: [{doi}](https://doi.org/{doi})",
              f"**版本**: v{rec.get('version')}", ""]
    if cat:
        lines += [f"**分类**: {cat}", ""]
    if pub and pub != "NA":
        lines += [f"**已发表于**: {pub}", ""]
    if rec.get("license"):
        lines += [f"**许可**: {rec['license']}", ""]
    lines += ["## 摘要", ""]
    lines += [(rec.get("abstract") or "").strip()
              or "_API 未返回摘要，请通过 DOI 查看。_", ""]
    (d / f"{doi_slug(doi)}.md").write_text("\n".join(lines), encoding="utf-8")
    return {
        "doi": doi, "title": rec.get("title", "").strip(),
        "authors": authors, "server": server, "date": rec.get("date"),
        "month": rec.get("date", "")[:7], "category": cat,
        "version": rec.get("version"), "abstract": rec.get("abstract", ""),
        "published": pub, "is_preprint": True,
        "file": f"{doi_slug(doi)}.md",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=92)
    ap.add_argument("--servers", default="medrxiv,biorxiv",
                    help="逗号分隔：medrxiv,biorxiv")
    args = ap.parse_args()
    today = date.today()
    since = today - timedelta(days=args.days)
    s, e = since.isoformat(), today.isoformat()
    servers = [x.strip() for x in args.servers.split(",") if x.strip()]
    print(f"抓取预印本 {s} ~ {e}：{', '.join(servers)}", flush=True)

    DATA.mkdir(parents=True, exist_ok=True)
    jsonl = DATA / "preprints.jsonl"
    merged = {}
    if jsonl.exists():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            merged[p["doi"]] = p

    skipped_cats = {}
    for server in servers:
        for rec in fetch_server(server, s, e):
            cat = (rec.get("category") or "").lower()
            if server == "biorxiv" and cat not in MED_CATEGORIES:
                skipped_cats[cat] = skipped_cats.get(cat, 0) + 1
                continue
            p = write_preprint(rec, server)
            merged[p["doi"]] = p
        # 每完成一个 server 就落盘一次，可断点续跑
        out = sorted(merged.values(), key=lambda p: p["date"], reverse=True)
        with open(jsonl, "w", encoding="utf-8") as f:
            for p in out:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"  {server}: 已写入 jsonl，当前累计 {len(out)} 篇", flush=True)

    if skipped_cats:
        print("bioRxiv 已过滤分类:",
              json.dumps(skipped_cats, ensure_ascii=False, indent=2))
    by_srv = {}
    for p in merged.values():
        by_srv[p["server"]] = by_srv.get(p["server"], 0) + 1
    print(json.dumps({"total": len(merged), "by_server": by_srv,
                      "range": [s, e]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
