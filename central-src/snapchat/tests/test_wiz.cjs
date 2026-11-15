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
const rows = (state, linked = true) => [].concat(linked ? [{ kind: 'acct', a: '6a74', b: 'خدمة', c: 'USD' }] : [], state ? [{ kind: 'state', a: JSON.stringify(state), b: '5' }] : []);
function step(cb, state, results, linked = true) {
  const plan = run(D.plan, { Route: route(cb) }, rows(state, linked));
  const res = plan[0].need ? plan.map(p => ({ regs: regsRes, ints: intsRes }[p.k])) : [];
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
r = step('sn:i:slc_9', S); S = r.S; r = step('sn:in', S); S = r.S; checkKb('sum', r.out);
ok('summary text', S.st === 'sum' && r.plan.length === 2 && /ملخص الاستهداف/.test(r.out.text) && /الهدف: زيارات/.test(r.out.text) && /المحافظات: حلبجة/.test(r.out.text) && /الجنس: نساء/.test(r.out.text) && /Interest number 9/.test(r.out.text) && /مسودة استهداف فقط/.test(r.out.text), r.out.text);
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
