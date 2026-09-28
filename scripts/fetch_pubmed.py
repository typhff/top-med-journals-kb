#!/usr/bin/env python3
"""
从 PubMed 抓取 Lancet / NEJM / JAMA 近 N 天的论文元数据，
用 OpenAlex 补充主题标签与开放获取链接，写入知识库。

数据源均为公开免费接口：
  - NCBI E-utilities (PubMed)：标题 / 作者 / 摘要 / DOI / 发表类型 / MeSH
  - OpenAlex：主题概念(Concepts)、开放获取状态、OA 全文链接

用法：
  python3 scripts/fetch_pubmed.py [--days 92]
重跑会全量重建 papers/ 与 data/papers.jsonl（按 PMID 去重，幂等）。
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PAPERS_DIR = ROOT / "papers"

JOURNALS = {
    "Lancet": "lancet",
    "N Engl J Med": "nejm",
    "JAMA": "jama",
}

# 这些发表类型视为非实质性内容，直接过滤
EXCLUDE_TYPES = {
    "Editorial", "Comment", "Letter", "News", "Biography", "Autobiography",
    "Portrait", "Interview", "Directory", "Congress", "Festschrift",
    "Retraction of Publication", "Retracted Publication", "Duplicate Publication",
    "Published Erratum", "Erratum", "Correction",
}

MONTH_MAP = {m: f"{i:02d}" for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}

UA = {"User-Agent": "med-papers-kb/1.0 (personal knowledge base; polite pool)"}


def http_get(url, timeout=30, retries=3):
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - 网络抖动则重试
            last = e
            time.sleep(2)
    raise RuntimeError(f"GET 失败: {url} ({last})")


def esearch_ids(term, retmax=100000):
    q = urllib.parse.urlencode(
        {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json"})
    raw = http_get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{q}")
    ids = json.loads(raw)["esearchresult"]["idlist"]
    print(f"  检索到 {len(ids)} 条 PMID", flush=True)
    return ids


def efetch_xml(idlist):
    out = []
    for i in range(0, len(idlist), 200):
        chunk = idlist[i:i + 200]
        q = urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(chunk), "retmode": "xml"})
        raw = http_get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{q}")
        out.append(raw)
        time.sleep(0.4)  # NCBI 未持 key 限速 3 req/s
    return out  # 每个 batch 是独立 XML 文档，调用方分别解析


def text(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_pubmed(xml_bytes):
    papers = []
    root = ET.fromstring(xml_bytes)
    for art in root.findall("PubmedArticle"):
        mc = art.find("MedlineCitation")
        pmid = text(mc.find("PMID"))
        article = mc.find("Article")
        if article is None:
            continue
        title = html.unescape(text(article.find("ArticleTitle"))).rstrip(".")
        # 摘要（可能分段带小标题）
        abs_parts = []
        for ab in article.findall("Abstract/AbstractText"):
            label = ab.get("Label")
            t = html.unescape(text(ab))
            abs_parts.append(f"{label}: {t}" if label else t)
        abstract = "\n\n".join(abs_parts)
        # 作者
        authors = []
        for au in article.findall("AuthorList/Author"):
            if au.find("CollectiveName") is not None:
                authors.append(text(au.find("CollectiveName")))
            else:
                ln = text(au.find("LastName"))
                fn = text(au.find("ForeName")) or text(au.find("Initials"))
                authors.append(f"{ln} {fn}".strip() if ln else fn)
        # 期刊与日期
        journal_el = article.find("Journal")
        iso = text(journal_el.find("ISOAbbreviation")) if journal_el is not None else ""
        jtitle = text(journal_el.find("Title")) if journal_el is not None else ""
        pubdate = article.find("Journal/JournalIssue/PubDate")
        year = text(pubdate.find("Year")) if pubdate is not None else ""
        month = text(pubdate.find("Month")) if pubdate is not None else ""
        day = text(pubdate.find("Day")) if pubdate is not None else ""
        if not year and pubdate is not None:  # MedlineDate 兜底
            m = re.search(r"(\d{4})", text(pubdate.find("MedlineDate")))
            year = m.group(1) if m else ""
        month = MONTH_MAP.get(month[:3], month if month.isdigit() else "01")
        day = day if day.isdigit() else "01"
        pub_day = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year else ""
        # DOI
        doi = ""
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = text(aid).lower()
        # 发表类型 / MeSH
        ptypes = [text(p) for p in article.findall("PublicationTypeList/PublicationType")]
        mesh = [text(m.find("DescriptorName"))
                for m in mc.findall("MeshHeadingList/MeshHeading")]
        # 期刊归一化
        slug = JOURNALS.get(iso) or JOURNALS.get(jtitle)
        if not slug:
            for k, v in JOURNALS.items():
                if k.lower() in (iso + " " + jtitle).lower():
                    slug = v
                    break
        if not slug:
            continue
        # 过滤非实质性类型
        if ptypes and all(t in EXCLUDE_TYPES for t in ptypes):
            continue
        papers.append({
            "pmid": pmid, "title": title, "abstract": abstract,
            "authors": authors, "journal_iso": iso or jtitle,
            "journal_slug": slug, "date": pub_day,
            "month": pub_day[:7] if pub_day else "",
            "doi": doi, "pub_types": ptypes, "mesh": mesh[:15],
        })
    return papers


def enrich_openalex(doi):
    """用 OpenAlex 补充主题概念与 OA 链接；失败返回空 dict。"""
    if not doi:
        return {}
    try:
        url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="")
        data = json.loads(http_get(url, timeout=15, retries=1))
        concepts = [c["display_name"] for c in data.get("concepts", [])[:6]]
        oa = data.get("open_access", {}) or {}
        best = data.get("best_oa_location") or {}
        primary = data.get("primary_location") or {}
        return {
            "concepts": concepts,
            "is_oa": bool(oa.get("is_oa")),
            "oa_pdf": best.get("pdf_url") or "",
            "oa_url": best.get("landing_page_url") or primary.get("landing_page_url") or "",
        }
    except Exception:  # noqa: BLE001 - 补充信息缺失不影响主流程
        return {}


def md_escape(s):
    return s.replace("|", "\\|")


def write_paper(p):
    d = PAPERS_DIR / p["journal_slug"] / p["month"]
    d.mkdir(parents=True, exist_ok=True)
    authors = ", ".join(p["authors"][:12]) + (" et al." if len(p["authors"]) > 12 else "")
    tags = p.get("concepts", [])[:4]
    fm = {
        "pmid": p["pmid"], "doi": p["doi"], "journal": p["journal_slug"],
        "date": p["date"], "tags": tags, "is_oa": p.get("is_oa", False),
    }
    lines = ["---",
             json.dumps(fm, ensure_ascii=False, indent=2),
             "---", "",
             f"# {p['title']}", "",
             f"**期刊**: {p['journal_iso']} · {p['date']}", "",
             f"**作者**: {md_escape(authors) or '—'}", ""]
    if p["doi"]:
        lines += [f"**DOI**: [{p['doi']}](https://doi.org/{p['doi']})",
                  f"**PubMed**: https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/", ""]
    if p.get("is_oa") and p.get("oa_pdf"):
        lines += [f"**开放获取全文**: [PDF]({p['oa_pdf']})", ""]
    elif p.get("is_oa") and p.get("oa_url"):
        lines += [f"**开放获取**: {p['oa_url']}", ""]
    if p["pub_types"]:
        lines += [f"**文献类型**: {', '.join(p['pub_types'])}", ""]
    if tags:
        lines += [f"**主题**: {', '.join(tags)}", ""]
    lines += ["## 摘要", ""]
    lines += [p["abstract"] if p["abstract"] else "_PubMed 未收录摘要，请通过 DOI 查看原文。_", ""]
    if p["mesh"]:
        lines += ["## MeSH 主题词", "", ", ".join(f"`{m}`" for m in p["mesh"]), ""]
    (d / f"{p['pmid']}.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=92)
    args = ap.parse_args()

    today = date.today()
    since = today - timedelta(days=args.days)
    term = ("(Lancet[jour] OR \"N Engl J Med\"[jour] OR JAMA[jour]) AND "
            f"(\"{since:%Y/%m/%d}\"[pdat] : \"{today:%Y/%m/%d}\"[pdat])")
    print(f"检索式: {term}\n时间范围: {since} ~ {today}", flush=True)

    ids = esearch_ids(term)
    if not ids:
        print("无结果")
        return
    papers = []
    for raw in efetch_xml(ids):  # 每个 batch 是独立 XML 文档，需分别解析
        papers.extend(parse_pubmed(raw))
    print(f"过滤后保留 {len(papers)} 篇实质性文献", flush=True)

    # OpenAlex 补充（best-effort）
    for i, p in enumerate(papers):
        extra = enrich_openalex(p["doi"])
        p.update(extra)
        if (i + 1) % 25 == 0:
            print(f"  OpenAlex 补充进度 {i + 1}/{len(papers)}", flush=True)
        time.sleep(0.15)

    # 落盘
    for p in papers:
        write_paper(p)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "papers.jsonl", "w", encoding="utf-8") as f:
        for p in papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # 统计
    by_j = {}
    for p in papers:
        by_j[p["journal_slug"]] = by_j.get(p["journal_slug"], 0) + 1
    oa_n = sum(1 for p in papers if p.get("is_oa"))
    print(json.dumps({"total": len(papers), "by_journal": by_j,
                      "open_access": oa_n,
                      "range": [str(since), str(today)]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
