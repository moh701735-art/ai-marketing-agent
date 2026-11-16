// يشغّل عقد SN2: plan/render/reply الحقيقية على بيانات سناب اختبارية ويتحقق من قيود أزرار تلغرام (≤8 صفوف، ≤3 بالصف، t ≤40، callback [a-z0-9_:-]{1,48}، نص ≤3800).
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.SN2_NODES || '/tmp/sn2_nodes.json', 'utf8'));
const J = a => a.map(x => ({ json: x })); let pass = 0, fail = 0;
const ok = (n, c, x) => { if (c) pass++; else { fail++; console.log('FAIL', n, x === undefined ? '' : JSON.stringify(x).slice(0, 400)); } };
function run(code, nodes, input) {
  const $ = n => { if (!(n in nodes)) throw new Error("Node '" + n + "' hasn't been executed"); const v = nodes[n]; return { first: () => ({ json: Array.isArray(v) ? v[0] : v }), all: () => J(Array.isArray(v) ? v : [v]) }; };
  return new Function('$', '$input', code)($, { all: () => J(input), first: () => ({ json: input[0] }) }).map(x => x.json);
}
for (const k of ['plan', 'render', 'reply']) { try { new Function('$', '$input', D[k]); pass++; } catch (e) { fail++; console.log('SYNTAX', k, e.message); } }
const GOVS = ['Baghdad', 'Basra', 'Nineveh', 'Erbil', 'Sulaymaniyah', 'Dohuk', 'Kirkuk', 'Anbar', 'Babil', 'Karbala', 'Najaf', 'Diyala', 'Wasit', 'Maysan', 'Dhi Qar', 'Muthanna', 'Qadisiyyah', 'Salah ad Din', 'Halabja'];
const regsRes = { ok: true, data: { targeting_dimensions: GOVS.map((n, i) => ({ sub_request_status: 'SUCCESS', region: { id: String(25600 + i), name: n, code2: 'iq' } })) } };
const intsRes = { ok: true, data: { targeting_dimensions: Array.from({ length: 150 }, (_, i) => ({ sub_request_status: 'SUCCESS', scls: { id: 'SLC_' + (i + 1), name: 'Interest number ' + (i + 1) + ' of the long list', parentId: 'SLC_0' } })) } };
const route = (cb) => ({ ctx: 'CTX', chatId: 77, cmd: 'snapwiz', cb });
let ACCTS = [{ kind: 'acct', a: '6a74', b: 'خدمة', c: 'USD' }];
const rows = (state, linked = true) => [].concat(linked ? ACCTS : [], state ? [{ kind: 'state', a: JSON.stringify(state), b: '5' }] : []);
function step(cb, state, results, linked = true) {
  const plan = run(D.plan, { Route: route(cb) }, rows(state, linked));
  const res = plan[0].need ? plan.map(p => ({ regs: regsRes, ints: intsRes, go: results }[p.k])) : [];
  const out = run(D.render, { 'SN2: plan': plan }, res);
  return { plan, out: out[0], S: JSON.parse(out[0].state || 'null') };
}
function checkKb(name, o) {
  const kb = o.keyboard || []; let good = kb.length >= 1 && kb.length <= 8 && o.text.length <= 3800;
  const bad = [];
  kb.forEach(r => { if (r.length < 1 || r.length > 3) bad.push('row ' + r.length); r.forEach(b => { if (typeof b.t !== 'string' || b.t.length < 1 || b.t.length > 40) bad.push('t:' + b.t); if (b.c && !/^[a-z0-9_:\-]{1,48}$/.test(b.c)) bad.push('c:' + b.c); }); });
  ok(name + ' keyboard rules', good && !bad.length, { rows: kb.length, bad, len: o.text.length });
}
// 1) بداية
let r = step('sn:s', null); checkKb('start', r.out);
ok('start: obj screen with 4 objectives', r.S.st === 'obj' && r.out.keyboard.flat().filter(b => /^sn:o:/.test(b.c)).length === 4 && !r.plan[0].need && r.out.edit === true, r.out);
// 2) اختيار الهدف → المحافظات
r = step('sn:o:trf', r.S); ok('obj → reg needs regions', r.plan[0].need === true && r.plan[0].op === 'snapchat.t_regions' && r.plan[0].params.oid === 'iq' && r.plan[0].platform === 'snapchat', r.plan[0]);
checkKb('reg', r.out); ok('reg screen: 15 govs page1 Arabic names', /بغداد/.test(JSON.stringify(r.out.keyboard)) && r.out.keyboard.flat().filter(b => /^sn:r:\d+$/.test(b.c)).length === 15, r.out.keyboard.flat().map(b => b.t));
// 3) toggle محافظة + صفحة ثانية
let S = r.S; r = step('sn:r:25600', S); S = r.S; ok('toggle region on', S.regs.length === 1 && S.regs[0] === '25600' && /✅ بغداد/.test(JSON.stringify(r.out.keyboard)), S);
r = step('sn:r:25600', S); S = r.S; ok('toggle region off', S.regs.length === 0, S);
r = step('sn:rp:1', S); checkKb('reg p2', r.out); ok('reg page 2 has 4 govs', r.out.keyboard.flat().filter(b => /^sn:r:\d+$/.test(b.c)).length === 4 && /2\/2/.test(JSON.stringify(r.out.keyboard)), r.out.keyboard);
S = r.S; r = step('sn:r:25618', S); S = r.S; r = step('sn:rn', S); S = r.S; ok('regions → age', S.st === 'age' && !r.plan[0].need, S); checkKb('age', r.out);
// 4) عمر + جنس + لغة
r = step('sn:a:a3', S); S = r.S; ok('age toggle', S.ages[0] === 'a3' && /✅ 25-34/.test(JSON.stringify(r.out.keyboard)), S); r = step('sn:an', S); S = r.S; checkKb('gender', r.out); ok('gender screen', S.st === 'gen', S);
r = step('sn:g:f', S); S = r.S; ok('gender set → lng', S.gen === 'f' && S.st === 'lng', S); checkKb('lng', r.out);
r = step('sn:l:ar', S); S = r.S; ok('lng set → int needs interests', S.lng === 'ar' && S.st === 'int' && r.plan[0].op === 'snapchat.t_interests' && r.plan[0].params.country_code === 'iq' && r.plan[0].params.oid === 'scls', r.plan[0]);
checkKb('int', r.out); ok('int page1: 12 interests lowercase callbacks', r.out.keyboard.flat().filter(b => /^sn:i:slc_\d+$/.test(b.c)).length === 12, r.out.keyboard.flat().map(b => b.c));
// 5) اهتمامات
r = step('sn:i:slc_5', S); S = r.S; ok('interest toggle stores uppercase id', S.ints[0] === 'SLC_5', S);
for (let i = 6; i <= 17; i++) { r = step('sn:i:slc_' + i, S); S = r.S; } ok('interests capped at 10', S.ints.length === 10, S.ints);
r = step('sn:ip:12', S); S = r.S; checkKb('int p13', r.out); ok('int last page', /13\/13/.test(JSON.stringify(r.out.keyboard)), r.out.keyboard);
r = step('sn:ic', S); S = r.S; ok('clear interests', S.ints.length === 0, S);
r = step('sn:i:slc_9', S); S = r.S; r = step('sn:in', S); S = r.S; checkKb('bud', r.out);
ok('interests next → single account auto → budget screen (no broker)', S.st === 'bud' && S.acct === '6a74' && !r.plan[0].need && r.out.keyboard.flat().filter(b => /^sn:bu:\d+$/.test(b.c)).length === 5, S);
r = step('sn:bu:20', S); S = r.S; ok('budget set → duration', S.bud === 20 && S.st === 'dur', S); checkKb('dur', r.out);
r = step('sn:bu:7', S); ok('invalid budget ignored', r.S.bud === 20, r.S);
r = step('sn:du:3', S); S = r.S; ok('duration set → url screen with /snaplink hint', S.days === 3 && S.st === 'url' && /\/snaplink/.test(r.out.text), r.out.text); checkKb('url', r.out);
const linkStep = (args, state) => { const plan = run(D.plan, { Route: { ctx: 'CTX', chatId: 77, cmd: 'snaplink', args } }, rows(state)); const out = run(D.render, { 'SN2: plan': plan }, [])[0]; return { plan, out, S: JSON.parse(out.state) }; };
let L1 = linkStep('https://t.me/+abc123 ', S); S = L1.S; ok('/snaplink valid → summary, new message', S.url === 'https://t.me/+abc123' && S.st === 'sum' && L1.plan[0].edit === false && /ملخص الاستهداف/.test(L1.out.text), L1.out.text);
checkKb('sum', L1.out); ok('summary shows go button (traffic, complete)', L1.out.keyboard.flat().some(b => b.c === 'sn:go') && /الحساب: خدمة \(USD\)/.test(L1.out.text) && /20 USD \(إجمالية\)/.test(L1.out.text) && /3 أيام/.test(L1.out.text) && /مسودة استهداف فقط|متوقفة/.test(L1.out.text), L1.out.text);
let Lbad = linkStep('http://insecure.com', S); ok('/snaplink http rejected', /الرابط غير صالح/.test(Lbad.out.text) && Lbad.S.url === 'https://t.me/+abc123', Lbad.out.text);
// go: نجاح
const GOOD = { ok: true, data: { campaign_id: 'camp-9', adsquad_id: 'sq-9', currency: 'USD', start_time: '2026-11-15T17:42:05.000-08:00', end_time: '2026-11-18T17:42:05.000-08:00', creative: 'missing' } };
r = step('sn:go', S, GOOD); ok('go plan: launch_draft params', r.plan[0].k === 'go' && r.plan[0].op === 'snapchat.launch_draft' && r.plan[0].platform === 'snapchat' && r.plan[0].ad_account === '' && r.plan[0].params.account_id === '6a74' && r.plan[0].params.budget === 20 && r.plan[0].params.days === 3 && r.plan[0].params.objective === 'trf' && r.plan[0].params.landing_url === 'https://t.me/+abc123' && r.plan[0].params.gender === 'f' && JSON.stringify(r.plan[0].params.ages) === '["25-34"]' && r.plan[0].params.regions.length === 1, r.plan[0].params);
ok('go idempotency key 16..100 chars, safe', r.plan[0].idem.length >= 16 && r.plan[0].idem.length <= 100 && /^[A-Za-z0-9\-]+$/.test(r.plan[0].idem), r.plan[0].idem);
ok('go success text', /انرفعت مسودة حملة سناب شات \(متوقفة\)/.test(r.out.text) && /camp-9/.test(r.out.text) && /sq-9/.test(r.out.text) && /الإعلان.*ما انضاف بعد/.test(r.out.text) && /متوقفة، ما فيه صرف/.test(r.out.text), r.out.text); checkKb('go ok', r.out);
ok('go success resets state', r.S.st === 'obj' && r.S.obj === '' && r.S.url === '', r.S);
const idem1 = r.plan[0].idem; const r2 = step('sn:go', S, GOOD); ok('same state → same idempotency key (double tap safe)', r2.plan[0].idem === idem1);
// go: فشل بمرحلة المجموعة مع معرّف الحملة (لا نجاح وهمي)
r = step('sn:go', S, { ok: false, error: { class: 'bad_request', message: 'targeting invalid' }, data: { stage: 'adsquad', campaign_id: 'camp-9' } });
ok('go failure honest', /ما انرفعت الحملة \(المرحلة: إنشاء المجموعة الإعلانية\)/.test(r.out.text) && /targeting invalid/.test(r.out.text) && /camp-9/.test(r.out.text) && /احذف الحملة/.test(r.out.text) && !/انرفعت مسودة/.test(r.out.text), r.out.text); checkKb('go fail', r.out);
ok('go failure keeps state (can retry)', r.S.url === 'https://t.me/+abc123' && r.S.bud === 20, r.S);
// هدف غير مدعوم: ما يوصل للـbroker
const Ssal = { ...S, obj: 'sal' }; r = step('sn:go', Ssal); ok('non-traffic go blocked before broker', r.plan[0].goErr && !r.plan[0].need && /زيارات/.test(r.out.text), r.out.text);
r = run(D.render, { 'SN2: plan': run(D.plan, { Route: route('sn:b:sum') }, rows(Ssal)) }, [])[0]; ok('non-traffic summary hides go button + notes', !r.keyboard.flat().some(b => b.c === 'sn:go') && /زيارات.*فقط/.test(r.text), r.text);
// ناقصة معلومات
r = step('sn:go', { ...S, bud: 0 }); ok('missing info blocked', /ناقصة معلومات/.test(r.out.text) && !r.plan[0].need, r.out.text);
// حسابين: شاشة الحساب
const UU = 'c1f2d3a4-1111-2222-3333-444455556666'; ACCTS = [{ kind: 'acct', a: UU, b: 'حساب أول بإسم طويل جداً جداً جداً جداً', c: 'USD' }, { kind: 'acct', a: '9a8b7c6d-1111-2222-3333-444455556666', b: 'دينار', c: 'IQD' }];
r = step('sn:in', { st: 'int', obj: 'trf', regs: [], ages: [], gen: 'a', lng: 'ar', ints: [], rp: 0, ip: 0 }); checkKb('acct', r.out);
ok('2 accounts → account screen with lowercase uuid callbacks ≤48', r.S.st === 'acct' && r.out.keyboard.flat().filter(b => /^sn:ac:[0-9a-f\-]{36}$/.test(b.c)).length === 2, r.out.keyboard);
r = step('sn:ac:9a8b7c6d-1111-2222-3333-444455556666', r.S); ok('pick IQD account → budget screen in IQD amounts', r.S.st === 'bud' && r.out.keyboard.flat().filter(b => /^sn:bu:(10000|25000|50000|100000)$/.test(b.c)).length === 4 && /IQD/.test(r.out.text), r.out.keyboard); checkKb('bud iqd', r.out);
r = step('sn:ac:not-mine', { st: 'acct', obj: 'trf', regs: [], ages: [], ints: [] }); ok('unknown account id ignored', r.S.acct === '' && r.S.st === 'acct', r.S);
ACCTS = [{ kind: 'acct', a: '6a74', b: 'خدمة', c: 'USD' }];
// 6) غير مربوط + أخطاء broker + بيانات تالفة
r = step('sn:s', null, null, false); ok('not linked message', /غير مربوط/.test(r.out.text) && r.out.edit === true, r.out.text);
const planX = run(D.plan, { Route: route('sn:o:sal') }, rows(r.S && null)); const outX = run(D.render, { 'SN2: plan': planX }, [{ ok: false, error: { message: 'Auth failed' } }]);
ok('broker error shown, no crash', /ما كدرت أقرأ البيانات من سناب: Auth failed/.test(outX[0].text) && outX[0].keyboard.length >= 1, outX[0].text);
const planY = run(D.plan, { Route: route('sn:xx:junk') }, [{ kind: 'acct', a: 'x', b: 'y', c: 'USD' }, { kind: 'state', a: '{broken', b: '1' }]); ok('corrupt state → fresh obj screen', planY[0].S.st === 'obj', planY[0].S);
const planZ = run(D.plan, { Route: route('sn:r:abc') }, [{ kind: 'acct', a: 'x', b: 'y', c: 'USD' }, { kind: 'state', a: JSON.stringify({ st: 'reg', obj: 'sal', regs: [] }), b: '1' }]); ok('invalid region id ignored', planZ[0].S.regs.length === 0, planZ[0].S);
// 7) نص عادي /snapwiz بدون cb
const planT = run(D.plan, { Route: { ctx: 'C', chatId: 1, cmd: 'snapwiz', args: '' } }, rows(null)); ok('/snapwiz text → start, no edit', planT[0].S.st === 'obj' && planT[0].edit === false, planT[0]);
// 8) reply
const rep = run(D.reply, { 'SN2: render': [{ ctx: 'C', chatId: 5, text: 'hi', keyboard: [[{ t: 'a', c: 'h' }]], edit: true, state: '{}' }] }, [{}]); ok('reply shape', rep[0].text === 'hi' && rep[0].edit === true && rep[0].keyboard.length === 1, rep);
ok('save sql uses ui_set with sn: key', /api\.ui_set\(\$1, 'sn:' \|\| \$2/.test(D.save) && /api\.ui_get\(\$1, 'sn:'/.test(D.sql) && /platform::text = 'snapchat'/.test(D.sql), [D.save, D.sql]);
console.log('SN2 tests: pass=' + pass + ' fail=' + fail); process.exit(fail ? 1 : 0);
