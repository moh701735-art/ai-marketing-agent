#!/usr/bin/env python3
"""يبني ops/p250-radar-wiring.py.txt من patch_wire_template.py + pages.py (PAGES كنص ثابت)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
pages = open(os.path.join(H, "..", "pages.py"), encoding="utf-8").read()
t = open(os.path.join(H, "patch_wire_template.py"), encoding="utf-8").read()
assert t.count("@@PAGES@@") == 1
open(os.path.join(H, "..", "..", "ops", "p250-radar-wiring.py.txt"), "w", encoding="utf-8").write(t.replace("@@PAGES@@", repr(pages)))
print("built")
