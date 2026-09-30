# -*- coding: utf-8 -*-
"""Robust answer-key vs JSON comparison for source 1 (id == txt question number)."""
import json, re

BASE = "."
data = json.load(open(f"{BASE}/all_questions.json"))
t = open(f"{BASE}/ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 1.txt", encoding="utf-8").read()

# answer key is the run of "N letter." near the end; answers are ก-จ
keys = {}
# scan the last 14000 chars (the key block) with a strict pattern
for m in re.finditer(r"(\d{1,4})\s*([ก-จ])\s*\.", t[-14000:]):
    keys[int(m.group(1))] = m.group(2)

print("key entries parsed:", len(keys))

mism = []
checked = 0
for q in data:
    if q["source"] != 1:
        continue
    qid = q["id"]
    if qid not in keys:
        continue
    checked += 1
    k = keys[qid]
    ja = (q["answer"] or [""])[0]
    if k != ja:
        mism.append((qid, k, ja, q["question"][:50]))

print("checked:", checked, "| mismatches:", len(mism))
for m in mism:
    print(f"  id={m[0]:4d}  key={m[1]}  json={m[2]}  | {m[3]}")
