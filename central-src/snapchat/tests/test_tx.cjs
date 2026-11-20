// يختبر رفع سناب من رسالة نصية واحدة (op tx): نفس عقد SN2: plan/render الحقيقية. لا شبكة.
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.SN2_NODES || '/tmp/sn2_nodes.json', 'utf8'));
const J = a => a.map(x => ({ json: x })); let pass = 0, fail = 0;
const ok = (n, c, x) => { if (c) pass++; else { fail++; console.log('FAIL', n, x === undefined ? '' : JSON.stringify(x).slice(0, 500)); } };
function run(code, nodes, input) {
  const $ = n => { if (!(n in nodes)) throw new Error("Node '" + n + "' hasn't been executed"); const v = nodes[n]; return { first: () => ({ json: Array.isArray(v) ? v[0] : v }), all: () => J(Array.isArray(v) ? v : [v]) }; };
  return new Function('$', '$input', code)($, { all: () => J(input), first: () => ({ json: input[0] }) }).map(x => x.json);
}
const PIXRES = { ok: true, data: { pixels: [{ sub_request_status: 'SUCCESS', pixel: { id: 'bee15341-7ae6-477f-ae0f-b0f0db91347c', name: 'Main Pixel' } }] } };
const FID = 'BAACAgQAAxkBAAIBcmZ_video_file_id_12345'; const URL = 'https://wa.twasuliraq.com/w/hcnvkwua';
const A1 = { kind: 'acct', a: '6a74-aaaa', b: 'خدمة داتي محمد', c: 'USD' };
function tx(text, accts, extra) {
  const route = { ctx: 'CTX', chatId: 77, cmd: 'snaptext', args: text, ...(extra || {}) };
  const plan = run(D.plan, { Route: route }, accts);
  const res = plan[0].need ? plan.map(p => ({ pix: PIXRES }[p.k])) : [];
  const out = run(D.render, { 'SN2: plan': plan }, res)[0];
  return { plan, out, S: JSON.parse(out.state || 'null') };
}
const kbOk = o => { const kb = o.keyboard || []; return kb.length >= 1 && kb.length <= 8 && kb.every(r => r.length >= 1 && r.length <= 3 && r.every(b => b.t.length <= 40 && /^[a-z0-9_:-]{1,48}$/.test(b.c))) && o.text.length <= 3800; };
const withV = { fileId: FID, fileSize: 4000000, fileName: 'v.mp4' };
const OWNER = 'ارفع حمله سناب شات بحساب محمد مبيعا ' + URL + ' تواصل معنا واتساب يوم واحد الميزانيه 5دولار سميها فستان';

// 1) رسالة المالك الأصلية (مبيعات): يفهم كل شي، ويقف عند البكسل (المبيعات تحتاج بكسل) بدون أي رفع
let r = tx(OWNER, [A1], withV);
ok('1 sales: fields', r.S.obj === 'sal' && r.S.acct === '6a74-aaaa' && r.S.url === URL && r.S.days === 1 && r.S.bud === 5 && r.S.nm === 'فستان' && r.S.vid === FID, r.S);
ok('1 sales: stops at pixel step, nothing launched', r.S.st === 'pix' && !r.plan.some(p => p.k === 'go'), r.S.st);
ok('1 sales: note lists what was understood', /فهمت من رسالتك/.test(r.out.text) && /الحساب/.test(r.out.text) && /الميزانية: 5 USD/.test(r.out.text) && /الفيديو: وصل/.test(r.out.text), r.out.text);
ok('1 sales: kb valid', kbOk(r.out), r.out.keyboard);
// 2) نفس الرسالة بهدف زيارات: يصل للملخص وفيه زر الرفع
r = tx(OWNER.replace('مبيعا', 'زيارات'), [A1], withV);
ok('2 traffic: lands on summary', r.S.st === 'sum' && r.S.obj === 'trf', r.S);
ok('2 traffic: has launch button sn:go', JSON.stringify(r.out.keyboard).includes('sn:go'), r.out.keyboard);
ok('2 traffic: defaults Iraq/ar/all ages/all genders', r.S.regs.length === 0 && r.S.lng === 'ar' && r.S.gen === 'a' && !r.S.amin, r.S);
// 3) بدون فيديو: يسأل عن الفيديو
r = tx(OWNER.replace('مبيعا', 'زيارات'), [A1], {}); ok('3 no video → asks video', r.S.st === 'vid' && !r.S.vid, r.S.st);
// 4) حسابان واسم غير موجود: يسأل عن الحساب ويقول السبب
const A2 = { kind: 'acct', a: '7b85-bbbb', b: 'متجر النور', c: 'USD' };
r = tx(OWNER.replace('مبيعا', 'زيارات').replace('محمد', 'زين'), [A1, A2], withV);
ok('4 unknown account → asks account + reason', r.S.st === 'acct' && !r.S.acct && /ما لقيت حساب/.test(r.out.text), r.out.text);
r = tx(OWNER.replace('مبيعا', 'زيارات').replace('محمد', 'النور'), [A1, A2], withV); ok('4b matches second account by name', r.S.acct === '7b85-bbbb', r.S.acct);
// 5) ميزانية غير مدعومة / مدة غير مدعومة: تتحول لسؤال مع تنبيه، ولا تتخمّن
r = tx(OWNER.replace('مبيعا', 'زيارات').replace('5دولار', '7 دولار'), [A1], withV); ok('5 unsupported budget → asked, not guessed', !r.S.bud && r.S.st === 'bud' && /مو من خيارات/.test(r.out.text), r.out.text);
r = tx(OWNER.replace('مبيعا', 'زيارات').replace('يوم واحد', 'يومين'), [A1], withV); ok('5b unsupported duration → asked', !r.S.days && r.S.st === 'dur' && /مو من الخيارات/.test(r.out.text), r.out.text);
// 6) حساب دينار + «25 الف»
const AI = { kind: 'acct', a: '9c96-cccc', b: 'محمد دينار', c: 'IQD' };
r = tx('ارفع حملة سناب بحساب محمد زيارات ' + URL + ' يوم واحد ميزانية 25 الف', [AI], withV); ok('6 IQD 25 الف', r.S.bud === 25000 && r.S.st === 'sum', r.S);
r = tx('ارفع حملة سناب بحساب محمد زيارات ' + URL + ' يوم واحد ميزانية 5 دولار', [AI], withV); ok('6b $5 on IQD account → asked (no silent conversion)', !r.S.bud && /مو من خيارات/.test(r.out.text), r.out.text);
// 7) رابط ناقص لهدف يحتاجه
r = tx('ارفع حملة سناب بحساب محمد زيارات يوم واحد 5 دولار', [A1], withV); ok('7 traffic without link → asks link', r.S.st === 'url', r.S.st);
// 8) رقم بالرابط أو بالنص ما يتحول لميزانية
r = tx('ارفع حملة سناب بحساب محمد زيارات https://wa.twasuliraq.com/w/12345678 يوم واحد', [A1], withV); ok('8 digits in URL are not a budget', !r.S.bud, r.S.bud);
// 9) إدخال عدواني: الاسم يتنظف
r = tx(OWNER.replace('فستان', '<b>x</b>{"a":1}'), [A1], withV); ok('9 name sanitized', !/[<>]/.test(r.S.nm), r.S.nm);
// 10) حساب واحد فقط يُختار تلقائياً حتى بدون ذكر اسمه
r = tx('ارفع حملة سناب زيارات ' + URL + ' يوم واحد 5 دولار', [A1], withV); ok('10 single account auto', r.S.acct === A1.a && r.S.st === 'sum', r.S);
// 11) عملاء محتملين: غير متاح، رسالة صادقة
r = tx('ارفع حملة سناب عملاء محتملين بحساب محمد', [A1], withV); ok('11 leads → honest note', /عملاء محتملين/.test(r.out.text) && r.S.st === 'obj', r.out.text);
// 12) بدون حسابات سناب مربوطة: ما ينهار
let r12; try { r12 = tx(OWNER, [], withV); ok('12 no linked accounts: no crash', !!r12.out, r12.out); } catch (e) { ok('12 no linked accounts: no crash', false, e.message); }
// 13) فيديو كبير
r = tx(OWNER.replace('مبيعا', 'زيارات'), [A1], { fileId: FID, fileSize: 30000000 }); ok('13 big video rejected', !r.S.vid && /20MB/.test(r.out.text), r.out.text);
// 14) الاسم المخصص يدخل بطلب الرفع (go)
r = tx(OWNER.replace('مبيعا', 'زيارات'), [A1], withV);
const go = run(D.plan, { Route: { ctx: 'CTX', chatId: 77, cmd: 'snapwiz', cb: 'sn:go' } }, [A1, { kind: 'state', a: JSON.stringify(r.S), b: '5' }]);
ok('14 launch params carry custom name + file + url', go[0].k === 'go' && go[0].params.name === 'فستان' && go[0].params.file_id === FID && go[0].params.landing_url === URL && go[0].params.budget === 5, go[0].params);
console.log('TX tests: pass=' + pass + ' fail=' + fail); process.exit(fail ? 1 : 0);
