# top-med-journals-kb

顶刊医学论文知识库：The Lancet（柳叶刀）、NEJM（新英格兰医学杂志）、JAMA（美国医学会杂志）近期实质性文献归档。

## 收录情况

- **共 988 篇**（2026-06-28 ~ 2026-09-28，近 3 个月）
  - The Lancet：215 篇
  - NEJM：182 篇
  - JAMA：591 篇
- 其中 160 篇为开放获取（含全文链接）
- 已过滤社论、评论、读者来信等非实质性内容

## 目录结构

```
top-med-journals-kb/
├── README.md                 # 本文件
├── papers/
│   ├── INDEX.md              # 按期刊/月份的浏览索引
│   ├── lancet/2026-07/…      # 每篇一个 Markdown 文件
│   ├── nejm/2026-07/…
│   └── jama/2026-07/…
├── data/
│   └── papers.jsonl          # 机器可读的全量索引（一行一篇）
└── scripts/
    ├── fetch_pubmed.py       # 抓取脚本（PubMed + OpenAlex 公开接口）
    └── build_index.py        # 索引生成脚本
```

每篇论文文件包含：标题、作者、期刊日期、DOI、PubMed 链接、文献类型、
OpenAlex 主题标签、开放获取全文链接（如有）、摘要、MeSH 主题词。

## 更新数据

```bash
python3 scripts/fetch_pubmed.py --days 92   # 重新抓取近 92 天（全量重建）
python3 scripts/build_index.py              # 重新生成浏览索引
```

数据源均为公开免费接口，不涉及付费墙内容：
- NCBI E-utilities（PubMed）：标题 / 作者 / 摘要 / DOI / 发表类型 / MeSH
- OpenAlex：主题概念、开放获取状态与全文链接

## 说明

- 摘要来自 PubMed 公开收录；部分文献 PubMed 未收录摘要，请通过 DOI 查看原文。
- 全文链接仅指向开放获取（Open Access）资源。
