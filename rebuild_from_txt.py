# -*- coding: utf-8 -*-
"""Rebuild all_questions.json from the five source .txt files.

Why this exists: the old import_sourceN.py scripts did a naive line split, which
(a) truncated questions whose options sat on the same line, (b) kept multi-option
lines as a single option, and (c) wrote "answer": [] for every question.
This script parses each question block as one text stream, finds the option
markers (ก. ข. ค. ง. จ.), and re-attaches the answer key printed at the end of
each source file (หัวข้อ "เฉลย").

Usage:  python3 rebuild_from_txt.py [--dry-run]
"""
import json
import re
import shutil
import sys
import datetime

BASE = "."
LETTERS = "กขคงจฉช"
STOP_TOKENS = {"ข้อ", "และ", "หรือ", "ตอบ", "กับ", "ฎีกา"}

NOISE_PATTERNS = [
    r"โทร\.\s*0?9",
    r"^\s*3 หมู่",
    r"^\s*[๐-๙]+\s*$",
    r"แบบทดสอบเตรียมความพร้อม",
    r"^\s*ข้อ\s*\d+\s*$",
    r"^\s*-\s*\d+\s*-\s*$",
]
NOISE = [re.compile(p) for p in NOISE_PATTERNS]

# source number -> txt path
SOURCES = {
    1: "ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 1.txt",
    2: "ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 2.txt",
    3: "ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 3.txt",
    4: "ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 4.txt",
    5: "ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 5.txt",
}

# Fallback answer-key source for a set whose working txt no longer carries the
# เฉลย section (ชุดที่ 1 was reformatted and the key was dropped). The key is
# matched by question number, so the numbering of the two files must agree.
FALLBACK_KEY_FILES = {
    1: "../ตัวอย่างข้อสอบเล่มสีเขียว 1-5/ตัวอย่างข้อสอบเล่มสีเขียว ชุดที่ 1.txt",
}

# Keys read by eye off the scanned key page where the OCR text is missing them.
# (source, question number) -> letter. Keep this list short and sourced.
KEY_OVERRIDES = {
    (4, 310): "ค",   # PDF ชุดที่ 4 หน้า 46: "309) ข.  310) ค." — the txt dropped it
}


def is_noise(line):
    s = line.strip()
    return bool(s) and any(r.search(s) for r in NOISE)


def read_txt(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def clean(s):
    return re.sub(r"[\s\u00a0]+", " ", s).strip()


def cut_key_section(text):
    """Return (question_part, key_part). The เฉลย section is the answer key."""
    idx = text.find("เฉลย")
    if idx < 0:
        return text, ""
    return text[:idx], text[idx:]


def parse_question_blocks(text):
    """Split the question part into (number, [lines]) blocks."""
    blocks = []
    cur = None
    for line in text.split("\n"):
        if is_noise(line):
            continue
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(\d{1,4})\s*[\.\)]\s*(.*)$", s)
        if m and len(m.group(2).strip()) > 3:
            if cur:
                blocks.append(cur)
            cur = [int(m.group(1)), [m.group(2).strip()]]
            continue
        if cur:
            cur[1].append(s)
    if cur:
        blocks.append(cur)
    return blocks


def option_markers(text, sep):
    out = []
    for m in re.finditer(r"(?:^|\n|[\s\u00a0]{%d,})([ก-จ])[\.\)][\s\u00a0]*" % sep, text):
        at_line_start = m.start(1) == 0 or text[m.start(1) - 1] == "\n"
        if not at_line_start:
            pre = text[: m.start(1)]
            toks = [t for t in re.split(r"[\s\u00a0]+", pre.strip()) if t]
            if toks and toks[-1] in STOP_TOKENS:
                continue
        out.append(m)
    return out


def split_question(parts):
    """Return (stem, [[letter, text], ...]) for one question block."""
    text = "\n".join(parts)
    best = None
    for sep in (2, 1):
        by_letter = {}
        for m in option_markers(text, sep):
            by_letter.setdefault(m.group(1), m)
        if len(by_letter) < 2:
            continue
        keep = sorted(by_letter.values(), key=lambda m: m.start())
        pairs = []
        for k, m in enumerate(keep):
            end = keep[k + 1].start(1) if k + 1 < len(keep) else len(text)
            pairs.append([m.group(1), clean(text[m.end():end])])
        if not all(p[1] for p in pairs):
            continue
        stem = clean(text[: keep[0].start(1)])
        pairs.sort(key=lambda p: LETTERS.find(p[0]))
        if best is None or len(pairs) > len(best[1]):
            best = (stem, pairs)
    if best:
        return best
    return clean(text), []


def parse_answers(key_part):
    """Answer key -> {question number: letter}.

    Two layouts appear in the sources:
        "1) ก.  2) ข."      (sets 2-5)
        "1 ก.   2 ก."       (set 1)
    Both are scan-derived, so two quirks must be handled:
      * a letter can be missing entirely where the book printed a blank
        (e.g. ชุด 2 ข้อ 191, ชุด 4 ข้อ 173) — those questions stay keyless;
      * the book misprints question 316 as a second "315" (ชุด 3, 4, 5), so an
        immediately repeated number is read as the next question number.
    """
    if not key_part:
        return {}

    def scan(pattern):
        raw = [(int(m.group(1)), m.group(2)) for m in re.finditer(pattern, key_part)]
        out = {}
        last = 0
        for i, (num, letter) in enumerate(raw):
            if num < last:              # page footer noise (phone numbers, addresses)
                continue
            if num == last:             # number printed twice in the source
                nxt = raw[i + 1][0] if i + 1 < len(raw) else None
                if nxt == num + 2:      # book misprint: "315) ง. 315) ค. 317)"
                    out[num + 1] = letter      # -> the second one is question 316
                    last = num + 1
                # otherwise it is a duplicated OCR line: drop it
                continue
            out[num] = letter
            last = num
        return out

    paren = scan(r"(?<!\d)(\d{1,4})\s*[\)\.]\s*([ก-จ])(?![ก-ฮ])")
    bare = scan(r"(?<!\d)(\d{1,4})\s*([ก-จ])\s*\.?(?![ก-ฮ])")
    return paren if len(paren) >= len(bare) else bare


def build():
    data = []
    stats = {}
    for n, name in SOURCES.items():
        text = read_txt(f"{BASE}/{name}")
        qpart, kpart = cut_key_section(text)
        if not kpart and n in FALLBACK_KEY_FILES:
            kpart = cut_key_section(read_txt(f"{BASE}/{FALLBACK_KEY_FILES[n]}"))[1]
        blocks = parse_question_blocks(qpart)
        answers = parse_answers(kpart)
        per = {"questions": 0, "with_key": 0, "no_key": 0, "short_options": 0}
        for num, parts in blocks:
            stem, opts = split_question(parts)
            letter = answers.get(num, KEY_OVERRIDES.get((n, num)))
            letters = [o[0] for o in opts]
            ans = [letter] if letter and letter in letters else []
            if letter:
                per["with_key"] += 1
            else:
                per["no_key"] += 1
            if len(opts) < 4:
                per["short_options"] += 1
            per["questions"] += 1
            data.append({
                "id": num,
                "question": stem,
                "options": [f"{o[0]}. {o[1]}" for o in opts],
                "answer": ans,
                "source": n,
            })
        stats[n] = per
    return data, stats


def main():
    dry = "--dry-run" in sys.argv
    data, stats = build()
    for n in sorted(stats):
        s = stats[n]
        print(f"ชุดที่ {n}: {s['questions']:4d} ข้อ | มีเฉลย {s['with_key']:4d} | "
              f"ไม่มีเฉลย {s['no_key']:3d} | ตัวเลือกไม่ครบ 4 ข้อ {s['short_options']:3d}")
    print(f"รวมทั้งหมด {len(data)} ข้อ")
    if dry:
        return
    json_path = f"{BASE}/all_questions.json"
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    shutil.copyfile(json_path, f"{json_path}.bak-{stamp}")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("เขียนทับ:", json_path)
    print("สำรองไว้ที่:", f"{json_path}.bak-{stamp}")


if __name__ == "__main__":
    main()
