#!/usr/bin/env python3
"""就地填充伤寒库 modules 的占位符（待提炼/待补充），用《伤寒论》讲稿原文替换。
原则：不删除既有实质内容；讲稿未收该方者显式标注"讲稿未收此方"，不编造。
解析：按讲稿"方证"分节，节内收集全部【原文】【注解】【治法】【方药】【方解】块，
      以【方药】块首词为方名；组成取方药块正文，功效取【治法】，主治取【原文】，
      辨证要点取【注解】，方解取【方解】，加减/禁忌从节内句子中筛。
"""
import re, glob, os, json

RAW = "shanghan_raw.md"
raw = open(RAW, encoding="utf-8").read().split("\n")

def clean(s):
    s = re.sub(r"\$[^$\n]*\$", "", s)
    s = s.replace("\\times", "×").replace("\\mathbb{I}", "Ⅱ")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    return re.sub(r"[ \t]+", " ", s).strip()

BLOCK_RE = re.compile(r"^【(.+?)】\s*(.*)$")

# 1) 切块
blocks = []
for i, l in enumerate(raw, 1):
    st = l.strip()
    m = BLOCK_RE.match(st)
    if m:
        blocks.append({"line": i, "key": m.group(1), "text": m.group(2)})
    elif st and blocks:
        blocks[-1]["text"] += " " + st

# 2) 按 "# " 标题分节
sections = []      # {"title": str, "blocks": [...]}
cur = {"title": "", "blocks": []}
for idx, l in enumerate(raw, 1):
    if l.startswith("# "):
        if cur["blocks"] or cur["title"]:
            sections.append(cur)
        cur = {"title": l[2:].strip(), "blocks": []}
        continue
    # 把块按行号归属
for b in blocks:
    sec = None
    for s in sections:
        pass
# 简化：线性扫描，遇 "# " 开新节，块按出现顺序归节
sections = []
cur = {"title": "", "blocks": [], "start": 1}
bi = 0
for i, l in enumerate(raw, 1):
    if l.startswith("# "):
        if cur["blocks"]:
            sections.append(cur)
        cur = {"title": l[2:].strip(), "blocks": [], "start": i}
        continue
    while bi < len(blocks) and blocks[bi]["line"] == i:
        cur["blocks"].append(blocks[bi]); bi += 1
if cur["blocks"]:
    sections.append(cur)

def sent(text):
    return [x.strip() for x in re.split(r"(?<=[。；])", clean(text)) if x.strip()]

RE_ADD = re.compile(r"(加减|随证|加减法|若[^。]{0,16}加[一-鿿]{2,6}|去[一-鿿]{2,6}\d|加[一-鿿]{2,6}\d)")
RE_JIN = re.compile(r"(禁|忌|不可|勿|不得|慎用|禁忌|不可令)")

def norm(s): return re.sub(r"[\s　]+", "", s)

# 建立 方名 → 提取结果
byname = {}
for sec in sections:
    bs = sec["blocks"]
    fy_idx = [n for n, b in enumerate(bs) if b["key"] == "方药"]
    if not fy_idx: continue
    for n in fy_idx:
        b = bs[n]
        nm = b["text"].strip().split()[0] if b["text"].strip() else ""
        if not nm: continue
        full = clean(b["text"])
        # 节内全部块文本
        pool_all = " ".join(x["text"] for x in bs)
        def first(key):
            for x in bs:
                if x["key"] == key and x["text"].strip():
                    return clean(x["text"])
            return ""
        add_sents = [s for s in sent(pool_all) if RE_ADD.search(s)]
        jin_sents = [s for s in sent(pool_all) if RE_JIN.search(s)]
        yuanwen = first("原文"); zhujie = first("注解"); zhiyao = first("治法")
        # 功效 fallback：治法 → 注解首句
        gongxiao = zhiyao
        if not gongxiao and zhujie:
            ss = sent(zhujie)
            gongxiao = ss[0] if ss else ""
        # 辨证要点 fallback：注解 → 原文
        bzyd = zhujie[:700] or yuanwen[:700]
        # 加减 / 禁忌 fallback：节内句子 → 组成（煎服法常含"禁…"）
        jiajian = "\n".join(f"- {s}" for s in add_sents[:5])
        jinji = "\n".join(f"- {s}" for s in jin_sents[:5])
        if not jinji:
            extra = [s for s in sent(full) if RE_JIN.search(s)]
            jinji = "\n".join(f"- {s}" for s in extra[:3])
        byname.setdefault(norm(nm), {
            "name": nm,
            "组成": full[len(nm):].strip(),
            "功效": gongxiao,
            "主治": yuanwen,
            "辨证要点": bzyd,
            "方解": first("方解"),
            "加减法": jiajian,
            "禁忌": jinji,
        })

def find_entry(mod_name):
    k = norm(mod_name)
    for cand in (k, k[:-1] if k.endswith("方") else k):
        if cand in byname: return byname[cand]
    for n, e in byname.items():
        if k and abs(len(n) - len(k)) <= 2 and (k in n or n in k):
            return e
    return None

stats = {"filled": 0, "annotated": 0, "kept": 0, "fields": 0}
detail = []
for f in sorted(glob.glob("modules/*.md")):
    t = open(f, encoding="utf-8").read()
    base = os.path.basename(f)[:-3]
    mod_name = base.split("_", 1)[1] if "_" in base else base
    e = find_entry(mod_name)
    t2 = t
    if e is None:
        t2 = t.replace("（待提炼）", "（讲稿未收此方，原文未载）").replace("（待补充）", "（讲稿未收此方，原文未载）")
        if t2 != t:
            open(f, "w", encoding="utf-8").write(t2); stats["annotated"] += 1
        else: stats["kept"] += 1
        continue
    for sec in ["功效", "主治", "辨证要点", "方解", "加减法", "禁忌"]:
        val = (e.get(sec) or "").strip()
        if not val:
            val = {"功效": "讲稿未载功效。", "主治": "讲稿未载主治原文。",
                   "辨证要点": "讲稿未载辨证要点。", "方解": "讲稿未载方解。",
                   "加减法": "讲稿未载加减法。", "禁忌": "讲稿未载禁忌。"}[sec]
        pat = re.compile(r"(^## " + re.escape(sec) + r"\s*\n)(.*?)(?=\n## |\Z)", re.S | re.M)
        m = pat.search(t2)
        if not m: continue
        if m.group(2).strip() not in ("（待提炼）", "（待补充）", ""): continue
        newval = val.replace("\n", " ") if sec in ("主治", "辨证要点", "方解") else val
        t2 = t2[:m.start(2)] + newval + t2[m.end(2):]
        stats["fields"] += 1
    if t2 != t:
        open(f, "w", encoding="utf-8").write(t2); stats["filled"] += 1
    else: stats["kept"] += 1
print(json.dumps(stats, ensure_ascii=False))
print("讲稿可匹配方数:", len(byname))
