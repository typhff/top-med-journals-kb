# top-med-journals-kb

顶刊医学论文知识库：The Lancet（柳叶刀）、NEJM（新英格兰医学杂志）、JAMA（美国医学会杂志）近期实质性文献归档，另收录 medRxiv / bioRxiv 医学相关预印本。

## 收录情况

- **期刊论文 988 篇**（2026-06-28 ~ 2026-09-28，近 3 个月）
  - The Lancet：215 篇
  - NEJM：182 篇
  - JAMA：591 篇
  - 其中 160 篇为开放获取（含全文链接）
  - 已过滤社论、评论、读者来信等非实质性内容
- **预印本 10,208 篇**
  - medRxiv：5,130 篇（2026-06-28 ~ 2026-09-28，全量）
  - bioRxiv：5,078 篇（2026-08-29 ~ 2026-09-28，近 30 天，仅收录医学相邻分类）
  - ⚠️ 预印本未经同行评审，引用时请注意

## 目录结构

```
top-med-journals-kb/
├── README.md                 # 本文件
├── papers/
│   ├── INDEX.md              # 按来源/月份的浏览索引
│   ├── lancet/2026-07/…      # 每篇一个 Markdown 文件
│   ├── nejm/2026-07/…
│   ├── jama/2026-07/…
│   └── preprints/
│       ├── medrxiv/2026-07/…
│       └── biorxiv/2026-08/…
├── data/
│   ├── papers.jsonl          # 期刊论文机器可读索引（一行一篇）
│   └── preprints.jsonl       # 预印本机器可读索引（一行一篇）
└── scripts/
    ├── fetch_pubmed.py       # 抓取脚本（PubMed + OpenAlex 公开接口）
    ├── fetch_preprints.py    # 预印本抓取脚本（bioRxiv/medRxiv 公开 API）
    └── build_index.py        # 索引生成脚本
```

每篇论文文件包含：标题、作者、期刊日期、DOI、PubMed 链接、文献类型、
OpenAlex 主题标签、开放获取全文链接（如有）、摘要、MeSH 主题词。

## 更新数据

```bash
python3 scripts/fetch_pubmed.py --days 92      # 重新抓取近 92 天期刊论文（全量重建）
python3 scripts/fetch_preprints.py --servers medrxiv --days 92    # medRxiv 预印本
python3 scripts/fetch_preprints.py --servers biorxiv --days 30    # bioRxiv 预印本（医学相邻分类）
python3 scripts/build_index.py                 # 重新生成浏览索引
```

数据源均为公开免费接口，不涉及付费墙内容：
- NCBI E-utilities（PubMed）：标题 / 作者 / 摘要 / DOI / 发表类型 / MeSH
- OpenAlex：主题概念、开放获取状态与全文链接
- bioRxiv/medRxiv API：预印本标题 / 作者 / 摘要 / DOI / 分类

## 说明

- 摘要来自 PubMed 公开收录；部分文献 PubMed 未收录摘要，请通过 DOI 查看原文。
- 全文链接仅指向开放获取（Open Access）资源。
