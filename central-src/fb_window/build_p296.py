import os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
T = open(os.path.join(H, "patch_template.py"), encoding="utf-8").read()
B = open(os.path.join(H, "block.js"), encoding="utf-8").read().rstrip("\n")
assert "'''" not in B
body = T.replace("@@BLOCK@@", B)
open(os.path.join(H, "..", "ops", "p296-fb-window.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: ingress p296=$(grep -c p296 n8n/wf_ingress.py) metaflow p296=$(grep -c p296 broker/app/metaflow.py) (expect >=1 each)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p296s.txt"), "w").write(line)
print(len(line))
