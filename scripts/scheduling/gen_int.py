import json, sys
# usage: gen_int.py <live_workflow.json> <out_ops.json> [main]
INT = 'QMgcjkonCz6M8SKF'
d = json.load(open(sys.argv[1])); w = d.get('workflow', d); N = {x['name']: x for x in w['nodes']}; C = w['connections']
is_main = len(sys.argv) > 3 and sys.argv[3] == 'main'
tid = lambda k: N[k]['parameters']['dataTableId']
hist, clients = tid('جلب سجل الحملات (للذاكرة)'), tid('جلب العملاء (للـAI)')
tok = tid('TT: توكنات سقف') if is_main else None
ttcred = N['جدولة: TikTok'].get('credentials', {}).get('httpHeaderAuth')
tgc = N['جدولة: رد']['credentials']['telegramApi']
CAP = 'سقف الرسالة: أمر؟'
nxt = C[CAP]['main'][1][0]['node']
P = 'اهتمامات: '
G = 'https://business-api.tiktok.com/open_api/v1.3/'
TOKEXPR = "={{ (() => { const a = String($('اهتمامات: محرك 1').first().json.advertiser_id || '').trim(); const R = $('اهتمامات: توكنات').all().map(i => i.json).filter(r => r && r.status === 'ok' && r.access_token).sort((x, y) => String(x.created_at).localeCompare(String(y.created_at))).reverse(); const t = R.find(r => String(r.advertiser_ids || '').split(',').map(s => s.trim()).includes(a)); return t ? t.access_token : ''; })() }}"
cd = lambda name, pos, js: {'name': name, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': pos, 'parameters': {'jsCode': js}}
ew = lambda name, pos: {'name': name, 'type': 'n8n-nodes-base.executeWorkflow', 'typeVersion': 1.3, 'position': pos, 'parameters': {'mode': 'once', 'source': 'database', 'workflowId': {'__rl': True, 'mode': 'id', 'value': INT}, 'options': {}}}
iff = lambda name, pos, expr: {'name': name, 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': pos, 'parameters': {'conditions': {
    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
    'conditions': [{'id': 'c1', 'leftValue': '={{ %s }}' % expr, 'rightValue': True, 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'}, 'options': {}}}
dt = lambda name, pos, table: {'name': name, 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': pos, 'executeOnce': True, 'alwaysOutputData': True, 'parameters': {'operation': 'get', 'dataTableId': table, 'returnAll': True}}
def http(name, pos, method, url, body=None, q=None):
    p = {'method': method, 'url': url, 'options': {'batching': {'batch': {'batchSize': 1, 'batchInterval': 300}}, 'response': {'response': {'neverError': True}}}}
    if body: p.update({'sendBody': True, 'specifyBody': 'json', 'jsonBody': body})
    if q: p.update({'sendQuery': True, 'queryParameters': {'parameters': [{'name': a, 'value': b} for a, b in q]}})
    n = {'name': name, 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': pos, 'onError': 'continueRegularOutput', 'parameters': p}
    if is_main:
        p.update({'authentication': 'none', 'sendHeaders': True, 'headerParameters': {'parameters': [{'name': 'Access-Token', 'value': TOKEXPR}]}})
    else:
        p.update({'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth'}); n['credentials'] = {'httpHeaderAuth': ttcred}
    return n
IFX = "(() => { const t = String($('قراءة رسالة تليجرام').first().json.text || ''); const n = t.replace(/[\\u064b-\\u065f\\u0640]/g, '').replace(/[أإآٱ]/g, 'ا'); return /(تلغي|الغ|الغي|الغاء|احذف|تحذف|امسح|تمسح|شيل|تشيل|اشيل|يلغي|ازل|ازاله|بدون)\\s*(ال)?اهتمامات/.test(n) && t.length < 400 && !/(ارفع|سوي|انشئ|أنشئ)/.test(n); })()"
X, Y = 6000, 12400
names = ['أمر؟', 'السجل', 'العملاء', 'توكنات', 'تجهيز', 'محرك 1', 'وجدنا؟', 'جلب المجموعات', 'تجهيز التعديل', 'محرك 2', 'تعديل؟', 'تعديل', 'تحقق', 'النهاية', 'محرك 3', 'رد']
Q, H, K, T, J, E1, F1, A1, J2, E2, F2, U, V, J3, E3, R = [P + s for s in names]
ctxsel = lambda n: "$('%s').all().map(i => i.json)" % n
new = [iff(Q, [X, Y], IFX), dt(H, [X+220, Y], hist), dt(K, [X+440, Y], clients)]
if is_main: new.append(dt(T, [X+660, Y], tok))
new += [
 cd(J, [X+880, Y], "const m = $('قراءة رسالة تليجرام').first().json;\nreturn [{ json: { mode: 'intFind', text: String(m.text || ''), phone: String(m.chatId || ''), hist: $('%s').all().map(i => i.json), clients: $('%s').all().map(i => i.json) } }];" % (H, K)),
 ew(E1, [X+1100, Y]), iff(F1, [X+1320, Y], "$json.kind === 'find'"),
 http(A1, [X+1540, Y-100], 'GET', G + 'adgroup/get/', None, [('advertiser_id', '={{ $json.advertiser_id }}'), ('filtering', "={{ JSON.stringify({ campaign_ids: [$json.campaign_id] }) }}"), ('page_size', '50')]),
 cd(J2, [X+1760, Y-100], "return [{ json: { mode: 'intUpd', ctx: $('%s').first().json, ag: $input.first().json } }];" % E1),
 ew(E2, [X+1980, Y-100]), iff(F2, [X+2200, Y-100], "$json.kind === 'upd'"),
 http(U, [X+2420, Y-200], 'POST', G + 'adgroup/update/', "={{ JSON.stringify($json.body) }}"),
 http(V, [X+2640, Y-200], 'GET', G + 'adgroup/get/', None, [('advertiser_id', "={{ $('%s').all()[$itemIndex].json.advertiser_id }}" % E2), ('filtering', "={{ JSON.stringify({ adgroup_ids: [$('%s').all().filter(i => i.json.kind === 'upd')[$itemIndex].json.adgroup_id] }) }}" % E2)]),
 cd(J3, [X+2860, Y-200], "return [{ json: { mode: 'intDone', ctx: $('%s').all().map(i => i.json).filter(j => j.kind === 'upd'), ups: $('%s').all().map(i => i.json), ver: $input.all().map(i => i.json) } }];" % (E2, U)),
 ew(E3, [X+3080, Y-200]),
 {'name': R, 'type': 'n8n-nodes-base.telegram', 'typeVersion': 1.2, 'position': [X+3300, Y+100], 'onError': 'continueRegularOutput', 'parameters': {'additionalFields': {'appendAttribution': False}, 'chatId': "={{ $('قراءة رسالة تليجرام').first().json.chatId }}", 'text': '={{ $json.finalMessage }}'}, 'credentials': {'telegramApi': tgc}}]
# fix: verify node advertiser expression must not use E2 index over non-upd items
ops = [{'type': 'addNode', 'node': n} for n in new]
c = lambda s, t, si=0: {'type': 'addConnection', 'source': s, 'target': t, 'sourceIndex': si, 'targetIndex': 0}
ops += [{'type': 'removeConnection', 'source': CAP, 'target': nxt, 'sourceIndex': 1}, c(CAP, Q, 1), c(Q, nxt, 1), c(Q, H), c(H, K)]
chain = [K] + ([T] if is_main else []) + [J, E1, F1]
ops += [c(chain[i], chain[i+1]) for i in range(len(chain) - 1)]
ops += [c(F1, A1), c(F1, R, 1), c(A1, J2), c(J2, E2), c(E2, F2), c(F2, U), c(F2, R, 1), c(U, V), c(V, J3), c(J3, E3), c(E3, R)]
# the 'reply' kind from E2/E3 etc. goes to R via F2 false; E3 outputs reply items -> R
if is_main:
    nodes2 = [dt('جدولة: توكنات', [1100, 7500], tok), cd('جدولة: تمرير', [1300, 7500], "return $('جدولة: محرك المستحق').all();")]
    ops += [{'type': 'addNode', 'node': n} for n in nodes2]
    ops += [{'type': 'removeConnection', 'source': 'جدولة: محرك المستحق', 'target': 'جدولة: تيك توك؟'}, c('جدولة: محرك المستحق', 'جدولة: توكنات'), c('جدولة: توكنات', 'جدولة: تمرير'), c('جدولة: تمرير', 'جدولة: تيك توك؟')]
    ops.append({'type': 'updateNodeParameters', 'nodeName': 'جدولة: TikTok', 'parameters': {'authentication': 'none', 'sendHeaders': True, 'headerParameters': {'parameters': [{'name': 'Access-Token', 'value': "={{ (() => { const a = String($json.advertiser_id || '').trim(); const R = $('جدولة: توكنات').all().map(i => i.json).filter(r => r && r.status === 'ok' && r.access_token).sort((x, y) => String(x.created_at).localeCompare(String(y.created_at))).reverse(); const t = R.find(r => String(r.advertiser_ids || '').split(',').map(s => s.trim()).includes(a)); return t ? t.access_token : ''; })() }}"}]}}})
json.dump(ops, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(ops), len(open(sys.argv[2], encoding='utf-8').read()), 'next=', nxt)
