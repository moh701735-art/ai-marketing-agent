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
const PIXRES = { ok: true, data: { pixels: [{ sub_request_status: 'SUCCESS', pixel: { id: 'bee15341-7ae6-477f-ae0f-b0f0db91347c', name: 'Main Pixel' } }] } };
let ACCTS = [{ kind: 'acct', a: '6a74', b: 'خدمة', c: 'USD' }];
const rows = (state, linked = true) => [].concat(linked ? ACCTS : [], state ? [{ kind: 'state', a: JSON.stringify(state), b: '5' }] : []);
let pixRes = PIXRES;
function step(cb, state, results, linked = true) {
  const plan = run(D.plan, { Route: route(cb) }, rows(state, linked));
  const res = plan[0].need ? plan.map(p => ({ regs: regsRes, ints: intsRes, pix: pixRes, go: results }[p.k])) : [];
  const out = run(D.render, { 'SN2: plan': plan }, res);
  return { plan, out: out[0], S: JSON.parse(out[0].state || 'null') };
}
function checkKb(name, o) {
  const kb = o.keyboard || []; let good = kb.length >= 1 && kb.length <= 8 && o.text.length <= 3800;
  const bad = [];
  kb.forEach(r => { if (r.length < 1 || r.length > 3) bad.push('row ' + r.length); r.forEach(b => { if (typeof b.t !== 'string' || b.t.length < 1 || b.t.length > 40) bad.push('t:' + b.t); if (b.c && !/^[a-z0-9_:\-]{1,48}$/.test(b.c)) bad.push('c:' + b.c); }); });
  ok(name + ' keyboard rules', good && !bad.length, { rows: kb.length, bad, len: o.text.length });
}

const inStep = (extra, state) => { const plan = run(D.plan, { Route: { ctx: 'CTX', chatId: 77, cmd: 'snapin', ...extra } }, rows(state)); const out = run(D.render, { 'SN2: plan': plan }, [])[0]; return { plan, out, S: JSON.parse(out.state) }; };
const has = (o, re) => re.test(JSON.stringify(o.keyboard)) || re.test(o.text);
// 1) بداية: 4 أهداف
let r = step('sn:s', null); checkKb('start', r.out);
ok('obj screen: 4 objectives (sales, leads, traffic, views)', r.S.st === 'obj' && ['sal', 'led', 'trf', 'vid'].every(k => r.out.keyboard.flat().some(b => b.c === 'sn:o:' + k)) && !r.plan[0].need, r.out);
// 2) عملاء محتملين: رسالة صريحة ولا يتقدّم
r = step('sn:o:led', r.S); ok('leads: honest not-built note, stays at obj', r.S.st === 'obj' && r.S.obj === '' && /نموذج عملاء/.test(r.out.text), r.out.text); checkKb('led', r.out);
// 3) زيارات: obj → (حساب واحد تلقائي) → url
let S = step('sn:s', null).S; r = step('sn:o:trf', S); S = r.S; ok('trf: single account auto → url step', S.st === 'url' && S.acct === '6a74' && S.obj === 'trf' && !r.plan[0].need, S); checkKb('url', r.out);
ok('url screen asks for plain https message', /رسالة عادية/.test(r.out.text) && /1?\d\/1[0-9]/.test(r.out.text) || /\[3\/1\d\]/.test(r.out.text), r.out.text);
r = inStep({ args: 'not a link' }, S); ok('bad link at url step rejected, stays', r.S.st === 'url' && /غير صالح/.test(r.out.text), r.out.text);
r = inStep({ args: 'http://insecure.com' }, S); ok('http link rejected', r.S.st === 'url' && r.S.url === '', r.S);
r = inStep({ args: 'https://wa.me/9647811317191' }, S); S = r.S; ok('plain https text at url step accepted → regions', S.url === 'https://wa.me/9647811317191' && S.st === 'reg' && r.plan[0].edit === false, S);
// regions
r = step('sn:s', S); r = step('sn:b:reg', S); ok('reg needs regions read', r.plan[0].op === 'snapchat.t_regions' && r.plan[0].params.oid === 'iq', r.plan[0]); checkKb('reg', r.out);
ok('reg: 15 govs page1', r.out.keyboard.flat().filter(b => /^sn:r:\d+$/.test(b.c)).length === 15, r.out.keyboard.flat().map(b => b.t));
S = r.S; r = step('sn:r:25600', S); S = r.S; ok('toggle region on', S.regs[0] === '25600' && /✅ بغداد/.test(JSON.stringify(r.out.keyboard)), S);
r = step('sn:r:25600', S); S = r.S; ok('toggle off', S.regs.length === 0, S); r = step('sn:r:25600', S); S = r.S;
r = step('sn:rp:1', S); checkKb('reg p2', r.out); ok('page2 has 4', r.out.keyboard.flat().filter(b => /^sn:r:\d+$/.test(b.c)).length === 4, r.out.keyboard);
r = step('sn:rn', r.S); S = r.S; ok('regions next → age (from)', S.st === 'age' && !r.plan[0].need, S); checkKb('age from', r.out);
ok('age from screen: from buttons + all ages', [18, 21, 25, 30, 35, 40, 45].every(n => r.out.keyboard.flat().some(b => b.c === 'sn:af:' + n)) && r.out.keyboard.flat().some(b => b.c === 'sn:aa') && /من أي عمر/.test(r.out.text), r.out.keyboard);
// age from → to
r = step('sn:af:21', S); S = r.S; checkKb('age to', r.out); ok('from 21 → to screen without values ≤21', S.amin === 21 && S.st === 'age' && !S.aset && r.out.keyboard.flat().some(b => b.c === 'sn:at:24') && r.out.keyboard.flat().some(b => b.c === 'sn:at:0') && /من 21 إلى/.test(r.out.text), r.out.keyboard);
r = step('sn:af:45', S); ok('from 45: only 49 + open', r.out.keyboard.flat().filter(b => /^sn:at:(24|29|34|39|44)$/.test(b.c)).length === 0 && r.out.keyboard.flat().some(b => b.c === 'sn:at:49'), r.out.keyboard);
r = step('sn:at:20', S); ok('to ≤ from ignored', r.S.amax === 0 && r.S.st === 'age' && !r.S.aset, r.S);
r = step('sn:af0', S); ok('af0 resets from', r.S.amin === 0 && r.S.st === 'age', r.S);
r = step('sn:at:34', S); S = r.S; ok('to 34 → gender, range 21-34', S.amin === 21 && S.amax === 34 && S.st === 'gen', S); checkKb('gender', r.out);
let Sa = step('sn:af:25', step('sn:b:age', S).S).S; r = step('sn:at:0', Sa); ok('open-ended upper bound', r.S.amin === 25 && r.S.amax === 0 && r.S.st === 'gen' && r.S.aset, r.S);
r = step('sn:b:age', S); r = step('sn:aa', r.S); ok('all ages → no range, gender', r.S.amin === 0 && r.S.amax === 0 && r.S.st === 'gen', r.S);
r = step('sn:g:f', S); S = r.S; ok('gender → lng', S.gen === 'f' && S.st === 'lng', S); checkKb('lng', r.out);
r = step('sn:l:ar', S); S = r.S; ok('lng → int needs interests', S.st === 'int' && r.plan[0].op === 'snapchat.t_interests', r.plan[0]); checkKb('int', r.out);
for (let i = 5; i <= 17; i++) { r = step('sn:i:slc_' + i, S); S = r.S; } ok('interests capped 10', S.ints.length === 10, S.ints); r = step('sn:ic', S); S = r.S; r = step('sn:i:slc_9', S); S = r.S;
r = step('sn:in', S); S = r.S; ok('interests next → budget (account auto)', S.st === 'bud', S); checkKb('bud', r.out);
r = step('sn:bu:20', S); S = r.S; ok('budget → duration', S.bud === 20 && S.st === 'dur', S); checkKb('dur', r.out);
r = step('sn:bu:7', S); ok('invalid budget ignored', r.S.bud === 20, r.S);
r = step('sn:du:3', S); S = r.S; ok('duration → video step', S.days === 3 && S.st === 'vid' && /أرسل الفيديو/.test(r.out.text) && /إلزامي/.test(r.out.text) && !r.out.keyboard.flat().some(b => b.c === 'sn:vn'), r.out.text); checkKb('vid', r.out);
// video
r = inStep({ args: 'hello' }, S); ok('text at video step: asks for file', r.S.st === 'vid' && !r.S.vid && /ما استلمت فيديو/.test(r.out.text), r.out.text);
r = inStep({ fileId: 'BAACAgQAAxkBAAIBigabcdef', fileName: 'ad.mp4', fileSize: 30000000 }, S); ok('video >20MB rejected', !r.S.vid && /أكبر من 20MB/.test(r.out.text), r.out.text);
r = inStep({ fileId: 'bad id!' }, S); ok('invalid file id rejected', !r.S.vid, r.S);
r = inStep({ fileId: 'BAACAgQAAxkBAAIBigabcdef', fileName: 'ad.mp4', fileSize: 5000000 }, S); S = r.S; ok('video accepted, shows next button', S.vid === 'BAACAgQAAxkBAAIBigabcdef' && S.st === 'vid' && r.out.keyboard.flat().some(b => b.c === 'sn:vn') && /استلمت الفيديو/.test(r.out.text), r.out.text); checkKb('vid ok', r.out);
r = step('sn:vn', S); S = r.S; ok('video next → text step (cta for traffic)', S.st === 'txt' && r.out.keyboard.flat().filter(b => /^sn:ct:/.test(b.c)).length === 6, r.out.keyboard); checkKb('txt', r.out);
r = inStep({ args: 'x'.repeat(40) }, S); ok('long headline rejected', !r.S.hdl && /34 حرف/.test(r.out.text), r.out.text);
r = inStep({ args: 'خصم 50% على الشامبو' }, S); S = r.S; ok('headline saved, stays on txt', S.hdl === 'خصم 50% على الشامبو' && S.st === 'txt' && /انحفظ العنوان/.test(r.out.text), r.out.text);
r = step('sn:ct:shop_now', S); S = r.S; ok('cta set (lowercase callback)', S.cta === 'SHOP_NOW', S); r = step('sn:ct:hack', S); ok('bad cta ignored', r.S.cta === 'SHOP_NOW', r.S);
r = step('sn:tn', S); S = r.S; ok('text next → summary', S.st === 'sum', S); checkKb('sum', r.out);
ok('summary shows everything + go', r.out.keyboard.flat().some(b => b.c === 'sn:go') && /من 21 إلى 34/.test(r.out.text) && /الفيديو: ✅ جاهز/.test(r.out.text) && /الحساب: خدمة \(USD\)/.test(r.out.text) && /20 USD \(إجمالية\)/.test(r.out.text) && /خصم 50%/.test(r.out.text) && /wa\.me/.test(r.out.text), r.out.text);
// go
const GOOD = { ok: true, data: { campaign_id: 'camp-9', adsquad_id: 'sq-9', ad_id: 'ad-9', creative_id: 'cr-9', media_id: 'm-9', currency: 'USD', start_time: '2026-11-15T17:42:05.000-08:00', end_time: '2026-11-18T17:42:05.000-08:00', stage: 'ad' } };
r = step('sn:go', S, GOOD); const pr = r.plan[0].params;
ok('go params (traffic)', r.plan[0].op === 'snapchat.launch_draft' && pr.objective === 'trf' && pr.file_id === 'BAACAgQAAxkBAAIBigabcdef' && pr.min_age === 21 && pr.max_age === 34 && pr.landing_url === 'https://wa.me/9647811317191' && pr.cta === 'SHOP_NOW' && pr.headline === 'خصم 50% على الشامبو' && pr.budget === 20 && pr.days === 3 && !('pixel_id' in pr) && !('ages' in pr) && pr.brand_name === 'خدمة', pr);
ok('go idem safe', r.plan[0].idem.length >= 16 && r.plan[0].idem.length <= 100 && /^[A-Za-z0-9\-]+$/.test(r.plan[0].idem), r.plan[0].idem);
ok('go success text: full campaign + ad id', /انرفعت حملة سناب شات كاملة \(متوقفة\)/.test(r.out.text) && /camp-9/.test(r.out.text) && /sq-9/.test(r.out.text) && /ad-9/.test(r.out.text) && /متوقفة، ما فيه صرف/.test(r.out.text), r.out.text); checkKb('go ok', r.out);
ok('success resets state', r.S.st === 'obj' && r.S.obj === '' && r.S.vid === '' && r.S.url === '', r.S);
const idem1 = r.plan[0].idem; ok('double tap same idem', step('sn:go', S, GOOD).plan[0].idem === idem1);
// open-ended age: only min_age
{ const g = step('sn:go', { ...S, amin: 25, amax: 0 }, GOOD); ok('open upper age: min only', g.plan[0].params.min_age === 25 && !('max_age' in g.plan[0].params), g.plan[0].params); const g2 = step('sn:go', { ...S, amin: 0, amax: 0 }, GOOD); ok('all ages: no age params', !('min_age' in g2.plan[0].params) && !('max_age' in g2.plan[0].params)); }
// p197f: E3017 (pixel not eligible for PIXEL_PURCHASE) gets an Arabic explanation, other errors don't
{ const e3017 = 'Error code: E3017, message: validation failed because event source is ineligible for the optimization goal and conversion window. : [AdSquad ineligible for PIXEL_PURCHASE null]';
  r = step('sn:go', S, { ok: false, error: { class: 'bad_request', message: e3017 }, data: { stage: 'adsquad', campaign_id: 'camp-9' } });
  ok('E3017 shows Snap text + Arabic explanation + no fake success', /E3017/.test(r.out.text) && /البكسل غير مؤهل لتحسين الشراء/.test(r.out.text) && /Snap Events Manager/.test(r.out.text) && /camp-9/.test(r.out.text) && !/انرفعت حملة/.test(r.out.text), r.out.text); checkKb('E3017', r.out);
  r = step('sn:go', S, { ok: false, error: { class: 'bad_request', message: 'snap says no' }, data: { stage: 'adsquad', campaign_id: 'camp-9' } });
  ok('other errors: no pixel explanation', !/البكسل غير مؤهل/.test(r.out.text), r.out.text); }
// failures by stage
for (const [stage, label] of [['adsquad', 'إنشاء المجموعة الإعلانية'], ['upload', 'رفع الفيديو'], ['profile', 'البروفايل العام'], ['creative', 'إنشاء التصميم'], ['ad', 'إنشاء الإعلان'], ['media', 'إنشاء ملف الفيديو بسناب']]) {
  r = step('sn:go', S, { ok: false, error: { class: 'bad_request', message: 'snap says no' }, data: { stage, campaign_id: 'camp-9', adsquad_id: 'sq-9' } });
  ok('failure at ' + stage + ' honest', new RegExp('المرحلة: ' + label).test(r.out.text) && /snap says no/.test(r.out.text) && /camp-9/.test(r.out.text) && /احذف/.test(r.out.text) && !/انرفعت حملة/.test(r.out.text), r.out.text); checkKb('fail ' + stage, r.out);
  ok('failure keeps state', r.S.vid === 'BAACAgQAAxkBAAIBigabcdef' && r.S.bud === 20, r.S);
}
r = step('sn:go', { ...S, vid: '' }); ok('missing video blocked before broker', r.plan[0].goErr && !r.plan[0].need && /الفيديو/.test(r.out.text), r.out.text);
r = step('sn:go', { ...S, bud: 0 }); ok('missing budget blocked', /ناقصة معلومات/.test(r.out.text) && !r.plan[0].need, r.out.text);
r = step('sn:go', { ...S, url: '' }); ok('traffic without url blocked', /ناقصة معلومات/.test(r.out.text) && /الرابط/.test(r.out.text), r.out.text);
// 4) مشاهدات: بدون رابط ولا بكسل
S = step('sn:s', null).S; r = step('sn:o:vid', S); S = r.S; ok('views: no url step → regions directly', S.st === 'reg' && S.obj === 'vid', S);
{ let V = { ...S, st: 'txt', age: 0, amin: 0, bud: 20, days: 3, vid: 'BAACAgQAAxkBAAIBigabcdef', aset: true }; r = step('b', V); r = step('sn:b:txt', V); ok('views txt step has no CTA buttons', !r.out.keyboard.flat().some(b => /^sn:ct:/.test(b.c)), r.out.keyboard); r = step('sn:tn', V); V = r.S; ok('views summary has no link line', V.st === 'sum' && !/🔗 الرابط/.test(r.out.text) && r.out.keyboard.flat().some(b => b.c === 'sn:go'), r.out.text);
  r = step('sn:go', V, GOOD); ok('views go: no landing_url, no pixel', r.plan[0].params.objective === 'vid' && !('landing_url' in r.plan[0].params) && !('pixel_id' in r.plan[0].params), r.plan[0].params); }
// 5) مبيعات: بكسل
S = step('sn:s', null).S; r = step('sn:o:sal', S); S = r.S; ok('sales: account auto → pixel step reads pixels', S.st === 'pix' && r.plan[0].need && r.plan[0].op === 'snapchat.pixels' && r.plan[0].params.oid === '6a74', r.plan[0]);
checkKb('pix', r.out); ok('pixel list shown with lowercase uuid callback', r.out.keyboard.flat().some(b => b.c === 'sn:px:bee15341-7ae6-477f-ae0f-b0f0db91347c' && /Main Pixel/.test(b.t)), r.out.keyboard);
{ const saved = pixRes; pixRes = { ok: true, data: { pixels: [] } }; const e = step('sn:o:sal', step('sn:s', null).S); ok('no pixels: honest message, can go back', /ما لقيت بكسل/.test(e.out.text) && e.out.keyboard.flat().some(b => /^sn:b:/.test(b.c)), e.out.text); pixRes = { ok: false, error: { message: 'denied' } }; const e2 = step('sn:o:sal', step('sn:s', null).S); ok('pixel read error shown', /denied/.test(e2.out.text), e2.out.text); pixRes = saved; }
r = step('sn:px:bee15341-7ae6-477f-ae0f-b0f0db91347c', S); S = r.S; ok('pixel chosen → url step', S.pix === 'bee15341-7ae6-477f-ae0f-b0f0db91347c' && S.st === 'url', S);
r = step('sn:px:bad!', { ...S, st: 'pix', pix: '' }); ok('invalid pixel id ignored', r.S.pix === '', r.S);
{ const V = { ...S, st: 'sum', regs: [], amin: 0, aset: true, bud: 20, days: 3, vid: 'BAACAgQAAxkBAAIBigabcdef', url: 'https://t.me/x' }; r = step('sn:go', V, GOOD); ok('sales go: pixel_id + landing', r.plan[0].params.objective === 'sal' && r.plan[0].params.pixel_id === 'bee15341-7ae6-477f-ae0f-b0f0db91347c' && r.plan[0].params.landing_url === 'https://t.me/x', r.plan[0].params);
  r = step('sn:go', { ...V, pix: '' }); ok('sales without pixel blocked', /البكسل/.test(r.out.text) && !r.plan[0].need, r.out.text); }
// 6) /snaplink القديم ما زال يشتغل
const linkStep = (args, state) => { const plan = run(D.plan, { Route: { ctx: 'CTX', chatId: 77, cmd: 'snaplink', args } }, rows(state)); const out = run(D.render, { 'SN2: plan': plan }, [])[0]; return { plan, out, S: JSON.parse(out.state) }; };
r = linkStep('https://t.me/+abc123 ', { st: 'url', obj: 'trf', acct: '6a74' }); ok('/snaplink at url step advances', r.S.url === 'https://t.me/+abc123' && r.S.st === 'reg', r.S);
r = linkStep('http://x.com', { st: 'url', obj: 'trf', acct: '6a74' }); ok('/snaplink http rejected', /غير صالح/.test(r.out.text), r.out.text);
// 7) حسابين
const UU = 'c1f2d3a4-1111-2222-3333-444455556666'; ACCTS = [{ kind: 'acct', a: UU, b: 'حساب أول بإسم طويل جداً جداً جداً جداً', c: 'USD' }, { kind: 'acct', a: '9a8b7c6d-1111-2222-3333-444455556666', b: 'دينار', c: 'IQD' }];
r = step('sn:o:trf', step('sn:s', null).S); checkKb('acct', r.out); ok('2 accounts → account screen', r.S.st === 'acct' && r.out.keyboard.flat().filter(b => /^sn:ac:[0-9a-f\-]{36}$/.test(b.c)).length === 2, r.out.keyboard);
r = step('sn:ac:9a8b7c6d-1111-2222-3333-444455556666', r.S); ok('pick account → url step (traffic)', r.S.st === 'url' && r.S.acct === '9a8b7c6d-1111-2222-3333-444455556666', r.S);
{ const B = { ...r.S, st: 'dur', amin: 0, aset: true }; r = step('sn:b:bud', B); checkKb('bud iqd', r.out); ok('IQD budget buttons', r.out.keyboard.flat().filter(b => /^sn:bu:(10000|25000|50000|100000)$/.test(b.c)).length === 4 && /IQD/.test(r.out.text), r.out.keyboard); }
r = step('sn:ac:not-mine', { st: 'acct', obj: 'trf' }); ok('unknown account ignored', r.S.acct === '' && r.S.st === 'acct', r.S);
ACCTS = [{ kind: 'acct', a: '6a74', b: 'خدمة', c: 'USD' }];
// 8) غير مربوط + أخطاء + بيانات تالفة
r = step('sn:s', null, null, false); ok('not linked message', /غير مربوط/.test(r.out.text) && r.out.edit === true, r.out.text);
{ const planX = run(D.plan, { Route: route('sn:b:reg') }, rows({ st: 'reg', obj: 'trf', acct: '6a74', url: 'https://x.com' })); const outX = run(D.render, { 'SN2: plan': planX }, [{ ok: false, error: { message: 'Auth failed' } }]); ok('broker error shown', /ما كدرت أقرأ البيانات من سناب: Auth failed/.test(outX[0].text), outX[0].text); }
const planY = run(D.plan, { Route: route('sn:xx:junk') }, [{ kind: 'acct', a: 'x', b: 'y', c: 'USD' }, { kind: 'state', a: '{broken', b: '1' }]); ok('corrupt state → fresh obj', planY[0].S.st === 'obj', planY[0].S);
const planZ = run(D.plan, { Route: route('sn:r:abc') }, [{ kind: 'acct', a: 'x', b: 'y', c: 'USD' }, { kind: 'state', a: JSON.stringify({ st: 'reg', obj: 'trf', regs: [] }), b: '1' }]); ok('invalid region ignored', planZ[0].S.regs.length === 0, planZ[0].S);
const planS = run(D.plan, { Route: { ctx: 'C', chatId: 1, cmd: 'snapin', args: 'hi' } }, rows(null)); ok('snapin with no state → fresh obj, no crash', planS[0].S.st === 'obj', planS[0].S);
const planO = run(D.plan, { Route: { ctx: 'C', chatId: 1, cmd: 'snapwiz', args: '' } }, rows(null)); ok('/snapwiz text → start, no edit', planO[0].S.st === 'obj' && planO[0].edit === false, planO[0]);
// 9) reply + sql
const rep = run(D.reply, { 'SN2: render': [{ ctx: 'C', chatId: 5, text: 'hi', keyboard: [[{ t: 'a', c: 'h' }]], edit: true, state: '{}' }] }, [{}]); ok('reply shape', rep[0].text === 'hi' && rep[0].edit === true && rep[0].keyboard.length === 1, rep);
ok('save sql uses ui_set sn:', /api\.ui_set\(\$1, 'sn:' \|\| \$2/.test(D.save) && /api\.ui_get\(\$1, 'sn:'/.test(D.sql) && /platform::text = 'snapchat'/.test(D.sql), [D.save, D.sql]);
// 10) كل شاشة بحالة عميقة تحترم قيود تلغرام
{ const full = { st: 'sum', obj: 'sal', acct: '6a74', pix: 'bee15341-7ae6-477f-ae0f-b0f0db91347c', url: 'https://example.com/' + 'a'.repeat(200), regs: ['25600', '25601', '25602'], amin: 21, amax: 34, aset: true, gen: 'f', lng: 'ar', ints: ['SLC_1', 'SLC_2', 'SLC_3', 'SLC_4', 'SLC_5', 'SLC_6', 'SLC_7', 'SLC_8', 'SLC_9', 'SLC_10'], bud: 100, days: 30, vid: 'BAACAgQAAxkBAAIBigabcdef', vnm: 'a'.repeat(40), hdl: 'h'.repeat(34), cta: 'ORDER_NOW' };
  for (const st of ['obj', 'acct', 'pix', 'url', 'reg', 'age', 'gen', 'lng', 'int', 'bud', 'dur', 'vid', 'txt', 'sum']) { const o = step('sn:b:' + st, { ...full, st: 'sum' }); checkKb('deep ' + st, o.out); } }
console.log('SN2 tests: pass=' + pass + ' fail=' + fail); process.exit(fail ? 1 : 0);
