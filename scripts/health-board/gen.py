#!/usr/bin/env python3
"""Generates the n8n SDK code of the 'bot health board' workflow (one check chain per bot)."""
import json
BOTS = [
 dict(n='الرئيسي', table='CaceYGtBYl5iHwzW', tt=('DEItueStmKD0gqEH','وكالة 3 فيتناميه'), fb=('h31afIgaoJKLvsmq','Facebook Graph account'), tg=('6ukhAg629mf9HFlF','Telegram account','2076853250')),
 dict(n='علي', table='q5vfp7rolMTlu5Ta', tt=('IWnFpAGmZTMehVgM','علي القريشي'), fb=('MKSechMtirCiCXg2','علي القريشي'), tg=('LZWmJYDacP1zHMHG','القريشي”.','214283814')),
 dict(n='مسلم', table='5bMcWJpgqupl4XXb', tt=('F6N4LUWlIeiWOWLL','Access-Token - مسلم تيك توك،'), fb=('G9qYQk8QvMoz5XfJ','Facebook - Ahmed'), tg=('l8Vnb5oyLljuS7E6','Access-Token - مسلم','5684599913')),
 dict(n='أحمد', table='qaXAJeAXp4YUSayJ', tt=('YPnztpL9vMU76K5B','Access-Token - Ahmed'), fb=('G9qYQk8QvMoz5XfJ','Facebook - Ahmed'), tg=('hERwE8jzSfaxlj2J','عميل احمد فوريفر','1016383221')),
 dict(n='حسن', table='tS6dUzvRNo6vtpZC', tt=('G7mCJd0z9H58h0H2','Access-Token - حسن'), fb=('h31afIgaoJKLvsmq','Facebook Graph account'), tg=None),
]
def q(s): return json.dumps(s, ensure_ascii=False)
out = ["import { workflow, node, trigger } from '@n8n/workflow-sdk';", ""]
out.append("const sched = trigger({ type: 'n8n-nodes-base.scheduleTrigger', version: 1.4, config: { name: 'لوحة الصحة: كل ساعة', parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 1 }] } } } });")
chain = ['sched']
for i, b in enumerate(BOTS):
    v = f'b{i}'
    out.append(f"""const {v}c = node({{ type: 'n8n-nodes-base.dataTable', version: 1.1, config: {{ name: {q(b['n']+': العملاء')}, alwaysOutputData: true, parameters: {{ operation: 'get', dataTableId: {{ __rl: true, mode: 'id', value: {q(b['table'])} }}, returnAll: true }} }} }});""")
    out.append(f"""const {v}t = node({{ type: 'n8n-nodes-base.httpRequest', version: 4.2, config: {{ name: {q(b['n']+': تيك توك')}, executeOnce: true, onError: 'continueRegularOutput', credentials: {{ httpHeaderAuth: {{ id: {q(b['tt'][0])}, name: {q(b['tt'][1])} }} }}, parameters: {{ url: 'https://business-api.tiktok.com/open_api/v1.3/advertiser/info/', authentication: 'genericCredentialType', genericAuthType: 'httpHeaderAuth', sendQuery: true, queryParameters: {{ parameters: [{{ name: 'advertiser_ids', value: {q("={{ JSON.stringify($('"+b['n']+": العملاء').all().map(x => String(x.json.tiktok_advertiser_id || '')).filter(Boolean)) }}")} }}, {{ name: 'fields', value: '["advertiser_id","name","status"]' }}] }}, options: {{ response: {{ response: {{ neverError: true }} }} }} }} }} }});""")
    out.append(f"""const {v}m = node({{ type: 'n8n-nodes-base.httpRequest', version: 4.2, config: {{ name: {q(b['n']+': ميتا')}, executeOnce: true, onError: 'continueRegularOutput', credentials: {{ facebookGraphApi: {{ id: {q(b['fb'][0])}, name: {q(b['fb'][1])} }} }}, parameters: {{ url: 'https://graph.facebook.com/v20.0/me', authentication: 'predefinedCredentialType', nodeCredentialType: 'facebookGraphApi', sendQuery: true, queryParameters: {{ parameters: [{{ name: 'fields', value: 'id,name' }}] }}, options: {{ response: {{ response: {{ neverError: true }} }} }} }} }} }});""")
    chain += [f'{v}c', f'{v}t', f'{v}m']
    if b['tg']:
        out.append(f"""const {v}g = node({{ type: 'n8n-nodes-base.telegram', version: 1.2, config: {{ name: {q(b['n']+': تيليجرام')}, executeOnce: true, onError: 'continueRegularOutput', credentials: {{ telegramApi: {{ id: {q(b['tg'][0])}, name: {q(b['tg'][1])} }} }}, parameters: {{ resource: 'chat', operation: 'get', chatId: {q(b['tg'][2])} }} }} }});""")
        chain.append(f'{v}g')
names = [b['n'] for b in BOTS]
tg_names = [b['n'] for b in BOTS if b['tg']]
agg = open('agg.js', encoding='utf-8').read().replace('__BOTS__', json.dumps([dict(n=b['n'], tg=bool(b['tg'])) for b in BOTS], ensure_ascii=False))
out.append(f"const agg = node({{ type: 'n8n-nodes-base.code', version: 2, config: {{ name: 'تجميع لوحة الصحة', parameters: {{ jsCode: {q(agg)} }} }} }});")
out.append("""const send = node({ type: 'n8n-nodes-base.telegram', version: 1.2, config: { name: 'لوحة الصحة: إرسال', credentials: { telegramApi: { id: '6ukhAg629mf9HFlF', name: 'Telegram account' } }, parameters: { resource: 'message', operation: 'sendMessage', chatId: '2076853250', text: "={{ String($json.text ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}", additionalFields: { appendAttribution: false, parse_mode: 'HTML' } } } });""")
chain += ['agg', 'send']
out.append("")
out.append("export default workflow('health-board', 'لوحة صحة البوتات')")
out.append("  .add(sched)")
for c in chain[1:]:
    out.append(f"  .to({c})")
out.append(";")
open('health_board.sdk.ts', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print(len('\n'.join(out)))
