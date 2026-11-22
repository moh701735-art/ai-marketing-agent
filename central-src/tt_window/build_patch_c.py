#!/usr/bin/env python3
"""يبني ops/p230c-tt-window-days.py.txt: يبدّل كتلة p230 المركّبة (block_v1.js) بالنسخة الجديدة (block.js)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda n: open(os.path.join(H, n), encoding="utf-8").read().rstrip("\n")
old, new, t = rd("block_v1.js"), rd("block_v2.js"), open(os.path.join(H, "patch_c_template.py"), encoding="utf-8").read()
assert "'''" not in old + new and t.count("@@OLD@@") == 1 and t.count("@@NEW@@") == 1
open(os.path.join(H, "..", "ops", "p230c-tt-window-days.py.txt"), "w", encoding="utf-8").write(t.replace("@@OLD@@", old).replace("@@NEW@@", new))
print("built")
