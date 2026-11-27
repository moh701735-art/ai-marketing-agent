// يشغّل عقد MP2: plan/render الحقيقية على كليشات: المحلل، بطاقة المراجعة، عناصر الإطلاق، النتائج، حالات الفشل.
const fs = require('fs'); const D = JSON.parse(fs.readFileSync(process.env.MP2_NODES || '/tmp/mp2_nodes.json', 'utf8'));
const J = a => a.map(x => ({ json: x })); let pass = 0, fail = 0;
const ok = (n, c, x) => { if (c) pass++; else { fail++; console.log('FAIL', n, x === undefined ? '' : JSON.stringify(x).slice(0, 600)); } };
function run(code, nodes, input) {
  const $ = n => { if (!(n in nodes)) throw new Error("Node '" + n + "' hasn't been executed"); const v = nodes[n]; return { first: () => ({ json: Array.isArray(v) ? v[0] : v }), all: () => J(Array.isArray(v) ? v : [v]) }; };
  return new Function('$', '$input', code)($, { all: () => J(input), first: () => ({ json: input[0] }) }).map(x => x.json);
}
for (const k of ['plan', 'render', 'reply']) { try { new Function('$', '$input', D[k]); pass++; } catch (e) { fail++; console.log('SYNTAX', k, e.message); } }
const ACC = [{ kind: 'acct', a: 'tiktok', b: '7700000000000000001', c: 'بنين', d: 'USD' }, { kind: 'acct', a: 'tiktok', b: '7700000000000000002', c: 'عمار IQD', d: 'IQD' },
  { kind: 'acct', a: 'meta', b: '898845696108142', c: 'Noor', d: 'USD' }, { kind: 'acct', a: 'snapchat', b: 'aaaaaaaa-1111', c: 'سناب محمد', d: 'USD' }];
const PG = n => Array.from({ length: n }, (_, i) => ({ kind: 'page', a: String(100000 + i), b: i === 0 ? 'مركز الارتقاء الطبي للتجميل' : i === 1 ? 'مركز الارتقاء الثاني' : 'صفحة ' + i }));
const rows = (o = {}) => [].concat(o.acc || ACC, o.pages || [], o.state ? [{ kind: 'state', a: JSON.stringify(o.state), b: String(o.age == null ? 5 : o.age) }] : []);
const route = (cb, extra) => ({ ctx: 'CTX', chatId: 77, cmd: cb ? 'promocb' : 'promo', cb, ...extra });
function step(cb, o = {}, extra = {}, results) {
  const plan = run(D.plan, { Route: route(cb, extra) }, rows(o));
  const res = plan[0].need ? plan.map((_, i) => (results ? (Array.isArray(results) ? results[i] : results) : { ok: true, data: {} })) : [];
  const out = run(D.render, { 'MP2: plan': plan }, res); return { plan, out: out[0], S: out[0].state ? JSON.parse(out[0].state) : null };
}
function kbOk(name, o) { const kb = o.keyboard || []; let good = kb.length >= 1 && kb.length <= 8 && o.text.length <= 3800; kb.forEach(r => { if (r.length < 1 || r.length > 3) good = false; r.forEach(b => { if (!b.t || b.t.length > 40 || (b.c && !/^[A-Za-z0-9_:\-]{1,48}$/.test(b.c))) good = false; }); }); ok(name + ' keyboard rules', good, o); }
const KL = (o = {}) => `روّج: ${o.plats || 'تيك توك + فيسبوك + سناب'}
الميزانية: ${o.bud || '20 دولار (لكل منصة)'}
المدة: ${o.days || 'يوم واحد'}
العمر: ${o.age || '25-45'}
الجنس: ${o.gen || 'الكل'}
الاسم: عطر الشتاء

— تيك توك —
كود: ${o.code || 'AbCdEf123456'}
هدف: محادثات واتساب 07829503973
حساب: بنين

— فيسبوك —
${o.fb || 'https://www.facebook.com/share/r/1FKBRTjVAn/'}
هدف: ${o.fbobj || 'رسائل واتساب 07811317191'}
حساب: Noor
${o.page !== undefined ? o.page : 'صفحة: الارتقاء الطبي'}

— سناب —
هدف: ${o.snapobj || 'زيارات https://wa.twasuliraq.com/w/abc12345'}
حساب: سناب محمد
(الفيديو مرفق بنفس الرسالة)`;
const FILE = { fileId: 'BAACAgQAAxkBAAIxxxxxxxxxxxx', fileSize: 1000000, fileName: 'v.mp4' };
// 1) كليشة المالك الحرفية: توقف بالأخطاء الثلاثة، بدون أي إنشاء
const OWNER = `روّج: تيك توك + فيسبوك + سناب
الميزانية: 20 دولار (لكل منصة)
المدة: يوم واحد
العمر: 25-45
الجنس: الكل
الاسم: عطر الشتاء

— تيك توك —
كود: #XXXXXXXXXXXX
هدف: محادثات واتساب 07829503973
حساب: بنين

— فيسبوك —
https://www.facebook.com/share/r/1FKBRTjVAn/
هدف: رسائل واتساب 07811317191
حساب: Noor
صفحة: مركز الارتقاء

— سناب —
هدف: زيارات 
حساب: اسم حساب سناب
(الفيديو مرفق بنفس الرسالة)`;
let r = step(null, { pages: PG(13) }, { args: OWNER }); kbOk('owner sample', r.out);
ok('owner sample: halts, no broker, no state', !r.plan[0].need && r.S === null && /ما قدرت أكمل/.test(r.out.text) && /الكود مثال/.test(r.out.text) && /الفيديو لازم/.test(r.out.text) && /رابط الوجهة/.test(r.out.text), r.out.text);
// 2) كليشة صحيحة: بطاقة مراجعة
r = step(null, { pages: PG(13) }, { args: KL(), ...FILE }); kbOk('review', r.out);
ok('review: card with amounts/total/duration/age', /20\$ لكل منصة × 3 = \$60/.test(r.out.text.replace('$20', '20$')) || /\$20 لكل منصة × 3 = \$60/.test(r.out.text), r.out.text);
ok('review: per platform lines + honest snap paused + no-guard warning', /تيك توك: حساب «بنين» \(USD\)/.test(r.out.text) && /فيسبوك\/إنستغرام: حساب «Noor»/.test(r.out.text) && /سناب: حساب «سناب محمد»/.test(r.out.text) && /مسودة متوقفة/.test(r.out.text) && /ما عندهم إيقاف صرف تلقائي/.test(r.out.text), r.out.text);
ok('review: page resolved by name, buttons go/cancel, state saved', /مركز الارتقاء الطبي للتجميل|الارتقاء/.test(r.out.text) && r.out.keyboard.flat().some(b => b.c === 'mp:go') && r.out.keyboard.flat().some(b => b.c === 'mp:x') && r.S && r.S.st === 'ready' && r.S.fid === FILE.fileId, r.S);
const READY = r.S;
// 3) تأكيد: عناصر الإطلاق
r = step('mp:go', { pages: PG(13), state: READY }, {}, null); const it = r.plan;
ok('go: 3 broker items with the real ops', it.length === 3 && it.map(x => x.op).join() === 'tiktok.launch_spark,meta.launch_whatsapp,snapchat.launch_draft', it.map(x => x.op));
const tt = it[0], mt = it[1], sn = it[2];
ok('tiktok params', tt.platform === 'tiktok' && tt.ad_account === '7700000000000000001' && tt.params.objective === 'whatsapp' && tt.params.budget === 20 && tt.params.budget_mode === 'total' && tt.params.days === 1 && tt.params.spark_codes[0] === 'AbCdEf123456' && tt.params.whatsapp_number === '07829503973' && tt.params.activate_now === true && tt.params.age_min === 25 && tt.params.age_max === 45 && tt.params.campaign_name === 'عطر الشتاء', tt);
ok('meta params (whatsapp legacy path, page_id, live)', mt.platform === 'meta' && mt.ad_account === 'act_898845696108142' && mt.params.post_url.includes('facebook.com') && mt.params.whatsapp === '07811317191' && mt.params.budget_usd === 20 && mt.params.budget_mode === 'total' && mt.params.page_id === '100000' && mt.params.activate_now === true && !('objective_key' in mt.params) && mt.params.countries[0] === 'IQ', mt.params);
ok('snap params (draft, file id, landing, no activation flag)', sn.platform === 'snapchat' && sn.ad_account === '' && sn.params.account_id === 'aaaaaaaa-1111' && sn.params.objective === 'trf' && sn.params.file_id === FILE.fileId && sn.params.landing_url === 'https://wa.twasuliraq.com/w/abc12345' && sn.params.budget === 20 && !('activate_now' in sn.params), sn.params);
ok('idem keys distinct and 16..90', new Set(it.map(x => x.idem)).size === 3 && it.every(x => x.idem.length >= 16 && x.idem.length <= 90), it.map(x => x.idem));
ok('go saves done state', r.S && r.S.st === 'done', r.S);
// 4) نتائج: نجاح/فشل جزئي مستقل
const okTT = { ok: true, data: { campaign_id: '111' } }, badMeta = { ok: false, error: { class: 'bad_request', message: 'Meta says no' }, data: { stage: 'adset', created_before_failure: { campaign_id: '222' } } }, okSn = { ok: true, data: { campaign_id: 'sn-1' } };
r = step('mp:go', { pages: PG(13), state: READY }, {}, [okTT, badMeta, okSn]); kbOk('results', r.out);
ok('results: independent per platform, partial failure verbatim, no rollback claim', /تيك توك: ✅/.test(r.out.text) && /فيسبوك\/إنستغرام: ❌ Meta says no/.test(r.out.text) && /222/.test(r.out.text) && /سناب: ✅ انرفعت مسودة متوقفة/.test(r.out.text) && /ما فيه تراجع تلقائي/.test(r.out.text), r.out.text);
r = step('mp:go', { pages: PG(13), state: READY }, {}, [{ ok: false, error: { message: 'post_not_from_selected_page' } }, okTT, okSn]);
// 5) بطاقة قديمة/ملغاة
r = step('mp:go', { pages: PG(13) }, {}); ok('go without state → stale, no broker', !r.plan[0].need && /انتهت صلاحية/.test(r.out.text), r.out.text);
r = step('mp:go', { pages: PG(13), state: READY, age: 2000 }, {}); ok('go with old state (>30 min) → stale', !r.plan[0].need && /انتهت صلاحية/.test(r.out.text), r.out.text);
r = step('mp:go', { pages: PG(13), state: { st: 'done' } }, {}); ok('go after done → stale (no double launch)', !r.plan[0].need, r.out.text);
r = step('mp:x', { state: READY }, {}); ok('cancel → no broker, done state', !r.plan[0].need && /انلغت/.test(r.out.text) && r.S.st === 'done', r.out.text);
// 6) صفحات: غامض/ناقص/وحيدة/صفر
r = step(null, { pages: PG(13) }, { args: KL({ page: 'صفحة: الارتقاء' }), ...FILE }); ok('ambiguous page name (2 match) → halt with candidates', /الصفحة/.test(r.out.text) && /أكثر من واحد/.test(r.out.text) && r.S === null, r.out.text);
r = step(null, { pages: PG(13) }, { args: KL({ page: '' }), ...FILE }); ok('2+ pages and none given → asks «صفحة:»', /الصفحة: اكتب «حساب: الاسم»|الصفحة/.test(r.out.text) && r.S === null, r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ page: '' }), ...FILE }); ok('single page auto', r.S && r.S.R.page.id === '100000', r.out.text);
r = step(null, { pages: [] }, { args: KL({ page: '' }), ...FILE }); ok('no pages: proceeds without page_id', r.S && !r.S.R.page && !/صفحة «/.test(r.out.text), r.out.text);
r = step('mp:go', { pages: [], state: r.S }, {}); ok('no pages: no page_id param', !('page_id' in r.plan[1].params), r.plan[1].params);
// 7) ميزانية: عملة وحدود
r = step(null, { pages: PG(1) }, { args: KL({ bud: '400 دولار' }), ...FILE }); ok('budget over cap refused', /أكبر من الحد الأقصى/.test(r.out.text) && !r.plan[0].need, r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ bud: '30 الف' }), ...FILE }); ok('30 الف = IQD → ~19.29$ per platform', r.S && Math.abs(r.S.P.bud.usd - 19.2926) < 0.01 && r.S.P.bud.cur === 'IQD', r.S && r.S.P.bud);
r = step(null, { pages: PG(1) }, { args: KL({ bud: '5000' }), ...FILE }); ok('bare 5000 = dinar', r.S && r.S.P.bud.cur === 'IQD', r.S && r.S.P.bud);
r = step(null, { pages: PG(1) }, { args: KL({ bud: '5' }), ...FILE }); ok('bare 5 = dollars', r.S && r.S.P.bud.cur === 'USD' && r.S.P.bud.usd === 5, r.S && r.S.P.bud);
r = step(null, { pages: PG(1) }, { args: KL({ bud: ' ' }) , ...FILE }); ok('missing budget → halt', /ناقصة الميزانية/.test(r.out.text), r.out.text);
// 8) مدة/عمر/جنس
for (const [t, n] of [['يومين', 2], ['3 أيام', 3], ['ثلاث ايام', 3], ['يوم واحد', 1], ['7 ايام', 7]]) { r = step(null, { pages: PG(1) }, { args: KL({ days: t }), ...FILE }); ok('days «' + t + '»', r.S && r.S.P.days === n, r.S && r.S.P.days); }
r = step(null, { pages: PG(1) }, { args: KL({ days: 'غدا' }), ...FILE }); ok('days unreadable → halt', /ناقصة المدة/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ age: 'كل الأعمار' }), ...FILE }); ok('all ages', r.S && r.S.P.age.min === 0, r.S && r.S.P.age);
r = step(null, { pages: PG(1) }, { args: KL({ age: '17-30' }), ...FILE }); ok('age <18 refused', /العمر غير مفهوم/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ gen: 'نساء' }), ...FILE }); ok('gender women: warning on tiktok/fb-whatsapp, card shows it', /الجنس يُطبَّق على فيسبوك/.test(r.out.text), r.out.text);
// 9) منصات منفردة وأهداف فيسبوك
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'فيسبوك', fbobj: 'تفاعل', gen: 'نساء' }), ...FILE }); ok('facebook only, engagement objective', r.S && r.S.P.plats.join() === 'meta', r.out.text);
r = step('mp:go', { pages: PG(1), state: r.S }, {}); ok('single platform → one item with objective_key + genders', r.plan.length === 1 && r.plan[0].params.objective_key === 'engagement' && r.plan[0].params.genders[0] === '2' && !('whatsapp' in r.plan[0].params), r.plan[0]);
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'فيسبوك', fbobj: 'زيارات' }), ...FILE }); ok('traffic needs https site link', /رابط موقع https/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'فيسبوك', fbobj: 'زيارات https://example.com/shop' }), ...FILE }); r = step('mp:go', { pages: PG(1), state: r.S }, {}); ok('traffic → objective_key traffic + link_url', r.plan[0].params.objective_key === 'traffic' && r.plan[0].params.link_url === 'https://example.com/shop', r.plan[0].params);
r = step(null, { pages: PG(1) }, { args: KL({ fb: 'https://example.com/x' }), ...FILE }); ok('non-facebook link refused', /ناقص رابط منشور/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'سناب', snapobj: 'مبيعات' }), ...FILE }); ok('snap sales unsupported (honest)', /زيارات» فقط/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'تيك توك' }) }); ok('tiktok only needs no file', r.S && r.S.P.plats.join() === 'tt', r.out.text);
r = step('mp:go', { pages: PG(1), state: r.S }, {}); ok('tiktok only: one item, no snap/meta', r.plan.length === 1 && r.plan[0].op === 'tiktok.launch_spark', r.plan.map(x => x.op));
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'تيك توك', code: 'AbCdEf123456 ZyXwVu987654' }), ...FILE }); ok('two spark codes', r.S && r.S.P.tt.codes.length === 2, r.S && r.S.P.tt.codes);
// 10) IQD: ميزانية بعملة حساب تيك توك
const ACC2 = ACC.map(a => a.a === 'tiktok' && a.c === 'بنين' ? { ...a, c: 'بنين', d: 'IQD' } : a);
r = step(null, { pages: PG(1), acc: ACC2 }, { args: KL({ plats: 'تيك توك' }) }); r = step('mp:go', { pages: PG(1), acc: ACC2, state: r.S }, {}); ok('IQD tiktok account → budget converted (20$ × 1555)', r.plan[0].params.budget === 31100, r.plan[0].params);
// 11) حسابات: غامض/غير موجود/غير مربوط
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'تيك توك' }).replace('حساب: بنين', 'حساب: ع'), ...FILE }); ok('ambiguous account name', /تيك توك: «ع»/.test(r.out.text) || /أكثر من واحد|غير موجود/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'تيك توك' }).replace('حساب: بنين', 'حساب: زززز'), ...FILE }); ok('unknown account', /غير موجود بحساباتك/.test(r.out.text), r.out.text);
r = step(null, { pages: PG(1), acc: ACC.filter(a => a.a !== 'meta') }, { args: KL({ plats: 'فيسبوك' }), ...FILE }); ok('facebook not linked', /ما عندك حساب مربوط/.test(r.out.text) && !r.plan[0].need, r.out.text);
r = step(null, { pages: PG(1) }, { args: 'روّج: تيك توك\nالميزانية: 5 دولار\nالمدة: يوم\nالعمر: 25-45\n— تيك توك —\nكود: AbCdEf123456\nهدف: محادثات واتساب 07829503973', ...FILE }); ok('account omitted + 2 tiktok accounts → asks', /اكتب «حساب: الاسم»/.test(r.out.text), r.out.text);
// 12) ما يشتغل بدون أول سطر صحيح
r = step(null, { pages: PG(1) }, { args: 'مرحبا\nالميزانية: 5', ...FILE }); ok('no header → platforms error', /ما فهمت المنصات/.test(r.out.text), r.out.text);
// 13) تنقية: بدون HTML/تحكم، اسم طويل
r = step(null, { pages: PG(1) }, { args: KL({ plats: 'تيك توك' }).replace('الاسم: عطر الشتاء', 'الاسم: <b>x</b>' + 'ص'.repeat(80)), ...FILE }); ok('name sanitized and capped at 40', r.S && !/[<>]/.test(r.S.P.name) && r.S.P.name.length <= 40, r.S && r.S.P.name);
// 14) caption بدل args، أرقام عربية
r = step(null, { pages: PG(1) }, { caption: KL({ plats: 'تيك توك', bud: '٢٠ دولار', days: '١ يوم' }), ...FILE }); ok('caption + Arabic digits', r.S && r.S.P.bud.usd === 20 && r.S.P.days === 1, r.S && r.S.P);
console.log('PASS', pass, 'FAIL', fail); process.exit(fail ? 1 : 0);
