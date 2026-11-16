#!/usr/bin/env python3
"""生成 cases/00_index.md：合并既有 NN_证型案.md 与本脚本生成的 sh_*/li_* 医案。"""
import re, os, glob

rows = []
# 新生成
if os.path.exists("cases/00_index.md"):
    t = open("cases/00_index.md", encoding="utf-8").read()
    for m in re.finditer(r"^\| (.+?) \| (.+?) \| (.+?) \| L(\d+) \| `(.+?)` \|$", t, re.M):
        rows.append((m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), "新"))
# 既有
for f in sorted(glob.glob("cases/[0-9][0-9]_*.md")):
    tt = open(f, encoding="utf-8").read()
    title = re.search(r"^#\s+(.+)$", tt, re.M)
    title = title.group(1).strip() if title else os.path.basename(f)
    src = re.search(r"来源[:：]\s*(.+)", tt)
    src = src.group(1).strip() if src else "（未标注）"
    rows.append((title[:24], "—", src, "—", os.path.basename(f), "既有"))

with open("cases/00_index.md", "w", encoding="utf-8") as f:
    f.write("# 医案库索引\n\n")
    f.write(f"> 共 {len(rows)} 篇医案文件（新增 {sum(1 for r in rows if r[5]=='新')} · 既有 {sum(1 for r in rows if r[5]=='既有')}）。\n")
    f.write("> 新增医案逐条溯源至底稿行号，四段链内容逐字取自原文；原文未载者显式标注，未作推理补全。\n\n")
    f.write("| 方证/病种 | 患者 | 出处 | 行号 | 文件 | 批次 |\n")
    f.write("|-----------|------|------|------|------|------|\n")
    for r in rows:
        f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3] if r[3]=='—' else 'L'+r[3]} | `{r[4]}` | {r[5]} |\n")
    f.write("\n> 检索：症状/病名 → 查本表定位方证 → Read 对应医案文件。\n")
print(f"index rows={len(rows)}")
