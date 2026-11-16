#!/usr/bin/env python3
"""Skill 质控校验（蓝本 tcm-distiller：S1-S12 / 字段完整性 / 溯源 / 索引审计 / 剂量）
用法: python3 scripts/validate_skill.py [--repo <dir>]
退出码 0 = 全通过；1 = 有 FAIL
"""
import re, os, sys, glob, json, argparse

p = argparse.ArgumentParser()
p.add_argument("--repo", default=".")
p.add_argument("--raw", default=None, help="底稿文件名，用于溯源行号校验")
args = p.parse_args()
R = args.repo
os.chdir(R)

errors, warns, notes = [], [], []
def FAIL(m): errors.append(m)
def WARN(m): warns.append(m)
def NOTE(m): notes.append(m)

# ---------- 1. 目录结构 ----------
for d in ["modules", "cases", "sources"]:
    if not os.path.isdir(d): FAIL(f"缺少目录 {d}/")

def md(globpat):
    return sorted(glob.glob(globpat))

mods = md("modules/*.md")
cases = [f for f in md("cases/*.md") if not f.endswith("00_index.md")]
srcs = md("sources/*.md")
NOTE(f"modules={len(mods)} cases={len(cases)} sources={len(srcs)}")

# ---------- 2. 模块字段完整性 ----------
REQ = ["出处", "组成", "主治", "辨证要点", "禁忌"]
ADD_KEYS = ["加减", "加减法"]
OPT = ["功效", "方解", "用法"]
missing_counter = {}
for f in mods:
    t = open(f, encoding="utf-8").read()
    for k in REQ:
        if k not in t:
            missing_counter.setdefault(k, []).append(os.path.basename(f))
    if not any(k in t for k in ADD_KEYS):
        missing_counter.setdefault("加减/加减法", []).append(os.path.basename(f))
    for k in OPT:
        if k not in t:
            NOTE(f"{os.path.basename(f)} 缺可选字段 {k}")
    if "待提炼" in t or "待补充" in t:
        FAIL(f"{os.path.basename(f)} 仍含占位符（待提炼/待补充）")
for k, v in missing_counter.items():
    FAIL(f"modules 字段缺失：{k} → {len(v)} 篇，如 {v[:4]}")

# ---------- 3. 医案四段链 + 溯源 ----------
CASE_REQ = ["## 证", "## 机", "## 方", "## 效", "**溯源**"]
for f in cases:
    t = open(f, encoding="utf-8").read()
    for k in CASE_REQ:
        if k not in t: FAIL(f"{os.path.basename(f)} 缺医案段/溯源字段：{k}")
    if "原文未载" not in t and "未见疗效记录" not in t:
        NOTE(f"{os.path.basename(f)} 未出现诚实标注")
    for m in re.finditer(r"\*\*溯源\*\*：`([^`]+)` 搜\"([^\"]*)\"（第 (\d+) 行）", t):
        rawf, kw, ln = m.group(1), m.group(2), int(m.group(3))
        if not os.path.exists(rawf):
            NOTE(f"{os.path.basename(f)} 溯源文件 {rawf} 未随库分发（底稿可从来源书核对）")
            continue
        lines = open(rawf, encoding="utf-8").read().split("\n")
        if ln > len(lines):
            FAIL(f"{os.path.basename(f)} 溯源行号 {ln} 越界（共 {len(lines)} 行）")
        elif kw and kw not in lines[ln-1]:
            FAIL(f"{os.path.basename(f)} 溯源行 L{ln} 不含关键词「{kw}」")

# ---------- 4. 索引完整性（cases/00_index.md）----------
idx = "cases/00_index.md"
if os.path.exists(idx):
    t = open(idx, encoding="utf-8").read()
    listed = set(re.findall(r"`([^`]*\.md)`", t))
    listed = {x.split("/")[-1] for x in listed}
    actual = {os.path.basename(f) for f in cases}
    miss = actual - listed
    listed.discard("00_index.md")
    dead = listed - actual
    if miss: FAIL(f"cases/00_index.md 未收录 {len(miss)} 篇：{sorted(miss)[:5]}")
    if dead: FAIL(f"cases/00_index.md 索引指向不存在的文件：{sorted(dead)[:5]}")
else:
    FAIL("缺少 cases/00_index.md")

# ---------- 5. 模块-医案配对：每方剂至多一个医案文件引用 ----------
ref = {}
for f in cases:
    t = open(f, encoding="utf-8").read()
    m = re.search(r"\*\*来源方剂\*\*：([\d.]+)", t)
    if m: ref.setdefault(m.group(1), []).append(os.path.basename(f))
dup = {k: v for k, v in ref.items() if len(v) > 1}
if dup: WARN(f"同一方剂挂多则医案：{dup}")

# ---------- 6. 剂量单位一致性 ----------
unit_bad = []
for f in mods:
    t = open(f, encoding="utf-8").read()
    comp = re.search(r"(?:## |\[)组成\]\s*(.+)", t)
    if not comp: continue
    seg = comp.group(1).split("\n")[0]
    if re.search(r"\d+\s*(钱|两|分|克)", seg):
        # 非克单位混用，允许但需提示
        unit_bad.append(os.path.basename(f))
if unit_bad: WARN(f"{len(unit_bad)} 篇模块含非克计量单位（钱/两/分）：{unit_bad[:5]}")

# ---------- 7. 医学安全边界 ----------
safety = re.compile(r"(面诊|就医|医师|辨证施治|仅供参考|不能替代|必须在|指导下)")
for f in ["SKILL.md", "README.md"]:
    if os.path.exists(f):
        t = open(f, encoding="utf-8").read()
        if not safety.search(t): FAIL(f"{f} 缺少医疗安全边界声明")
    else:
        WARN(f"缺少 {f}")

# ---------- 8. 索引中不得出现行号硬编码（SKILL.md 正文）----------
if os.path.exists("SKILL.md"):
    t = open("SKILL.md", encoding="utf-8").read()
    if re.search(r"(第\s*\d+\s*[-–]\s*\d+\s*行|L\d{3,})", t):
        FAIL("SKILL.md 正文含行号引用（违反索引铁律）")

print("=" * 60)
for e in errors: print("FAIL:", e)
for w in warns: print("WARN:", w)
for n in notes: print("NOTE:", n)
print("=" * 60)
print(f"errors={len(errors)} warns={len(warns)}")
sys.exit(1 if errors else 0)
