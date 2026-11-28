import os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda f: open(os.path.join(H, f), encoding="utf-8").read()
import re
v3 = rd("block_v3.js"); v4 = rd("block.js")
pick = lambda t: [l for l in t.split("\n") if l.startswith("  const to24 = ")]
o, n = pick(v3), pick(v4); assert len(o) == 1 and len(n) == 1
t = rd("patch_e_template.py").replace("@@OLD@@", o[0].strip()).replace("@@NEW@@", n[0].strip())
assert "'''" not in o[0] and "'''" not in n[0]
open(os.path.join(H, "..", "ops", "p230e-tt-window-night.py.txt"), "w", encoding="utf-8").write(t)
b = base64.b64encode(lzma.compress(t.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: ingress p230e=$(grep -c p230e n8n/wf_ingress.py) (expect >=1)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p230es.txt"), "w").write(line); print(len(line))
