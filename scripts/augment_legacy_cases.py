#!/usr/bin/env python3
"""为既有的 NN_证型案.md 补 证-机-方-效 四段链（标准段头）+ 溯源行。
原则：内容全部取自该文件既有正文，逐字搬运，不作推理补全；
      溯源能在底稿定位的给行号，定位不到的显式写明无法给行号。
"""
import re, glob, os

RAWS = ["shanghan_raw.md", "linzheng_raw.md", "jingui_raw.md", "fuqin_zhu_neike_raw.md"]
rawmap = {r: open(r, encoding="utf-8").read().split("\n") for r in RAWS if os.path.exists(r)}

def locate(text):
    sents = [s.strip() for s in re.split(r"(?<=[。；])", text) if len(s.strip()) >= 14]
    for r, lines in rawmap.items():
        for s in sents[:14]:
            key = s[:16]
            for i, l in enumerate(lines, 1):
                if key in l:
                    return r, i, l.strip()
    return None, None, None

def sec(t, name):
    m = re.search(r"\*\*" + re.escape(name) + r"\*\*[：:]?\s*\n?(.*?)(?=\n\*\*[一-鿿]|\n---|\Z)", t, re.S)
    return m.group(1).strip() if m else ""

report = []
for f in sorted(glob.glob("cases/[0-9][0-9]_*.md")):
    if os.path.basename(f) == "00_index.md":
        continue
    t = open(f, encoding="utf-8").read()
    if re.search(r"^## 证\s*$", t, re.M):
        continue
    zq, zp = sec(t, "证候详述"), sec(t, "主诉")
    zheng = ""
    if zq: zheng += "**证候详述**：\n" + zq + "\n\n"
    if zp: zheng += "**主诉**：\n" + zp + "\n\n"
    if not zheng.strip(): zheng = "原文未载证候描述。"

    ji = sec(t, "病因病机") or sec(t, "病因") or "原文未单独论述病机。"

    fang_parts = []
    zf = sec(t, "治法")
    if zf: fang_parts.append("**治法**：\n" + zf)
    for k in ("方药", "用法"):
        v = sec(t, k)
        if v: fang_parts.append(f"**{k}**：\n{v}")
    fang = "\n\n".join(fang_parts) if fang_parts else "原文未载处方。"

    xiao = sec(t, "疗效") or sec(t, "按语") or "未见疗效记录。"

    r, ln, line = locate(t)
    if r:
        kw = line[:12]
        prov = f"**溯源**：`{r}` 搜\"{kw}\"（第 {ln} 行）"
    else:
        srcm = re.search(r"来源[:：]\s*(.+)", t)
        src = srcm.group(1).strip() if srcm else "原书"
        prov = (f"**溯源**：本篇整理自《{src}》，该书内容未收录于本仓库底稿，"
                f"故无法给出行号；请回原书对应篇目核对。")

    block = f"""## 证

{zheng}
## 机

{ji}

## 方

{fang}

## 效

{xiao}

{prov}

"""
    idx = t.find("\n---\n")
    if idx == -1: idx = t.find("\n---")
    t2 = (t[:idx] + "\n" + block + t[idx:]) if idx != -1 else (t + "\n" + block)
    open(f, "w", encoding="utf-8").write(t2)
    report.append((os.path.basename(f), r, ln))

for x in report: print(x)
print("已改造", len(report))
