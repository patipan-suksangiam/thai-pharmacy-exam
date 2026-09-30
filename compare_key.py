# -*- coding: utf-8 -*-
"""Compare the answer key embedded at the end of each .txt against all_questions.json answers."""
import json, re, glob, os

BASE = "."
data = json.load(open(f"{BASE}/all_questions.json"))

# build id -> (source, answer)
by_id = {q["id"]: q for q in data}

KEY_RE = re.compile(r"(\d{1,4})\s*([ก-ฮ]|[ก-ฮ][ก-ฮ]?)\s*[.)]\s*")

report = []
for src in (1, 2, 3, 4, 5):
    fp = f"{BASE}/ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ {src}.txt"
    if not os.path.exists(fp):
        continue
    t = open(fp, encoding="utf-8").read()
    # find the key block: the last big run of "N letter." patterns
    # take from the last occurrence of a question-number line near the end
    keys = {}
    for m in KEY_RE.finditer(t):
        n = int(m.group(1))
        if 1 <= n <= 2000:
            keys[n] = m.group(2)
    # questions of this source
    qs = [q for q in data if q["source"] == src]
    # map: the id of a source question corresponds to the .txt question number? 
    # ids are NOT equal to txt numbers. We need the txt-number -> question mapping.
    # For now: report the raw key only.
    nkeys = sum(1 for q in qs if q["id"] in keys)
    print(f"source {src}: {len(qs)} questions, {len(keys)} key entries, ids-in-key {nkeys}")
    # sample the key around id 615 for source 1
    if src == 1:
        for n in (613, 614, 615, 616, 617, 618):
            print(f"   txt#{n} -> key '{keys.get(n)}' | json answer for id {n} = {by_id.get(n, {}).get('answer')}")

# For source 1, find mismatches where id == txt number
print("\n=== source1: mismatch between key[txt#] and json[id] where id == txt# ===")
mism = []
t = open(f"{BASE}/ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 1.txt", encoding="utf-8").read()
keys = {}
for m in KEY_RE.finditer(t):
    n = int(m.group(1))
    if 1 <= n <= 2000:
        keys[n] = m.group(2)
for q in data:
    if q["source"] != 1:
        continue
    if q["id"] in keys:
        k = keys[q["id"]]
        ja = q["answer"][0] if q["answer"] else ""
        if k != ja:
            mism.append((q["id"], k, ja, q["question"][:45]))
print("mismatches:", len(mism))
for m in mism[:40]:
    print(f"  id={m[0]} key={m[1]} json={m[2]} | {m[3]}")
