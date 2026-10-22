import json, sys, subprocess
live, table, out = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(live)); w = d.get('workflow', d); nodes = w['nodes']
g = lambda k: [x for x in nodes if x['name'] == k][0]
def cred(node, key):
    c = (g(node).get('credentials') or {}).get(key)
    return c
cfg = {'table': table,
       'tiktok': cred('TikTok: إيقاف حملة', 'httpHeaderAuth'),
       'fb': cred('Meta: إيقاف حملة', 'facebookGraphApi'),
       'tg': cred('الرد النهائي على واتساب', 'telegramApi') or cred('سقف التكلفة: إرسال', 'telegramApi')}
print(json.dumps(cfg, ensure_ascii=False))
json.dump(cfg, open(out + '.cfg.json', 'w'), ensure_ascii=False)
subprocess.check_call(['python3', 'gen2.py', out + '.cfg.json', out + '.main.json'])
sm = g('AI Agent - فهم الأمر')['parameters']['options']['systemMessage']
assert 'schedule_cancel' not in sm
blk = open('prompt_block.txt').read()
ps = g('مخطط إخراج JSON')['parameters']['jsonSchemaExample']
ps2 = ps.replace('"start_time"', '"schedule": [{"action": "on", "time": "10:00", "repeat": "once", "day": ""}], "start_time"', 1); json.loads(ps2)
ex = g('استخراج نتيجة الـAI1')['parameters']['jsCode']
ex2 = ex.replace("tiktok_auth_codes: [], general_reply", "tiktok_auth_codes: [], schedule: [], general_reply", 1)
ex2 = ex2.replace("const txt = String(incoming.text || '');", "const txt = String(incoming.text || '');\n  if (result.action === 'create' && !(Array.isArray(result.schedule) && result.schedule.length) && prev && Array.isArray(prev.schedule)) result.schedule = prev.schedule;", 1)
ex2 = ex2.replace("return [{ json: result }];", "if (!Array.isArray(result.schedule)) result.schedule = [];\nreturn [{ json: result }];", 1)
assert ex2.count('schedule') >= 4, 'extract patch failed'
ops = [{'type': 'setNodeParameter', 'nodeName': 'مخطط إخراج JSON', 'path': '/jsonSchemaExample', 'value': ps2},
       {'type': 'setNodeParameter', 'nodeName': 'AI Agent - فهم الأمر', 'path': '/options/systemMessage', 'value': sm.rstrip() + blk},
       {'type': 'setNodeParameter', 'nodeName': 'استخراج نتيجة الـAI1', 'path': '/jsCode', 'value': ex2}]
json.dump(ops, open(out + '.ai.json', 'w'), ensure_ascii=False, separators=(',', ':'))
m = json.load(open(out + '.main.json'))
json.dump(m, open(out + '.main.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(open(out + '.main.json').read()), len(open(out + '.ai.json').read()))
