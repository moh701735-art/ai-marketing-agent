import json, sys, re
cfg = json.load(open(sys.argv[1]))
rd = lambda f: open(f).read()
LIB = rd('lib.js')
def code(f, **kw):
    s = rd(f).replace('//__LIB__\n', LIB + '\n')
    for k, v in kw.items(): s = s.replace(k, v)
    return s
EX = cfg.get('extract', 'استخراج نتيجة الـAI1')
SAVE = cfg.get('save', 'حفظ النتيجة')
NEXT = cfg.get('next', 'وقف: استخراج الاسم')
T = cfg['table']
tbl = {'__rl': True, 'mode': 'id', 'value': T}
COLS = ['sid','phone','client','platform','advertiser_id','campaign_id','campaign_name','action','repeat','time','run_date','last_run_date','status','last_result','created_at']
def upsert(name, pos):
    return {'name': name, 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': pos, 'parameters': {
        'operation': 'upsert', 'dataTableId': tbl,
        'filters': {'conditions': [{'keyName': 'sid', 'condition': 'eq', 'keyValue': '={{ $json.sid }}'}]},
        'columns': {'mappingMode': 'defineBelow', 'matchingColumns': [], 'value': {c: '={{ $json.%s ?? "" }}' % c for c in COLS}, 'attemptToConvertTypes': False, 'convertFieldsToString': False}, 'options': {}}, 'onError': 'continueRegularOutput'}
tg = lambda name, pos, chat, text: {'name': name, 'type': 'n8n-nodes-base.telegram', 'typeVersion': 1.2, 'position': pos, 'parameters': {
    'additionalFields': {'appendAttribution': False, 'parse_mode': 'HTML'}, 'chatId': chat, 'operation': 'sendMessage', 'resource': 'message', 'text': text},
    'credentials': {'telegramApi': cfg['tg']}, 'onError': 'continueRegularOutput'}
ESC = "={{ String($json.finalMessage ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}"
iff = lambda name, pos, expr: {'name': name, 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': pos, 'parameters': {'conditions': {
    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
    'conditions': [{'id': 'c1', 'leftValue': '={{ %s }}' % expr, 'rightValue': True, 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'}, 'options': {}}}
cd = lambda name, pos, js: {'name': name, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': pos, 'parameters': {'jsCode': js}}
http_tt = {'name': 'جدولة: TikTok', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [1400, 7200], 'onError': 'continueRegularOutput', 'parameters': {
    'method': 'POST', 'url': 'https://business-api.tiktok.com/open_api/v1.3/campaign/status/update/', 'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
    'sendBody': True, 'specifyBody': 'json', 'jsonBody': "={{ JSON.stringify({ advertiser_id: $json.advertiser_id, campaign_ids: [$json.campaign_id], operation_status: $json.action === 'on' ? 'ENABLE' : 'DISABLE' }) }}", 'options': {}},
    'credentials': {'httpHeaderAuth': cfg['tiktok']}}
http_fb = {'name': 'جدولة: Meta', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [1400, 7400], 'onError': 'continueRegularOutput', 'parameters': {
    'method': 'POST', 'url': '=https://graph.facebook.com/v20.0/{{$json.campaign_id}}', 'authentication': 'predefinedCredentialType', 'nodeCredentialType': 'facebookGraphApi',
    'sendBody': True, 'specifyBody': 'json', 'jsonBody': "={{ JSON.stringify({ status: $json.action === 'on' ? 'ACTIVE' : 'PAUSED' }) }}", 'options': {}},
    'credentials': {'facebookGraphApi': cfg['fb']}}
agg = "let m = '';\nfor (const n of ['جدولة: معالجة الطلب', 'جدولة: ربط الإنشاء']) { try { const f = $(n).first(); if (f && f.json.finalMessage) { m = f.json.finalMessage; break; } } catch (e) {} }\nreturn [{ json: { finalMessage: m } }];"
nodes = [
  iff('جدولة؟', [200, 3280], "['schedule','schedule_cancel','schedule_list'].includes($json.action)"),
  {'name': 'جدولة: الأحداث الحالية', 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': [440, 3100], 'parameters': {'operation': 'get', 'dataTableId': tbl, 'returnAll': True}, 'executeOnce': True, 'alwaysOutputData': True},
  cd('جدولة: معالجة الطلب', [680, 3100], code('intake.js')),
  iff('جدولة: صف؟', [920, 3100], "$json.kind === 'row'"),
  upsert('جدولة: حفظ', [1160, 3000]),
  cd('جدولة: تجميع الرد', [1400, 3000], agg),
  tg('جدولة: رد', [1640, 3100], "={{ $('قراءة رسالة تليجرام').first().json.chatId }}", ESC),
  cd('جدولة: ربط الإنشاء', [9420, 1500], code('hook.js')),
  # executor
  {'name': 'جدولة: كل 5 دقائق', 'type': 'n8n-nodes-base.scheduleTrigger', 'typeVersion': 1.4, 'position': [200, 7200], 'parameters': {'rule': {'interval': [{'field': 'minutes', 'minutesInterval': 5}]}}},
  {'name': 'جدولة: قراءة الأحداث', 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': [440, 7200], 'parameters': {'operation': 'get', 'dataTableId': tbl, 'returnAll': True}},
  cd('جدولة: المستحق', [680, 7200], code('due.js')),
  iff('جدولة: تيك توك؟', [920, 7200], "$json.api === 'apply' && $json.platform === 'tiktok'"),
  iff('جدولة: ميتا؟', [920, 7400], "$json.api === 'apply' && $json.platform === 'meta'"),
  http_tt, http_fb,
  cd('جدولة: نتيجة TikTok', [1640, 7200], code('result.js', **{'__SRC__': "$('جدولة: تيك توك؟').all(0)"})),
  cd('جدولة: نتيجة Meta', [1640, 7400], code('result.js', **{'__SRC__': "$('جدولة: ميتا؟').all(0)"})),
  cd('جدولة: نتيجة تخطي', [1160, 7600], code('result.js', **{'__SRC__': "null"})),
  upsert('جدولة: حفظ التنفيذ', [1880, 7300]),
  iff('جدولة: إشعار؟', [1880, 7500], "$json.notify === true"),
  tg('جدولة: إشعار', [2120, 7500], "={{ $json.phone }}", ESC),
]
ops = [{'type': 'addNode', 'node': n} for n in nodes]
# set credentials via node (already inside); wire
C = lambda s, t, si=0, ti=0: {'type': 'addConnection', 'source': s, 'target': t, 'sourceIndex': si, 'targetIndex': ti}
ops += [
  {'type': 'removeConnection', 'source': EX, 'target': NEXT},
  C(EX, 'جدولة؟'), C('جدولة؟', 'جدولة: الأحداث الحالية', 0), C('جدولة؟', NEXT, 1),
  C('جدولة: الأحداث الحالية', 'جدولة: معالجة الطلب'), C('جدولة: معالجة الطلب', 'جدولة: صف؟'),
  C('جدولة: صف؟', 'جدولة: حفظ', 0), C('جدولة: صف؟', 'جدولة: رد', 1),
  C('جدولة: حفظ', 'جدولة: تجميع الرد'), C('جدولة: تجميع الرد', 'جدولة: رد'),
  C(SAVE, 'جدولة: ربط الإنشاء'), C('جدولة: ربط الإنشاء', 'جدولة: حفظ'),
  C('جدولة: كل 5 دقائق', 'جدولة: قراءة الأحداث'), C('جدولة: قراءة الأحداث', 'جدولة: المستحق'), C('جدولة: المستحق', 'جدولة: تيك توك؟'),
  C('جدولة: تيك توك؟', 'جدولة: TikTok', 0), C('جدولة: تيك توك؟', 'جدولة: ميتا؟', 1),
  C('جدولة: ميتا؟', 'جدولة: Meta', 0), C('جدولة: ميتا؟', 'جدولة: نتيجة تخطي', 1),
  C('جدولة: TikTok', 'جدولة: نتيجة TikTok'), C('جدولة: Meta', 'جدولة: نتيجة Meta'),
]
for r in ['جدولة: نتيجة TikTok', 'جدولة: نتيجة Meta', 'جدولة: نتيجة تخطي']:
    ops += [C(r, 'جدولة: حفظ التنفيذ'), C(r, 'جدولة: إشعار؟')]
ops.append(C('جدولة: إشعار؟', 'جدولة: إشعار', 0))
json.dump(ops, open(sys.argv[2], 'w'), ensure_ascii=False)
print(len(ops), 'ops', len(json.dumps(ops, ensure_ascii=False)), 'chars')
