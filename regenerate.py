# -*- coding: utf-8 -*-
"""Rebuild index.html by SLICING the embedded 'const ALL = [...]' array (never lazy regex)."""
import json, sys

BASE = "."
h = open(f"{BASE}/index.html", encoding="utf-8").read()
data = json.load(open(f"{BASE}/all_questions.json"))

MARK = "const ALL = "
start = h.index(MARK) + len(MARK)
# string-aware bracket match
depth = 0; instr = False; esc = False; j = start
while j < len(h):
    c = h[j]
    if instr:
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            instr = False
    else:
        if c == '"':
            instr = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                j += 1
                break
    j += 1

# compact JS-friendly JSON (match original style: ', ' and ': ')
new_arr = json.dumps(data, ensure_ascii=False, separators=(", ", ": "))
out = h[:start] + new_arr + h[j:]
open(f"{BASE}/index.html", "w", encoding="utf-8").write(out)

print("questions embedded:", len(data))
print("index.html old bytes:", len(h), "new bytes:", len(out))
# sanity: the JS after the array is intact
print("tail intact:", h[j:j + 30] == out[start + len(new_arr):start + len(new_arr) + 30])
