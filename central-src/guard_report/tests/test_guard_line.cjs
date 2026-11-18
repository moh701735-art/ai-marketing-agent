// يختبر مساعد p201c المستخرج من wf_job_report.py المرقّع (fixture): سطر قاعدة الحارس بتقرير الساعة.
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(process.argv[2], 'utf8'); let n = 0;
const T = (name, f) => { try { f(); n++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + '\n  ' + (e.stack || e.message).split('\n').slice(0, 3).join('\n  ')); process.exitCode = 1; } };
const a = src.indexOf('// p201c begin'), b = src.indexOf('// p201c end'); const H = src.slice(a, b);
const mk = rows => new Function('$', H + '\nreturn { guardLine, GRM };')(nm => { if (nm !== 'Accounts') throw new Error('node ' + nm); return { all: () => rows.map(j => ({ json: j })) }; });
const acct = { ctx: 'c', chat_id: '1', platform: 'tiktok', external_id: '777', name: 'acc' };
const rules = al => ({ ctx: 'c', chat_id: '1', platform: null, external_id: null, name: '~rules~' + JSON.stringify(al) });
T('01 watching campaign → rule line with alerts and stop', () => { const g = mk([acct, rules([{ id: '188', stop: '0.5', al: '{0.3,0.4}' }])]).guardLine({ campaign_id: '188', status: 'ENABLE' }); assert.strictEqual(g, '🛡 الحارس: تنبيه عند 0.30$ / 0.40$، إيقاف تلقائي عند 0.50$ (بدون نتائج أو تكلفة نتيجة)'); });
T('02 custom rule values are shown as stored (0.2/0.3/0.6)', () => { const g = mk([rules([{ id: '9', stop: 0.6, al: '{0.2,0.3}' }])]).guardLine({ campaign_id: 9 }); assert(/تنبيه عند 0\.20\$ \/ 0\.30\$، إيقاف تلقائي عند 0\.60\$/.test(g), g); });
T('03 no alerts configured → only the stop part', () => { const g = mk([rules([{ id: '5', stop: '0.5', al: '{}' }])]).guardLine({ campaign_id: '5' }); assert(g.startsWith('🛡 الحارس: إيقاف تلقائي عند 0.50$'), g); });
T('04 active campaign with NO rule (rules row present) → explicit «بدون حارس»', () => { const g = mk([rules([{ id: '1', stop: '0.5', al: '{}' }])]).guardLine({ campaign_id: '2', status: 'ENABLE' }); assert(/بدون حارس/.test(g), g); });
T('05 paused campaign with no rule → no claim', () => { assert.strictEqual(mk([rules([])]).guardLine({ campaign_id: '2', status: 'DISABLE' }), null); });
T('06 rules row MISSING (query failed / older data) → never claims «بدون حارس»', () => { assert.strictEqual(mk([acct]).guardLine({ campaign_id: '2', status: 'ENABLE' }), null); });
T('07 bad JSON / node error → silent (null), no crash', () => { const h = mk([{ name: '~rules~{bad' }]); assert.strictEqual(h.guardLine({ campaign_id: '1' }), null); const g = new Function('$', H + '\nreturn guardLine;')(() => { throw new Error('x'); }); assert.strictEqual(g({ campaign_id: '1', status: 'ENABLE' }), null); });
T('08 stop <= 0 in a rule row → no line (never prints a nonsense rule)', () => { assert.strictEqual(mk([rules([{ id: '3', stop: '0', al: '{}' }])]).guardLine({ campaign_id: '3' }), null); });
T('09 account rows are ignored (only ~rules~ rows count)', () => { const h = mk([acct, acct, rules([{ id: '4', stop: '0.5', al: '{0.3}' }])]); assert(h.GRM.ok && Object.keys(h.GRM.m).length === 1); });
T('10 patched fmt code inserts the call after the verdict line', () => { assert(/B\.push\('📊 الحكم: ' \+ v\[0\] \+ ' ' \+ v\[1\]\);\n\s*\{ const gl = guardLine\(k\); if \(gl\) B\.push\(gl\); \}/.test(src)); });
console.log(n + ' passed');
