import importlib.util, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sn_wiz", os.path.join(ROOT, "wizard.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class W:
    def __init__(self): self.nodes = []; self.links = []
    def add(self, name, type_, ver, params, creds=None, **k): self.nodes.append({"name": name, "type": type_, "parameters": params}); return name
    def link(self, a, b, out=0): self.links.append((a, b, out))
    def chain(self, *n):
        for a, b in zip(n, n[1:]): self.link(a, b)
class B:
    def code(self, w, name, js): return w.add(name, "code", 2, {"jsCode": js})
    def pg(self, w, name, sql, qr, cred, always=False): return w.add(name, "postgres", 2, {"query": sql, "queryReplacement": qr})
    def call_broker(self, w, name, mode="once"): return w.add(name, "executeWorkflow", 1, {"mode": mode})
w = W(); b = B(); sw = "Command"
def reply(name, js): n = b.code(w, name, js); w.link(n, "Prep send"); return n
m.build(b, w, sw, 35, reply, {"id": "c"})
nodes = {n["name"]: n["parameters"] for n in w.nodes}
json.dump({"plan": nodes["SN2: plan"]["jsCode"], "render": nodes["SN2: render"]["jsCode"], "reply": nodes["SN2: reply"]["jsCode"], "sql": nodes["SN2: data"]["query"], "save": nodes["SN2: save state"]["query"], "links": w.links, "names": list(nodes)}, open("/tmp/sn2_nodes.json", "w"), ensure_ascii=False)
print("nodes:", len(nodes), "links:", len(w.links)); [print("  ", l) for l in w.links]
