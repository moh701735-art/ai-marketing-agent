import json, sys, hashlib
# usage: gen_rot.py <live_workflow.json> <out_ops.json>
ROT = '7NWaY0zGwHw8lBFH'
d = json.load(open(sys.argv[1])); w = d.get('workflow', d); N = {x['name']: x for x in w['nodes']}
g = lambda k: N[k]
fb = g('سقف ميتا: إيقاف الحملة')['credentials']['facebookGraphApi']
tgn = g('سقف ميتا: إرسال'); tgc = tgn['credentials']['telegramApi']; chat = tgn['parameters']['chatId']
tbl = g('سقف الرسالة: جلب')['parameters']['dataTableId']
tprep = g('سقف ميتا: تجهيز')['parameters']['jsCode']; tdec = g('سقف ميتا: قرار')['parameters']['jsCode']
tcmd = g('سقف الرسالة: تجهيز')['parameters']['jsCode']; tsave = g('سقف الرسالة: حفظ')['parameters']
assert 'rot' not in tprep.replace('rotate',''), 'already patched?'
def rep(s, a, b):
    assert s.count(a) == 1, a[:50]; return s.replace(a, b)
# --- patch تجهيز
tprep2 = rep(tprep, "return Object.values(by).map(x =>", """for (const cr of Object.values(capBy)) {
  let rot = {}; try { rot = JSON.parse(cr.rot) || {}; } catch (e) {}
  const cid = String(cr.campaign_id);
  if (!rot.on || !rot.acct || cr.stopped_at || seen.has(cid) || stopped[cid]) continue;
  seen.add(cid);
  const b = by[rot.acct] || (by[rot.acct] = { account_id: rot.acct, ids: [], names: {} });
  b.ids.push(cid); b.names[cid] = cr.name || '';
}
return Object.values(by).map(x =>""")
# --- patch قرار
t = rep(tdec, "const LEGACY_USD", "const P = s => { try { return JSON.parse(s) || {}; } catch (e) { return {}; } };\nconst LEGACY_USD")
t = rep(t, "    if (msgs < 1) continue;\n    const cpr = spend / msgs;\n", "    const rot = P(cr && cr.rot), rotOn = !!rot.on;\n    if (rotOn ? (msgs < 3 && spend < 3 * limit) : msgs < 1) continue;\n    const cpr = spend / Math.max(msgs, 1);\n")
t = rep(t, "limit, stop, hasRow: !!cr }", "limit, stop, hasRow: !!cr, rot: rotOn ? rot : null }")
tdec2 = t
# --- patch أمر السقف
c = rep(tcmd, "const m = rest.match(", """const rotOff = /(بدون|الغ|الغاء|ايقاف|وقف)\\s*(ال)?(تدوير|تبديل)/.test(rest);
const rotOn = !rotOff && /(تدوير|تبديل|بدل|غير|ابدل|دور)\\w*\\s*(ال)?جمهور|جمهور\\s*(جديد|ثاني|مختلف|اخر)|(ال)?تدوير/.test(rest);
const m = rest.match(""")
c = rep(c, "if (!m && !noStop) return", "if (!m && !noStop && !rotOn && !rotOff) return")
c = rep(c, "const cents = Math.round(cap * 100);", """let rot = {}; try { rot = JSON.parse(pick.rot) || {}; } catch (e) {}
if (rotOn) rot = { on: 1, gen: rot.gen || 1, max: rot.max || 3, root: rot.root || String(pick.campaign_id), used: rot.used || [], acct: rot.acct || '' };
if (rotOff) rot.on = 0;
const stopOn = rotOn ? true : !noStop;
const cents = Math.round(cap * 100);""")
c = rep(c, "(noStop ? 'إذا تعداه أنبّهك بس وما أطفيها.' : 'إذا تعداه أطفيها تلقائياً.');", "(stopOn ? 'إذا تعداه أطفيها تلقائياً.' : 'إذا تعداه أنبّهك بس وما أطفيها.') + (rotOn ? '\\n🔄 تدوير الجمهور شغّال: إذا تعدّى السقف أطفيها وأرفع حملة بديلة بجمهور أعمار مختلفة (لحد ' + rot.max + ' حملات بالسلسلة).' : (rotOff ? '\\n⏹️ ألغيت تدوير الجمهور لهذي الحملة.' : ''));")
c = rep(c, "auto_stop: noStop ? '0' : '1', finalMessage: msg", "auto_stop: stopOn ? '1' : '0', rot: Object.keys(rot).length ? JSON.stringify(rot) : String(pick.rot || ''), finalMessage: msg")
# --- save node: add rot column
cols = tsave['columns']
sch = cols['schema'] + [{"defaultMatch": False, "display": True, "displayName": "rot", "id": "rot", "readOnly": False, "removed": False, "required": False, "type": "string"}]
SET = lambda n, p, v: {'type': 'setNodeParameter', 'nodeName': n, 'path': p, 'value': v}
ops = [SET('سقف ميتا: تجهيز', '/jsCode', tprep2), SET('سقف ميتا: قرار', '/jsCode', tdec2), SET('سقف الرسالة: تجهيز', '/jsCode', c),
       SET('سقف الرسالة: حفظ', '/columns/schema', sch), SET('سقف الرسالة: حفظ', '/columns/value/rot', '={{ $json.rot ?? "" }}')]
# --- new nodes
cd = lambda name, pos, js: {'name': name, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': pos, 'parameters': {'jsCode': js}}
ew = lambda name, pos: {'name': name, 'type': 'n8n-nodes-base.executeWorkflow', 'typeVersion': 1.3, 'position': pos, 'parameters': {'mode': 'once', 'source': 'database', 'workflowId': {'__rl': True, 'mode': 'id', 'value': ROT}, 'options': {}}}
iff = lambda name, pos, expr: {'name': name, 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': pos, 'parameters': {'conditions': {
    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
    'conditions': [{'id': 'c1', 'leftValue': '={{ %s }}' % expr, 'rightValue': True, 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'}, 'options': {}}}
def http(name, pos, method, url, body=None, q=None):
    p = {'method': method, 'url': url, 'authentication': 'predefinedCredentialType', 'nodeCredentialType': 'facebookGraphApi',
         'options': {'batching': {'batch': {'batchSize': 1, 'batchInterval': 300}}, 'response': {'response': {'neverError': True}}}}
    if body: p.update({'sendBody': True, 'specifyBody': 'json', 'jsonBody': body})
    if q: p.update({'sendQuery': True, 'queryParameters': {'parameters': [{'name': a, 'value': b} for a, b in q]}})
    return {'name': name, 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': pos, 'onError': 'continueRegularOutput', 'parameters': p, 'credentials': {'facebookGraphApi': fb}}
G = 'https://graph.facebook.com/v20.0/'
X, Y = 6000, 11400
T1, E1, I1, CP, AS, T2, E2, I2, UP, T3, E3, AC, T4, E4, I3, SV, TG = ['تدوير: ' + s for s in ['بعد الإيقاف', 'محرك 1', 'نسخ؟', 'نسخ', 'مجموعات', 'استهداف', 'محرك 2', 'تعديل؟', 'تعديل المجموعة', 'تحقق', 'محرك 3', 'تفعيل', 'نهاية', 'محرك 4', 'صف؟', 'حفظ', 'إرسال']]
ALL = lambda n: "$('%s').all().map(i=>i.json)" % n
new = [
 cd(T1, [X, Y], "return [{json:{mode:'rotCopy',dec:%s,stops:$input.all().map(i=>i.json)}}];" % ALL('سقف ميتا: قرار')), ew(E1, [X+220, Y]), iff(I1, [X+440, Y], "$json.kind === 'copy'"),
 http(CP, [X+660, Y-100], 'POST', '=' + G + '{{ $json.campaign_id }}/copies', "={{ JSON.stringify({ deep_copy: true, status_option: 'INHERITED_FROM_SOURCE', rename_options: { rename_strategy: 'ONLY_TOP_LEVEL_RENAME', rename_suffix: ' - جمهور ' + ($json.gen + 1) } }) }}"),
 http(AS, [X+880, Y-100], 'GET', '=' + G + "{{ $json.copied_campaign_id || (($json.ad_object_ids || []).find(x => x.ad_object_type === 'campaign') || {}).copied_id || '0' }}/adsets", None, [('fields', 'id,name,targeting'), ('limit', '100')]),
 cd(T2, [X+1100, Y-100], "return [{json:{mode:'rotTarget',ctx:%s.filter(j=>j.kind==='copy'),copies:%s,adsets:$input.all().map(i=>i.json)}}];" % (ALL(E1), ALL(CP))),
 ew(E2, [X+1320, Y-100]), iff(I2, [X+1540, Y-100], "$json.kind === 'upd'"),
 http(UP, [X+1760, Y-200], 'POST', '=' + G + '{{ $json.adset_id }}', "={{ JSON.stringify({ targeting: $json.targeting }) }}"),
 cd(T3, [X+1980, Y-200], "return [{json:{mode:'rotCheck',ctx:%s.filter(j=>j.kind==='upd'),res:$input.all().map(i=>i.json)}}];" % ALL(E2)), ew(E3, [X+2200, Y-200]),
 http(AC, [X+2420, Y-200], 'POST', '=' + G + '{{ $json.new_id }}', "={{ JSON.stringify({ status: $json.ok ? 'ACTIVE' : 'PAUSED' }) }}"),
 cd(T4, [X+2640, Y-200], "return [{json:{mode:'rotFinal',ctx:%s,res:$input.all().map(i=>i.json)}}];" % ALL(E3)), ew(E4, [X+2860, Y-200]), iff(I3, [X+3080, Y-200], "$json.kind === 'row'"),
 {'name': SV, 'type': 'n8n-nodes-base.dataTable', 'typeVersion': 1.1, 'position': [X+3300, Y-300], 'parameters': {'operation': 'upsert', 'dataTableId': tbl, 'filters': {'conditions': [{'keyName': 'campaign_id', 'condition': 'eq', 'keyValue': '={{ $json.row.campaign_id }}'}]},
   'columns': {'mappingMode': 'defineBelow', 'matchingColumns': [], 'value': {k: '={{ $json.row.%s ?? "" }}' % k for k in ['campaign_id', 'name', 'cap_usd', 'auto_stop', 'stopped_at', 'warned_at', 'rot']}, 'attemptToConvertTypes': False, 'convertFieldsToString': False}, 'options': {}}},
 {'name': TG, 'type': 'n8n-nodes-base.telegram', 'typeVersion': 1.2, 'position': [X+3300, Y+100], 'onError': 'continueRegularOutput', 'parameters': {'additionalFields': {'appendAttribution': False}, 'chatId': chat, 'text': '={{ $json.text }}'}, 'credentials': {'telegramApi': tgc}}]
ops += [{'type': 'addNode', 'node': n} for n in new]
C = lambda s, t, si=0: {'type': 'addConnection', 'source': s, 'target': t, 'sourceIndex': si, 'targetIndex': 0}
ops += [C('سقف ميتا: إيقاف الحملة', T1), C(T1, E1), C(E1, I1), C(I1, CP), C(I1, TG, 1), C(CP, AS), C(AS, T2), C(T2, E2), C(E2, I2), C(I2, UP), C(I2, TG, 1), C(UP, T3), C(T3, E3), C(E3, AC), C(AC, T4), C(T4, E4), C(E4, I3), C(I3, SV), C(I3, TG, 1)]
json.dump(ops, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(ops), len(open(sys.argv[2], encoding='utf-8').read()), hashlib.md5((tprep + tdec + tcmd).encode()).hexdigest())
