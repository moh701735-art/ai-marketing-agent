#!/usr/bin/env python3
"""يبني ops/p230-tt-window.py.txt من patch_template.py + block.js (النسخة v1 المطبّقة بالسيرفر؛ التحديثات بـp230c)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
blk = open(os.path.join(H, "block_v1.js"), encoding="utf-8").read().rstrip("\n")
t = open(os.path.join(H, "patch_template.py"), encoding="utf-8").read()
assert t.count("@@BLOCK@@") == 1 and "'''" not in blk
open(os.path.join(H, "..", "ops", "p230-tt-window.py.txt"), "w", encoding="utf-8").write(t.replace("@@BLOCK@@", blk))
print("built")
