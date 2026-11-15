// يشغّل عقد SN: plan / plan2 / render / reply الحقيقية (من pages.py عبر dump.py) على بيانات سناب اختبارية. لا شبكة ولا n8n.
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.SN_NODES || '/tmp/sn_nodes.json', 'utf8'));
const J = a => a.map(x => ({ json: x })); let pass = 0, fail = 0;
const ok = (n, c, x) => { if (c) pass++; else { fail++; console.log('FAIL', n, x === undefined ? '' : JSON.stringify(x).slice(0, 300)); } };
function run(code, nodes, input) {
  const $ = n => { if (!(n in nodes)) throw new Error("Node '" + n + "' hasn't been executed"); const v = nodes[n]; return { first: () => ({ json: Array.isArray(v) ? v[0] : v }), all: () => J(Array.isArray(v) ? v : [v]) }; };
  return new Function('$', '$input', code)($, { all: () => J(input), first: () => ({ json: input[0] }) }).map(x => x.json);
}
for (const k of ['plan', 'plan2', 'render', 'reply']) { try { new Function('$', '$input', D[k]); pass++; } catch (e) { fail++; console.log('SYNTAX', k, e.message); } }
const route = (cmd, args) => ({ ctx: 'CTX', chatId: 77, cmd, args: args || '' });
const rows = [{ id: '6a7427d7-65a2-4afa-b756-aae4224b3111', name: 'خدمة داتي محمد', cur: 'USD' }];
const info = { ok: true, data: { adaccounts: [{ adaccount: { id: rows[0].id, name: 'خدمة داتي محمد', currency: 'USD', status: 'ACTIVE', timezone: 'America/Los_Angeles' } }] } };
const camps = (n) => ({ ok: true, data: { campaigns: Array.from({ length: n }, (_, i) => ({ campaign: { id: 'camp-' + i, name: 'الخارج ' + i, status: i === 0 ? 'ACTIVE' : 'PAUSED' } })) } });
// 1) لا حسابات
let p = run(D.plan, { Route: route('snapaccounts') }, [{}]);
ok('no accounts → halt', p.length === 1 && p[0].halt === true && /ما عندك حساب سناب/.test(p[0].text), p);
let r = run(D.render, { 'SN: plan': p }, p); ok('halt render', r[0].text === p[0].text && r[0].chatId === 77, r);
// 2) /snapaccounts
p = run(D.plan, { Route: route('snapaccounts') }, rows);
ok('plan items: info+camps per account', p.length === 2 && p[0].op === 'snapchat.adaccount' && p[1].op === 'snapchat.campaigns' && p[0].platform === 'snapchat' && p[0].ad_account === '' && p[0].params.oid === rows[0].id && p[1].params.limit === 50, p);
let res1 = [info, camps(2)];
let p2 = run(D.plan2, { 'SN: plan': p }, res1);
ok('accounts: no stats needed', p2.length === 1 && p2[0].need === false && p2[0].rep === false && p2[0].accts[rows[0].id].camps.length === 2, p2);
r = run(D.render, { 'SN: plan': p, 'SN: plan2': p2 }, p2);
ok('accounts text', /الحسابات الإعلانية/.test(r[0].text) && /خدمة داتي محمد \(USD\) — نشط/.test(r[0].text) && /الحملات: 2 \| ▶️ شغّالة: 1 \| ⏸️ غيرها: 1/.test(r[0].text) && /\/snapreport/.test(r[0].text) && r[0].text.length < 3800, r[0].text);
// 3) /snapreport (7 أيام)
p = run(D.plan, { Route: route('snapreport') }, rows);
ok('report flag + 7 days', p[0].rep === true && p[0].days === 7, p[0]);
p2 = run(D.plan2, { 'SN: plan': p }, [info, camps(3)]);
ok('stat items per campaign (active first)', p2.length === 3 && p2[0].op === 'snapchat.stats' && p2[0].params.oid === 'camp-0' && p2[0]._carry.need === true, p2.map(x => x.params));
ok('time params: ISO with account tz offset', /^\d{4}-\d{2}-\d{2}T00:00:00\.000-0[78]:00$/.test(p2[0].params.start_time) && /T00:00:00\.000-0[78]:00$/.test(p2[0].params.end_time) && p2[0].params.start_time < p2[0].params.end_time, p2[0].params);
const stats = [{ ok: true, data: { total_stats: [{ total_stat: { stats: { impressions: 12345, swipes: 20, spend: 5000000 } } }] } }, { ok: true, data: { total_stats: [{ total_stat: { stats: { impressions: 0, swipes: 0 } } }] } }, { ok: false, error: { class: 'bad_request', message: 'Validation failed' } }];
r = run(D.render, { 'SN: plan': p, 'SN: plan2': p2 }, stats);
const T = r[0].text;
ok('report text parts', /تقرير سناب شات — آخر 7 أيام/.test(T) && /الصرف: 5\.00 USD/.test(T) && /الظهور: 12,345/.test(T) && /السحبات \(Swipes\): 20/.test(T) && /سعر السحبة: 0\.25 USD/.test(T) && /ما صار توزيع بهالفترة/.test(T) && /ما كدرت أقرأ الأرقام: Validation failed/.test(T) && /الحكم ناجحة\/فاشلة غير متاح/.test(T), T);
// 4) أيام مخصّصة و«اليوم»
ok('args today → 1 day', run(D.plan, { Route: route('snapreport', 'اليوم') }, rows)[0].days === 1);
ok('args 14 → 14 days', run(D.plan, { Route: route('snapreport', '14') }, rows)[0].days === 14);
ok('args 99 → max 30', run(D.plan, { Route: route('snapreport', '99') }, rows)[0].days === 30);
// 5) فشل قراءة بيانات الحساب/الحملات: يظهر تحذير ولا ينهار
p = run(D.plan, { Route: route('snapaccounts') }, rows);
p2 = run(D.plan2, { 'SN: plan': p }, [{ ok: false, error: { message: 'Authorization failed' } }, { ok: false, error: { class: 'auth_expired' } }]);
r = run(D.render, { 'SN: plan': p, 'SN: plan2': p2 }, p2);
ok('errors shown, no crash', /⚠️ بيانات الحساب: Authorization failed/.test(r[0].text) && /⚠️ الحملات: auth_expired/.test(r[0].text), r[0].text);
// 6) تقرير بدون حملات: ما يستدعي stats
p = run(D.plan, { Route: route('snapreport') }, rows);
p2 = run(D.plan2, { 'SN: plan': p }, [info, camps(0)]);
ok('no campaigns → need false', p2.length === 1 && p2[0].need === false, p2);
r = run(D.render, { 'SN: plan': p, 'SN: plan2': p2 }, p2); ok('no campaigns text', /ما عندك حملات بهذا الحساب/.test(r[0].text), r[0].text);
// 7) 10 حملات: الحد 6 + تنبيه
p = run(D.plan, { Route: route('snapreport') }, rows); p2 = run(D.plan2, { 'SN: plan': p }, [info, camps(10)]);
ok('max 6 stat calls per account', p2.length === 6, p2.length); r = run(D.render, { 'SN: plan': p, 'SN: plan2': p2 }, Array(6).fill({ ok: true, data: { total_stats: [{ total_stat: { stats: { impressions: 1, swipes: 0, spend: 0 } } }] } }));
ok('hidden campaigns note', /و4 حملة ثانية ما انعرضت/.test(r[0].text), r[0].text);
// 8) reply
r = run(D.reply, {}, [{ ctx: 'C', chatId: 5, text: 'hi' }]); ok('reply shape', r[0].text === 'hi' && r[0].chatId === 5 && r[0].edit === false, r);
// 9) منطقة زمنية غير معروفة → احتياط UTC
p = run(D.plan, { Route: route('snapreport') }, rows); const bad = JSON.parse(JSON.stringify(info)); bad.data.adaccounts[0].adaccount.timezone = 'Not/AZone';
p2 = run(D.plan2, { 'SN: plan': p }, [bad, camps(1)]); ok('bad tz fallback', /\+00:00$/.test(p2[0].params.start_time), p2[0].params);
console.log('SN tests: pass=' + pass + ' fail=' + fail); process.exit(fail ? 1 : 0);
