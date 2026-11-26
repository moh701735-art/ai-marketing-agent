// يشغّل عقد FM2: plan/render/reply الحقيقية ويتحقق من تسلسل المعالج وقيود أزرار تلغرام وعناصر الإطلاق (الحملات دائماً متوقفة).
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.FM2_NODES || '/tmp/fm2_nodes.json', 'utf8'));
const J = a => a.map(x => ({ json: x })); let pass = 0, fail = 0;
const ok = (n, c, x) => { if (c) pass++; else { fail++; console.log('FAIL', n, x === undefined ? '' : JSON.stringify(x).slice(0, 500)); } };
function run(code, nodes, input) {
  const $ = n => { if (!(n in nodes)) throw new Error("Node '" + n + "' hasn't been executed"); const v = nodes[n]; return { first: () => ({ json: Array.isArray(v) ? v[0] : v }), all: () => J(Array.isArray(v) ? v : [v]) }; };
  return new Function('$', '$input', code)($, { all: () => J(input), first: () => ({ json: input[0] }) }).map(x => x.json);
}
for (const k of ['plan', 'render', 'reply']) { try { new Function('$', '$input', D[k]); pass++; } catch (e) { fail++; console.log('SYNTAX', k, e.message); } }
let ACCTS = [{ kind: 'acct', a: 'act_123456789', b: 'حساب عمر', c: 'USD' }];
const rows = (state, linked = true) => [].concat(linked ? ACCTS : [], state ? [{ kind: 'state', a: JSON.stringify(state), b: '5' }] : []);
const route = (cb, extra) => ({ ctx: 'CTX', chatId: 77, cmd: cb ? 'fmwiz' : 'fbobj', cb, ...extra });
function step(cb, state, goResult, extra, linked = true) {
  const plan = run(D.plan, { Route: route(cb, extra) }, rows(state, linked));
  const res = plan[0].need ? plan.map(() => goResult) : [];
  const out = run(D.render, { 'FM2: plan': plan }, res);
  return { plan, out: out[0], S: JSON.parse(out[0].state || 'null') };
}
const text = (t, state) => { const plan = run(D.plan, { Route: { ctx: 'CTX', chatId: 77, cmd: 'fmin', args: t } }, rows(state)); const out = run(D.render, { 'FM2: plan': plan }, [])[0]; return { plan, out, S: JSON.parse(out.state || 'null') }; };
function checkKb(name, o) {
  const kb = o.keyboard || []; let good = kb.length >= 1 && kb.length <= 8 && o.text.length <= 3800; const bad = [];
  kb.forEach(r => { if (r.length < 1 || r.length > 3) bad.push('row ' + r.length); r.forEach(b => { if (typeof b.t !== 'string' || b.t.length < 1 || b.t.length > 40) bad.push('t:' + b.t); if (b.c && !/^[a-z0-9_:\-]{1,48}$/.test(b.c)) bad.push('c:' + b.c); }); });
  ok(name + ' keyboard rules', good && !bad.length, { rows: kb.length, bad, len: o.text.length });
}
const POST = 'https://www.facebook.com/page.name/videos/123456789012345/';
// 1) بداية: 3 أهداف + ملاحظة «قريباً»
let r = step(null, null); checkKb('start', r.out);
ok('start: obj screen with 3 objectives, no broker', r.S.st === 'obj' && ['awareness', 'traffic', 'engagement'].every(k => r.out.keyboard.flat().some(b => b.c === 'fm:o:' + k)) && !r.plan[0].need, r.out);
ok('start: honest soon note for leads/sales/app', /قريباً/.test(r.out.text) && /عملاء محتملين/.test(r.out.text), r.out.text);
// 2) زيارات: حساب واحد تلقائي → post
r = step('fm:o:traffic', r.S); let S = r.S; ok('traffic: single account auto → post', S.st === 'post' && S.acct === 'act_123456789' && S.obj === 'traffic', S); checkKb('post', r.out);
// 3) رابط خطأ ثم صح
let t = text('hello', S); ok('bad post link stays + warning', t.S.st === 'post' && /ما فهمت الرابط/.test(t.out.text), t.out.text);
t = text(POST, S); S = t.S; ok('good post → url (traffic)', S.st === 'url' && S.post === POST, S); checkKb('url', t.out);
t = text('http://insecure.com', S); ok('http link refused', t.S.st === 'url' && /https/.test(t.out.text));
t = text('https://example.com/shop', S); S = t.S; ok('https link → bud', S.st === 'bud' && S.url === 'https://example.com/shop', S);
// 4) ميزانية بالدولار → مدة → عمر → جنس → اسم → ملخص
r = step('fm:bu:5', S); S = r.S; ok('bud 5 → dur', S.st === 'dur' && S.bud === 5, S); checkKb('dur', r.out);
r = step('fm:bu:7', S); ok('invalid budget ignored', r.S.bud === 5 || r.S.st === 'dur');
r = step('fm:du:3', S); S = r.S; ok('dur 3 → age', S.st === 'age' && S.days === 3, S); checkKb('age1', r.out);
r = step('fm:af:25', S); S = r.S; ok('age from 25 stays', S.st === 'age' && S.amin === 25, S); checkKb('age2', r.out);
r = step('fm:at:34', S); S = r.S; ok('age to 34 → gen', S.st === 'gen' && S.amax === 34, S);
r = step('fm:g:f', S); S = r.S; ok('gen f → nm', S.st === 'nm' && S.gen === 'f', S); checkKb('nm', r.out);
t = text('حملتي الأولى', S); S = t.S; ok('name → summary', S.st === 'sum' && S.nm === 'حملتي الأولى', S); checkKb('sum', t.out);
ok('summary: go button + not-messages note + paused note', t.out.keyboard.flat().some(b => b.c === 'fm:go') && /مو رسائل/.test(t.out.text) && /متوقفة/.test(t.out.text), t.out.text);
// 5) إطلاق: عنصر Broker صحيح
r = step('fm:go', S, null); const it = r.plan[0];
ok('go: one broker item meta.launch_whatsapp with objective_key', r.plan.length === 1 && it.need && it.op === 'meta.launch_whatsapp' && it.platform === 'meta' && it.ad_account === 'act_123456789', it);
const prm = it.params; ok('go params', prm.objective_key === 'traffic' && prm.post_url === POST && prm.link_url === 'https://example.com/shop' && prm.budget_usd === 5 && prm.days === 3 && prm.budget_mode === 'total' && prm.countries.join() === 'IQ' && prm.age_min === 25 && prm.age_max === 34 && prm.genders.join() === '2' && prm.name === 'حملتي الأولى', prm);
ok('go idem length 16..100', it.idem.length >= 16 && it.idem.length <= 100, it.idem); ok('no activate flag ever sent', !('activate_now' in prm), prm);
// 6) نتيجة النجاح والفشل
const okRes = { ok: true, data: { campaign_id: '900', adset_id: '901', ad_id: '903', creative_id: '902', currency: 'USD', status: 'PAUSED', readback: { effective_status: 'PAUSED' } } };
r = step('fm:go', S, okRes); checkKb('success', r.out); ok('success card honest: paused, ids, fbactivate, results metric', /انرفعت حملة فيسبوك \(متوقفة\)/.test(r.out.text) && /900/.test(r.out.text) && /\/fbactivate_900/.test(r.out.text) && /نقرات على الرابط/.test(r.out.text) && /ما فيه صرف/.test(r.out.text), r.out.text);
ok('success resets state', r.S.st === 'obj' && r.S.post === '', r.S);
const failRes = { ok: false, error: { class: 'bad_request', message: 'Meta says: invalid parameter' }, data: { stage: 'adset', created_before_failure: { campaign_id: '900' } } };
r = step('fm:go', S, failRes); checkKb('failure', r.out); ok('failure card: verbatim error, partial campaign, nothing activated', /Meta says: invalid parameter/.test(r.out.text) && /900/.test(r.out.text) && /ما فعّلت شي/.test(r.out.text) && /المجموعة الإعلانية/.test(r.out.text), r.out.text);
// 7) ناقص: يرفض قبل أي نداء
r = step('fm:go', { ...S, bud: 0 }, null); ok('go with missing budget → goErr, no broker', !r.plan[0].need && /ناقصة/.test(r.out.text), r.out.text);
r = step('fm:go', { ...S, post: '' }, null); ok('go with missing post → goErr', !r.plan[0].need);
r = step('fm:go', { ...S, url: '' }, null); ok('traffic without url → goErr', !r.plan[0].need);
// 8) وعي/تفاعل: بدون خطوة رابط الموقع
for (const k of ['awareness', 'engagement']) { let q = step('fm:o:' + k, step(null, null).S).S; ok(k + ': post then bud (no url step)', q.st === 'post', q); q = text(POST, q).S; ok(k + ': → bud', q.st === 'bud', q); }
// 9) IQD: ميزانيات بالدينار وتحويل لدولار
ACCTS = [{ kind: 'acct', a: 'act_123456789', b: 'حساب دينار', c: 'IQD' }];
let q = step('fm:o:awareness', step(null, null).S).S; q = text(POST, q).S; r = step(null, q); r = step('fm:b:bud', q); checkKb('iqd bud', r.out);
ok('IQD budgets shown', r.out.keyboard.flat().some(b => b.c === 'fm:bu:10000'), r.out.keyboard);
q = step('fm:bu:25000', q).S; q = step('fm:du:1', q).S; q = step('fm:aa', q).S; q = step('fm:g:a', q).S; q = step('fm:nt', q).S;
r = step('fm:go', q, null); ok('IQD → budget_usd converted (25000/1555)', Math.abs(r.plan[0].params.budget_usd - 16.0772) < 0.001 && !('genders' in r.plan[0].params) && !('age_min' in r.plan[0].params), r.plan[0].params);
// 10) عدة حسابات: اختيار الحساب
ACCTS = [{ kind: 'acct', a: 'act_111111', b: 'أ', c: 'USD' }, { kind: 'acct', a: 'act_222222', b: 'ب', c: 'IQD' }];
r = step('fm:o:awareness', step(null, null).S); ok('two accounts → acct step', r.S.st === 'acct', r.S); checkKb('acct', r.out);
r = step('fm:ac:222222', r.S); ok('choose account', r.S.acct === 'act_222222' && r.S.st === 'post', r.S);
r = step('fm:ac:999999', step('fm:o:awareness', step(null, null).S).S); ok('unknown account ignored', r.S.st === 'acct' && !r.S.acct, r.S);
// 11) غير مربوط
r = step(null, null, null, {}, false); ok('not linked message', /غير مربوط/.test(r.out.text), r.out.text);
// 12) رجوع وتبديل
ACCTS = [{ kind: 'acct', a: 'act_123456789', b: 'عمر', c: 'USD' }];
r = step('fm:b:post', S); ok('back to post step', r.S.st === 'post', r.S);
r = step('fm:b:nonsense', S); ok('invalid back step ignored', r.S.st === 'sum', r.S);
// 13) p288: دخول من المعالج القديم بعد اختيار حساب فيسبوك
ACCTS = [{ kind: 'acct', a: 'act_123456789', b: 'حساب عمر', c: 'USD' }, { kind: 'acct', a: 'act_555555555', b: 'حساب ثاني', c: 'IQD' }];
r = step('wz:ac:act_123456789', { st: 'post', obj: 'traffic', acct: 'act_555555555' }); checkKb('wz entry', r.out);
ok('wz entry: objective list with WhatsApp legacy button + 3 new + back to legacy', r.S.st === 'obj' && r.S.via === 'wz' && r.S.acct === 'act_123456789' && r.out.keyboard.flat().some(b => b.c === 'wz:ac:act_123456789' && /واتساب/.test(b.t)) && ['awareness', 'traffic', 'engagement'].every(k => r.out.keyboard.flat().some(b => b.c === 'fm:o:' + k)) && r.out.keyboard.flat().some(b => b.c === 'wz:r:acct'), r.out);
ok('wz entry resets previous state and shows the account', r.S.obj === '' && r.S.post === '' && /حساب عمر/.test(r.out.text) && !r.plan[0].need, r.out.text);
r = step('fm:o:traffic', r.S); ok('after objective: account skipped → post', r.S.st === 'post' && r.S.acct === 'act_123456789' && r.S.via === 'wz', r.S);
r = step('fm:b:obj', r.S); ok('back from post → objective list again (account kept)', r.S.st === 'obj' && r.S.acct === 'act_123456789', r.S); ok('and still has the legacy WhatsApp button', r.out.keyboard.flat().some(b => b.c === 'wz:ac:act_123456789'));
r = step('wz:ac:act_999999999', null); ok('unknown account in wz callback: list without preset account/WhatsApp button', r.S.acct === '' && !r.out.keyboard.flat().some(b => /^wz:ac:/.test(b.c || '')), r.S);
r = step('wz:ac:7691331863249256500', null); ok('non-meta callback id is not treated as wz entry', r.S.via === '', r.S);
// نفس العميل بحسابين بدون wz: السلوك القديم
r = step(null, null); r = step('fm:o:awareness', r.S); ok('plain /fbobj with 2 accounts still asks the account', r.S.st === 'acct' && r.S.via === '', r.S);
// الإطلاق من مسار wz يحمل الحساب الصحيح
let w = step('wz:ac:act_555555555', null).S; w = step('fm:o:awareness', w).S; w = text(POST, w).S; w = step('fm:bu:25000', w).S; w = step('fm:du:3', w).S; w = step('fm:aa', w).S; w = step('fm:g:a', w).S; w = step('fm:nt', w).S;
r = step('fm:go', w, null); ok('launch from wz path uses the chosen account + IQD→USD', r.plan[0].ad_account === 'act_555555555' && Math.abs(r.plan[0].params.budget_usd - 16.0772) < 0.001, r.plan[0]);
console.log('PASS', pass, 'FAIL', fail); process.exit(fail ? 1 : 0);
