#!/usr/bin/env python3
"""从伤寒库底稿抽取真医案（证-机-方-效 四段链 + 原文溯源）。
源一：shanghan_raw.md 的 【附医案】 块（伤寒论讲稿随证附案）
源二：linzheng_raw.md《临证会要》疑难病验案
原则：内容逐字取自原文；原文未载者显式标注；剂量按原文不换算。
"""
import re, os, json, sys

OUT = "cases"

def read(p): return open(p, encoding="utf-8").read().split("\n")

def clean(s):
    s = re.sub(r"\$[^$\n]*\$", "", s)
    s = s.replace("\\times", "×").replace("\\mathbb{I}", "Ⅱ")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    return re.sub(r"[ \t]+", " ", s).strip()

def sentences(t):
    t = re.sub(r"\s*\n\s*", " ", t)
    return [x.strip() for x in re.split(r"(?<=[。；])", t) if x.strip()]

RE_ZHENG = re.compile(r"(辨为|辨证|证属|属[太阳阳明少阳太阴厥阴])")
RE_FANG  = re.compile(r"(投|为疏|处方|方药[:：]|用本方|予|服上方|拟)")
RE_XIAO  = re.compile(r"(愈|好转|减轻|消失|改善|恢复|有效|无效|退|安|正常|复查|随访|不作痛|能食)")
RE_JI    = re.compile(r"(病机|所致|因|病在|湿|瘀|寒|热|水饮|痰|虚)")

def pick(sents, rx, limit=4, exclude=()):
    out = []
    for s in sents:
        if s in exclude: continue
        if rx.search(s) and s not in out: out.append(s)
        if len(out) >= limit: break
    return out

def build(first, body):
    ss = sentences(body)
    z = pick(ss, RE_ZHENG, 2)
    j = [s for s in pick(ss, RE_JI, 8) if s not in z]
    f = pick(ss, RE_FANG, 3, exclude=z)
    x = [s for s in pick(ss, RE_XIAO, 4) if s not in f and s not in z]
    return z, j, f, x

def seg(t, items, miss):
    if not items: return f"## {t}\n\n{miss}\n"
    return f"## {t}\n\n" + "\n".join(f"- {s}" for s in items) + "\n"

cases = []

# ================= 源一：shanghan_raw.md =================
lines = read("shanghan_raw.md")

# 所有标题
heads = [(i, l.strip()) for i, l in enumerate(lines, 1) if l.startswith("#")]

RE_FANGZHENG = re.compile(r"^#\s*(?:[（(]?[一二三四五六七八九十\d]+[）)\.．]?\s*)?(?:.*?)证(?:及.*)?$")
RE_FANGYAO  = re.compile(r"^#\s*【方药】\s*(.+)$")

def owner_of(ln):
    """返回 (方证标题, 落款方名, 行号)"""
    fz = None; fz_ln = None
    for i, l in heads:
        if i >= ln: break
        m = RE_FANGZHENG.match(l)
        if m and not l.startswith("# 【方药】"):
            fz = l.lstrip("# ").strip(); fz_ln = i
        my = RE_FANGYAO.match(l)
        if my:
            fang_name = my.group(1).strip()
    return fz, fang_name if 'fang_name' in dir() else "", fz_ln

def owner_of_safe(ln):
    fz, fz_ln, fang_name, fang_ln = None, None, None, None
    for i, l in heads:
        if i >= ln: break
        if RE_FANGYAO.match(l):
            fang_name = RE_FANGYAO.match(l).group(1).strip(); fang_ln = i
        elif RE_FANGZHENG.match(l):
            fz = l.lstrip("# ").strip(); fz_ln = i
    return fz, fang_name, fz_ln, fang_ln

for i, l in enumerate(lines, 1):
    m = re.match(r"^【附医案】\s*(.*)$", l.strip())
    if not m: continue
    first = clean(m.group(1))
    body = []
    for j in range(i, len(lines) + 1):
        if j > i and (lines[j-1].strip().startswith("【附医案】") or lines[j-1].startswith("#")):
            break
        body.append(lines[j-1].rstrip())
    body = clean("\n".join(body).strip())
    fz, fang_name, fz_ln, fang_ln = owner_of_safe(i)
    # 归属优先用方证标题；若方证标题过泛（含"及加减证"），用方药名
    formula = fz or fang_name or "（未定位方证）"
    z, jj, f, x = build(first, body)
    cases.append(dict(src="shanghan_raw.md", line=i, first=first, body=body,
                       formula=formula, z=z, ji=jj, f=f, x=x))

# ================= 源二：linzheng_raw.md =================
lines2 = read("linzheng_raw.md")
sec_heads = [(i, l.strip()) for i, l in enumerate(lines2, 1)
             if i >= 4487 and l.startswith("#") and not l.startswith("##")]
for idx, (i, h) in enumerate(sec_heads):
    end = sec_heads[idx+1][0] if idx+1 < len(sec_heads) else len(lines2)+1
    block = lines2[i-1:end-1]
    starts = []
    for k in range(len(block)):
        st = block[k].strip()
        if re.match(r"^[一-鿿]{1,3}某[，,][男女]", st):
            # 下一非空行不是小标题/治法/方药，才算案例起点
            nxt = ""
            for k2 in range(k+1, min(k+4, len(block))):
                if block[k2].strip():
                    nxt = block[k2].strip(); break
            if nxt and not nxt.startswith(("#", "治法", "方药", "用法", "体会", "附记")):
                starts.append(k)
    for si, k in enumerate(starts):
        stop = starts[si+1] if si+1 < len(starts) else len(block)
        cbody = []
        for z2 in range(k, stop):
            l2 = block[z2]
            if z2 > k and re.match(r"^[一-鿿]{1,3}某[，,][男女]", l2.strip()): break
            if z2 > k and l2.strip().startswith(("#", "附记", "白鹅血、白鸭血的服法")): break
            cbody.append(l2.rstrip())
        first = clean(block[k]); body = clean("\n".join(cbody).strip())
        if len(body) < 80: continue
        z, jj, f, x = build(first, body)
        cases.append(dict(src="linzheng_raw.md", line=i+k, first=first, body=body,
                           formula=h.lstrip("# ").strip(), z=z, ji=jj, f=f, x=x))

print(f"抽取 {len(cases)} 则", file=sys.stderr)
json.dump(cases, open("scripts/cases_extracted.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(c["src"] for c in cases), file=sys.stderr)
for c in cases:
    print(f"{c['src']}:{c['line']}\t{c['formula'][:30]}\t{c['first'][:34]}", file=sys.stderr)

# ================= 生成文件 =================
import glob, hashlib
os.makedirs(OUT, exist_ok=True)
# 只清理本脚本生成的 sh_*/li_* 文件，不触碰既有的 NN_证型案.md
for f in glob.glob(f"{OUT}/sh_*.md") + glob.glob(f"{OUT}/li_*.md"):
    os.remove(f)

def digest_of(s): return hashlib.md5(s.encode()).hexdigest()[:6]

rows = []
for c in cases:
    d = digest_of(c["src"] + str(c["line"]) + c["first"][:20])
    p1 = re.match(r"^[一-鿿]", c["first"])
    tag = p1.group(0) if p1 else "案"
    fn = f"{c['src'][:2]}_{tag}{d}.md"
    srcname = c["src"]
    kw = c["first"][:14]
    md = f"""# 医案：{c['formula']}（{c['first']}）

**所属方证/病种**：{c['formula']}
**出处底稿**：{srcname}（第 {c['line']} 行起）
**溯源**：`{srcname}` 搜"{kw}"（第 {c['line']} 行）

{seg("证", c["z"], "原文未显式标出证型，参见【原文】与脉舌描述。")}
{seg("机", c["ji"], "原文未单独论述病机。")}
{seg("方", c["f"], "原文仅记方名，组成见 `modules/` 对应方剂条目。")}
{seg("效", c["x"], "未见疗效记录。")}

## 原文摘录

> {c['first']}
>
{c['body']}
"""
    open(f"{OUT}/{fn}", "w", encoding="utf-8").write(md)
    rows.append((c["formula"], c["first"], srcname, c["line"], fn))

with open(f"{OUT}/00_index.md", "w", encoding="utf-8") as f:
    f.write("# 医案库索引\n\n")
    f.write(f"> 共 {len(rows)} 则真医案，逐条溯源至底稿行号。\n")
    f.write("> 四段链内容逐字取自原文；原文未载者显式标注，未作推理补全。\n\n")
    f.write("| 方证/病种 | 患者 | 底稿 | 行号 | 文件 |\n")
    f.write("|-----------|------|------|------|------|\n")
    for formula, first, srcname, ln, fn in rows:
        f.write(f"| {formula[:24]} | {first[:30]} | {srcname} | L{ln} | `{fn}` |\n")
    f.write("\n> 检索：症状/病名 → 查本表定位方证 → Read 对应医案文件。\n")
print(f"生成 {len(rows)} 篇医案", file=sys.stderr)
