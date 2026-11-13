"""يستخرج نصوص JS الحقيقية للعقد من smart_audience/pages.py + يتحقق من بناء الربط بين العقد (builder وهمي). يكتب /tmp/sa_nodes.json"""
import importlib.util, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sa_pages", os.path.join(ROOT, "pages.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class W:
    def __init__(self): self.nodes = []; self.links = []
    def add(self, name, type_, ver, params, creds=None, **k): self.nodes.append({"name": name, "type": type_, "parameters": params}); return name
    def link(self, a, b, out=0): self.links.append((a, b, out))
    def chain(self, *n):
        for a, b in zip(n, n[1:]): self.link(a, b)


class B:
    def __init__(self, w): self.w = w
    def code(self, w, name, js): return w.add(name, "code", 2, {"jsCode": js})
    def pg(self, w, name, sql, qr, cred, always=False): return w.add(name, "postgres", 2, {"query": sql, "queryReplacement": qr})
    def call_broker(self, w, name, mode="once"): return w.add(name, "executeWorkflow", 1, {"mode": mode})


w = W(); b = B(w); sw = "Command"
def reply(name, js): n = b.code(w, name, js); w.link(n, "Prep send"); return n
m.build(b, w, sw, 33, reply, {"id": "c"})
nodes = {n["name"]: n["parameters"] for n in w.nodes}
json.dump({"plan": nodes["SA: plan"]["jsCode"], "render": nodes["SA: render"]["jsCode"], "sql": nodes["SA: data"]["query"], "save_sql": nodes["SA: save state + cache"]["query"], "save_qr": nodes["SA: save state + cache"]["queryReplacement"], "reply": nodes["SA: reply"]["jsCode"], "data_qr": nodes["SA: data"]["queryReplacement"],
           "links": w.links, "names": list(nodes)}, open("/tmp/sa_nodes.json", "w"), ensure_ascii=False)
print("nodes:", len(nodes), "links:", len(w.links))
