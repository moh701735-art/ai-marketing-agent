import json, sys
# usage: gen2.py cfg.json out.json [refactor]
cfg = json.load(open(sys.argv[1])); refactor = len(sys.argv) > 3
CORE = cfg.get('core', 'cvLbTQe0UQSVkHFt')
EX = cfg.get('extract', 'استخراج نتيجة الـAI1'); SAVE = cfg.get('save', 'حفظ النتيجة'); NEXT = cfg.get('next', 'وقف: استخراج الاسم')
tbl = {'__rl': True, 'mode': 'id', 'value': cfg['table']}
COLS = ['sid','phone','client','platform','advertiser_id','campaign_id','campaign_name','action','repeat','time','run_date','last_run_date','status','last_result','created_at']
def upsert(name, pos):
    return {'name': name, 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': pos, 'onError': 'continueRegularOutput', 'parameters': {
        'operation': 'upsert', 'dataTableId': tbl, 'filters': {'conditions': [{'keyName': 'sid', 'condition': 'eq', 'keyValue': '={{ $json.sid }}'}]},
        'columns': {'mappingMode': 'defineBelow', 'matchingColumns': [], 'value': {c: '={{ $json.%s ?? "" }}' % c for c in COLS}, 'attemptToConvertTypes': False, 'convertFieldsToString': False}, 'options': {}}}
def tg(name, pos, chat):
    n = {'name': name, 'type': 'n8n-nodes-base.telegram', 'typeVersion': 1.2, 'position': pos, 'onError': 'continueRegularOutput', 'parameters': {
        'additionalFields': {'appendAttribution': False, 'parse_mode': 'HTML'}, 'chatId': chat, 'operation': 'sendMessage', 'resource': 'message',
        'text': "={{ String($json.finalMessage ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}"}}
    if cfg.get('tg'): n['credentials'] = {'telegramApi': cfg['tg']}
    return n
iff = lambda name, pos, expr: {'name': name, 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': pos, 'parameters': {'conditions': {
    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
    'conditions': [{'id': 'c1', 'leftValue': '={{ %s }}' % expr, 'rightValue': True, 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'}, 'options': {}}}
cd = lambda name, pos, js: {'name': name, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': pos, 'parameters': {'jsCode': js}}
ew = lambda name, pos: {'name': name, 'type': 'n8n-nodes-base.executeWorkflow', 'typeVersion': 1.3, 'position': pos, 'parameters': {'mode': 'once', 'source': 'database', 'workflowId': {'__rl': True, 'mode': 'id', 'value': CORE}, 'options': {}}}
J_INTAKE = "const ai=$('استخراج نتيجة الـAI1').first().json, ctx=$('تجهيز سياق الـAI').first().json;\nlet clients=[]; try{clients=$('جلب العملاء (للـAI)').all().map(i=>i.json)}catch(e){}\nreturn [{json:{mode:'intake',ai,chat:String($('قراءة رسالة تليجرام').first().json.chatId||''),from:ctx.from,camps:ctx.campaignHistory||[],existing:$('جدولة: الأحداث الحالية').all().map(i=>i.json),clients}}];"
J_HOOK = "const ctx=$('تحقق قبل التنفيذ').first().json;\nif(ctx.action!=='create'||!(Array.isArray(ctx.schedule)&&ctx.schedule.length)) return [];\nreturn [{json:{mode:'hook',ctx,saved:$json,chat:String($('قراءة رسالة تليجرام').first().json.chatId||'')}}];"
J_AGG = "return [{json:{finalMessage:$('جدولة: المحرك').first().json.finalMessage||''}}];"
J_DUE = "return [{json:{mode:'due',rows:$input.all().map(i=>i.json)}}];"
J_RES = lambda q: "const src=$('%s').all(0);\nreturn [{json:{mode:'result',items:$input.all().map((it,i)=>{const pi=it.pairedItem,k=(pi&&typeof pi.item==='number')?pi.item:i;return {r:(src[k]&&src[k].json)||{},j:it.json||{}}})}}];" % q
J_SKIP = "return [{json:{mode:'result',items:$input.all().map(it=>({r:it.json,j:{}}))}}];"
http_tt = {'name': 'جدولة: TikTok', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [1500, 7200], 'onError': 'continueRegularOutput', 'parameters': {
    'method': 'POST', 'url': 'https://business-api.tiktok.com/open_api/v1.3/campaign/status/update/', 'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
    'sendBody': True, 'specifyBody': 'json', 'jsonBody': "={{ JSON.stringify({ advertiser_id: $json.advertiser_id, campaign_ids: [$json.campaign_id], operation_status: $json.action === 'on' ? 'ENABLE' : 'DISABLE' }) }}", 'options': {}},
    'credentials': {'httpHeaderAuth': cfg['tiktok']}}
http_fb = {'name': 'جدولة: Meta', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [1500, 7400], 'onError': 'continueRegularOutput', 'parameters': {
    'method': 'POST', 'url': '=https://graph.facebook.com/v20.0/{{$json.campaign_id}}', 'authentication': 'predefinedCredentialType', 'nodeCredentialType': 'facebookGraphApi',
    'sendBody': True, 'specifyBody': 'json', 'jsonBody': "={{ JSON.stringify({ status: $json.action === 'on' ? 'ACTIVE' : 'PAUSED' }) }}", 'options': {}},
    'credentials': {'facebookGraphApi': cfg['fb']}}
C = lambda s, t, si=0: {'type': 'addConnection', 'source': s, 'target': t, 'sourceIndex': si, 'targetIndex': 0}
R = lambda s, t: {'type': 'removeConnection', 'source': s, 'target': t}
SET = lambda n, js: {'type': 'setNodeParameter', 'nodeName': n, 'path': '/jsCode', 'value': js}
ADD = lambda n: {'type': 'addNode', 'node': n}
ops = []
E1, E2, E3 = 'جدولة: المحرك', 'جدولة: محرك المستحق', 'جدولة: محرك النتائج'
if refactor:
    ops += [SET('جدولة: معالجة الطلب', J_INTAKE), SET('جدولة: ربط الإنشاء', J_HOOK), SET('جدولة: تجميع الرد', J_AGG), SET('جدولة: المستحق', J_DUE),
            SET('جدولة: نتيجة TikTok', J_RES('جدولة: تيك توك؟')), SET('جدولة: نتيجة Meta', J_RES('جدولة: ميتا؟')), SET('جدولة: نتيجة تخطي', J_SKIP),
            ADD(ew(E1, [800, 3100])), ADD(ew(E2, [800, 7200])), ADD(ew(E3, [1800, 7300])),
            R('جدولة: معالجة الطلب', 'جدولة: صف؟'), C('جدولة: معالجة الطلب', E1), C(E1, 'جدولة: صف؟'),
            R('جدولة: ربط الإنشاء', 'جدولة: حفظ'), C('جدولة: ربط الإنشاء', E1),
            R('جدولة: المستحق', 'جدولة: تيك توك؟'), C('جدولة: المستحق', E2), C(E2, 'جدولة: تيك توك؟')]
    for r in ['جدولة: نتيجة TikTok', 'جدولة: نتيجة Meta', 'جدولة: نتيجة تخطي']:
        ops += [R(r, 'جدولة: حفظ التنفيذ'), R(r, 'جدولة: إشعار؟'), C(r, E3)]
    ops += [C(E3, 'جدولة: حفظ التنفيذ'), C(E3, 'جدولة: إشعار؟')]
else:
    nodes = [iff('جدولة؟', [200, 3280], "['schedule','schedule_cancel','schedule_list'].includes($json.action)"),
        {'name': 'جدولة: الأحداث الحالية', 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': [440, 3100], 'parameters': {'operation': 'get', 'dataTableId': tbl, 'returnAll': True}, 'executeOnce': True, 'alwaysOutputData': True},
        cd('جدولة: معالجة الطلب', [680, 3100], J_INTAKE), ew(E1, [800, 3100]), iff('جدولة: صف؟', [920, 3100], "$json.kind === 'row'"),
        upsert('جدولة: حفظ', [1160, 3000]), cd('جدولة: تجميع الرد', [1400, 3000], J_AGG), tg('جدولة: رد', [1640, 3100], "={{ $('قراءة رسالة تليجرام').first().json.chatId }}"),
        cd('جدولة: ربط الإنشاء', [9420, 1500], J_HOOK),
        {'name': 'جدولة: كل 5 دقائق', 'type': 'n8n-nodes-base.scheduleTrigger', 'typeVersion': 1.4, 'position': [200, 7200], 'parameters': {'rule': {'interval': [{'field': 'minutes', 'minutesInterval': 5}]}}},
        {'name': 'جدولة: قراءة الأحداث', 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': [440, 7200], 'parameters': {'operation': 'get', 'dataTableId': tbl, 'returnAll': True}},
        cd('جدولة: المستحق', [680, 7200], J_DUE), ew(E2, [800, 7200]),
        iff('جدولة: تيك توك؟', [1000, 7200], "$json.api === 'apply' && $json.platform === 'tiktok'"), iff('جدولة: ميتا؟', [1000, 7400], "$json.api === 'apply' && $json.platform === 'meta'"),
        http_tt, http_fb,
        cd('جدولة: نتيجة TikTok', [1640, 7200], J_RES('جدولة: تيك توك؟')), cd('جدولة: نتيجة Meta', [1640, 7400], J_RES('جدولة: ميتا؟')), cd('جدولة: نتيجة تخطي', [1200, 7600], J_SKIP),
        ew(E3, [1800, 7300]), upsert('جدولة: حفظ التنفيذ', [2000, 7300]), iff('جدولة: إشعار؟', [2000, 7500], "$json.notify === true"), tg('جدولة: إشعار', [2200, 7500], "={{ $json.phone }}")]
    ops += [ADD(n) for n in nodes]
    ops += [R(EX, NEXT), C(EX, 'جدولة؟'), C('جدولة؟', 'جدولة: الأحداث الحالية'), C('جدولة؟', NEXT, 1),
        C('جدولة: الأحداث الحالية', 'جدولة: معالجة الطلب'), C('جدولة: معالجة الطلب', E1), C(SAVE, 'جدولة: ربط الإنشاء'), C('جدولة: ربط الإنشاء', E1),
        C(E1, 'جدولة: صف؟'), C('جدولة: صف؟', 'جدولة: حفظ'), C('جدولة: صف؟', 'جدولة: رد', 1), C('جدولة: حفظ', 'جدولة: تجميع الرد'), C('جدولة: تجميع الرد', 'جدولة: رد'),
        C('جدولة: كل 5 دقائق', 'جدولة: قراءة الأحداث'), C('جدولة: قراءة الأحداث', 'جدولة: المستحق'), C('جدولة: المستحق', E2), C(E2, 'جدولة: تيك توك؟'),
        C('جدولة: تيك توك؟', 'جدولة: TikTok'), C('جدولة: تيك توك؟', 'جدولة: ميتا؟', 1), C('جدولة: ميتا؟', 'جدولة: Meta'), C('جدولة: ميتا؟', 'جدولة: نتيجة تخطي', 1),
        C('جدولة: TikTok', 'جدولة: نتيجة TikTok'), C('جدولة: Meta', 'جدولة: نتيجة Meta')]
    for r in ['جدولة: نتيجة TikTok', 'جدولة: نتيجة Meta', 'جدولة: نتيجة تخطي']: ops.append(C(r, E3))
    ops += [C(E3, 'جدولة: حفظ التنفيذ'), C(E3, 'جدولة: إشعار؟'), C('جدولة: إشعار؟', 'جدولة: إشعار')]
json.dump(ops, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(ops), len(open(sys.argv[2]).read()))
