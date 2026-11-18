// يختبر عقدة نتيجة الإيقاف بعد p201b: JS مستخرج من wf_monitor.py المرقّع (fixture).
const fs = require('fs'), assert = require('assert');
const src = fs.readFileSync(process.argv[2], 'utf8'); let n = 0;
const T = (name, f) => { try { f(); n++; console.log('ok   ' + name); } catch (e) { console.log('FAIL ' + name + '\n  ' + (e.stack || e.message).split('\n').slice(0, 3).join('\n  ')); process.exitCode = 1; } };
const blk = nm => { const i = src.indexOf('code(w, "' + nm + '", r"""'); const a = src.indexOf('"""', i) + 3, b = src.indexOf('"""', a); return src.slice(a, b); };
const stopJs = blk('Stop result'), evJs = blk('Evaluate');
const run = (items, results) => new Function('$', '$input', stopJs)(nm => ({ all: () => items.map(j => ({ json: j })) }), { all: () => results.map(j => ({ json: j })) });
const base = { kind: 'stop', ctx: 'c', cid: '188', name: 'موبايل', level: 0.5, stopCap: 0.5, stats: 'stats-line' };
T('01 no results → «صرفت 0.50$ بدون أي نتيجة» + cap + stats + /activate', () => { const o = run([{ ...base, noRes: true, cpr: 0.5 }], [{ ok: true }])[0].json; assert.strictEqual(o.state, 'stopped'); assert(/تم إيقاف الحملة «موبايل»/.test(o.text) && /صرفت 0\.50\$ بدون أي نتيجة/.test(o.text) && /حد الإيقاف 0\.5\$/.test(o.text) && /stats-line/.test(o.text) && /\/activate_188/.test(o.text), o.text); assert(!o.text.includes('undefined')); });
T('02 with results → cost-per-result wording', () => { const o = run([{ ...base, noRes: false, cpr: 0.62 }], [{ ok: true }])[0].json; assert(/تكلفة النتيجة وصلت 0\.620\$/.test(o.text) && !/بدون أي نتيجة/.test(o.text), o.text); });
T('03 stop failed → unchanged «watching» branch (no fake success)', () => { const o = run([{ ...base, noRes: true, cpr: 0.5 }], [{ ok: false, error: { class: 'bad_request' } }])[0].json; assert.strictEqual(o.state, 'watching'); assert(/FAILTEXT/.test(o.text) && /bad_request/.test(o.text)); });
T('04 text uses real newlines only via \\n escapes (single message, ≤ 3800 chars)', () => { const o = run([{ ...base, noRes: true, cpr: 0.5 }], [{ ok: true }])[0].json; assert(o.text.split('\n').length === 3 && o.text.length < 600, JSON.stringify(o.text)); });
T('05 Evaluate stop item carries noRes (anchor inserted inside the object)', () => { assert(/noRes: !!noRes, \/\* p201b \*\/ idem: 'guard-stop-'/.test(evJs)); new Function('p', 'res', 'stop', 'cost', 'last', 'out', 'stats', 'const o=[];' + 'const f = () => {' + evJs.replace('for (const rule of p.rules)', 'for (const rule of p.rules)') + '};'); });
console.log(n + ' passed');
