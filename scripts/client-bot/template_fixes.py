#!/usr/bin/env python3
"""Build update_workflow operations that remove owner/template-specific data and known defects
from a COPY of the client template.  Usage:

  python3 template_fixes.py DETAILS_JSON OUT_PREFIX      # writes OUT_PREFIX.<n>.json (<=100 ops each)

Every code patch asserts that the text it replaces exists, so a template that already
changed fails loudly instead of being half-patched.
"""
import json, re, sys, collections

det = json.load(open(sys.argv[1]))
prefix = sys.argv[2]
w = det['workflow']
N = {n['name']: n for n in w['nodes']}
C = w['connections']
ops = []

def must_replace(s, old, new, where):
    if old not in s:
        sys.exit(f"PATCH FAILED in {where}: text not found: {old[:60]!r}")
    return s.replace(old, new)

# 1) dead nodes (not reachable from any trigger/webhook), never referenced by live nodes
adj = collections.defaultdict(set)
for s, v in C.items():
    for t, outs in v.items():
        for o in outs:
            for c in (o or []):
                adj[s].add(c['node'])
roots = [n['name'] for n in w['nodes'] if 'rigger' in n['type'] or n['type'].endswith('.webhook')]
seen, st = set(roots), list(roots)
while st:
    x = st.pop()
    for y in adj[x]:
        if y not in seen:
            seen.add(y); st.append(y)
sub = {s for s, v in C.items() if any(t.startswith('ai_') for t in v)}
dead = [n for n in N if n not in seen and n not in sub
        and not N[n]['type'].endswith('stickyNote') and not N[n]['type'].startswith('@n8n')]
for d in dead:
    ops.append({"type": "removeNode", "nodeName": d})

# 2) retry on every GET request (reads are safe to repeat)
for n in w['nodes']:
    if n['name'] in dead: continue
    if n['type'].endswith('httpRequest') and n['parameters'].get('method', 'GET') == 'GET':
        ops.append({"type": "setNodeSettings", "nodeName": n['name'],
                    "settings": {"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}})

# 3) invalid parameter combination
p = dict(N['TikTok: تنزيل الفيديو']['parameters']); p.pop('genericAuthType', None)
ops.append({"type": "updateNodeParameters", "nodeName": 'TikTok: تنزيل الفيديو', "replace": True, "parameters": p})

# 4) owner data inside code / prompts
GENERIC = "ما لقيت هوية تيك توك مرتبطة بهذا الحساب الإعلاني. اربط هوية (Business Center) بالحساب أو ابعث كود تفويض الفيديو."
nm = 'TikTok: تجهيز بيانات الحملة'
c = N[nm]['parameters']['jsCode']
a = c.index("const identityBcId = ")
b = c.index("const rawIdentity = ")
c = c[:a] + c[b:]
a = c.index("if (!identity && !idList.length) {")
b = c.index("let tiktokBudgetError = '';")
c = c[:a] + c[b:]
c = must_replace(c, "const offerCardByAdvertiser = { '7610439153943314433': '7641714026573007879' };", "const offerCardByAdvertiser = {};", nm)
c = must_replace(c, "(identity && identity.bc) || identityBcId", "(identity && identity.bc) || ''", nm)
c = must_replace(c, "عندك 3 حسابات: boostpro7، شركة الجود، محمد امين.", GENERIC, nm)
ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/jsCode", "value": c})

OWNER_PHONES = ('07741536361', '07811317191')   # real numbers used as examples inside prompts/messages
EXAMPLE_PHONE = '07701234567'
OWNER_PHONE = OWNER_PHONES[0]
GENERIC = "ما لقيت هوية تيك توك مرتبطة بهذا الحساب الإعلاني. اربط هوية (Business Center) بالحساب أو ابعث كود تفويض الفيديو."
nm = 'TikTok: وضع واتساب'
c = N[nm]['parameters']['jsCode']
c = must_replace(c, "'عندك 3 حسابات: boostpro7، شركة الجود، محمد امين.'", "'" + GENERIC + "'", nm)
c = c.replace(OWNER_PHONE, EXAMPLE_PHONE)
ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/jsCode", "value": c})

nm = 'TikTok: صفحة هبوط بالاسم'
c = N[nm]['parameters']['jsCode']
a = c.index("const SITES = [")
b = c.index("];", a) + 2
c = c[:a] + "const SITES = [];" + c[b:]
c = must_replace(c, "عندك 3 حسابات: boostpro7، شركة الجود، محمد امين. رد باسم الحساب اللي تريد.", GENERIC, nm)
ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/jsCode", "value": c})

nm = 'AI Agent - فهم الأمر'
opt = N[nm]['parameters']['options']
sm = opt['systemMessage']
sm = must_replace(sm, "الحسابات المتوفرة: boostpro7، شركة الجود، محمد امين.", "الهويات المتوفرة تُجلب تلقائياً من حساب العميل؛ اكتب الاسم كما قاله المستخدم.", nm)
for ph in OWNER_PHONES:
    sm = sm.replace(ph, EXAMPLE_PHONE).replace(ph[1:], EXAMPLE_PHONE[1:])
ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/options/systemMessage", "value": sm})

nm = 'ميتا: تجهيز'
c = N[nm]['parameters']['jsCode']
c = must_replace(c, '07811317191', EXAMPLE_PHONE, nm)
c = must_replace(c, 'يعطي حساب Mohammed Amin (صاحب التوكن) صلاحية', 'يعطي حساب صاحب التوكن (المستخدم المربوط بالبوت) صلاحية', nm)
ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/jsCode", "value": c})

# 5) TikTok BC balance belongs to the agency: never answer it inside a client bot
nm = 'طلب رصيد تيك توك؟'
cond = json.dumps(N[nm]['parameters']['conditions'], ensure_ascii=False)
cond = must_replace(cond, "$('قراءة رسالة تليجرام').first().json.from === '2076853250' &&", "false &&", nm)
pp = dict(N[nm]['parameters']); pp['conditions'] = json.loads(cond)
ops.append({"type": "updateNodeParameters", "nodeName": nm, "replace": True, "parameters": pp})

# 6) per-client chat id becomes an explicit placeholder (replaced by provision.py, flagged by verify_clean.py)
PH = "__CLIENT_CHAT_ID__"
for nm in ['سقف ميتا: إرسال', 'ميتا+: إرسال']:
    ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/chatId", "value": "={{ String('%s') }}" % PH})
ops.append({"type": "setNodeParameter", "nodeName": 'حالة الحساب: إرسال', "path": "/chatId", "value": PH})
for nm in ['تقرير الأداء: إرسال التقرير', 'تنبيه رصيد: إرسال', 'سقف التكلفة: إرسال']:
    ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/chatId", "value": "={{ '%s' }}" % PH})

# 7) webhook paths become placeholders (provision.py writes a unique value per client)
for nm, ph in [('استقبال TikTok OAuth', '__TT_OAUTH_PATH__'), ('استقبال Facebook OAuth', '__FB_OAUTH_PATH__'), ('استقبال واتساب (Webhook)', '__WA_PATH__')]:
    ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/path", "value": ph})

# 8) media: no bot token inside a URL. Telegram files are served through this workflow's own webhook
#    (credential-based download) and the URL only carries the file_id.
tg_cred = N['Telegram: جلب مسار الملف']['credentials']['telegramApi']
bx, by = N['بناء رابط الوسائط']['position']
ops.append({"type": "addNode", "node": {"name": "وسيط الوسائط: استقبال", "type": "n8n-nodes-base.webhook", "typeVersion": 2.1,
    "position": [bx, by + 400],
    "parameters": {"httpMethod": "GET", "path": "media-__MEDIA_KEY__", "authentication": "none", "responseMode": "responseNode", "options": {}}}})
ops.append({"type": "addNode", "node": {"name": "وسيط الوسائط: تنزيل", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
    "position": [bx + 300, by + 400],
    "parameters": {"resource": "file", "operation": "get", "fileId": "={{ $json.query.fid }}", "download": True},
    "credentials": {"telegramApi": tg_cred}}})
ops.append({"type": "addNode", "node": {"name": "وسيط الوسائط: رد", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5,
    "position": [bx + 600, by + 400],
    "parameters": {"respondWith": "binary", "responseDataSource": "automatically", "options": {}}}})
ops.append({"type": "addConnection", "source": "وسيط الوسائط: استقبال", "target": "وسيط الوسائط: تنزيل"})
ops.append({"type": "addConnection", "source": "وسيط الوسائط: تنزيل", "target": "وسيط الوسائط: رد"})
nm = 'بناء رابط الوسائط'
c = N[nm]['parameters']['jsCode']
c = re.sub(r"const BOT_TOKEN = '[^']*';\n", "", c)
c = must_replace(c, "const mediaUrl = filePath ? `https://api.telegram.org/file/bot${BOT_TOKEN}/${filePath}` : '';",
 "const fid = String(parsed.mediaFileId || (fileResult && fileResult.result && fileResult.result.file_id) || '');\n"
 "const N8N_HOST = 'https://n8n.srv2007124.hstgr.cloud';\n"
 "const fname = filePath ? String(filePath).split('/').pop() : '';\n"
 "const mediaUrl = (filePath && fid) ? `${N8N_HOST}/webhook/media-__MEDIA_KEY__?fid=${encodeURIComponent(fid)}&f=${encodeURIComponent(fname)}` : '';", nm)
ops.append({"type": "setNodeParameter", "nodeName": nm, "path": "/jsCode", "value": c})

for i in range(0, len(ops), 100):
    json.dump(ops[i:i+100], open(f"{prefix}.{i//100}.json", 'w'), ensure_ascii=False, separators=(',', ':'))
print(f"dead={len(dead)} ops={len(ops)} batches={(len(ops)+99)//100}", file=sys.stderr)
