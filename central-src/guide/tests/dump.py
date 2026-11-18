import importlib.util, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("gd_pages", os.path.join(ROOT, "pages.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class W:
    def __init__(self): self.nodes = []; self.links = []
    def add(self, name, type_, ver, params, creds=None, **k): self.nodes.append({"name": name, "type": type_, "parameters": params}); return name
    def link(self, a, b, out=0): self.links.append((a, b, out))
    def chain(self, *n):
        for a, b in zip(n, n[1:]): self.link(a, b)
class B:
    def code(self, w, name, js): return w.add(name, "code", 2, {"jsCode": js})
w = W(); b = B()
def reply(name, js): n = b.code(w, name, js); w.link(n, "Prep send"); return n
m.build(b, w, "Command", 36, reply, {"id": "c"})
nodes = {n["name"]: n["parameters"] for n in w.nodes}
json.dump({"render": nodes["GD: render"]["jsCode"], "reply": nodes["GD: reply"]["jsCode"], "links": w.links}, open(os.environ.get("GD_NODES", "/tmp/gd_nodes.json"), "w"), ensure_ascii=False)
print("nodes:", len(nodes), "links:", w.links)
