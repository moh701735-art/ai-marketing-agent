# -*- coding: utf-8 -*-
"""فيسبوك — معالج الحملة بالأهداف (p287): وعي / زيارات / تفاعل (وواتساب بمساره القديم). معالج مستقل بجانب معالج واتساب القديم (ما نلمسه).
callbacks بادئة `fm:` (wf_ingress يوجّهها cmd = fmwiz): fm:s · o:<هدف> · ac:<رقم> · bu:<n> · du:<n> · af:<n>/af0/at:<n>/aa · g:<a|m|f> · nt (اسم تلقائي) · go · b:<خطوة>.
إدخال نص (cmd = fmin من wf_ingress عندما تكون الخطوة post/url/nm): النص بـd.args. الدخول: /fbobj.
الحالة بـapi.ui_set بمفتاح fm:<chat> لمدة ساعة (اختيارات فقط). الإنشاء دائماً متوقف (PAUSED) عبر Broker العملية meta.launch_whatsapp مع objective_key. تلغرام: ≤8 صفوف، ≤3 أزرار بالصف، t ≤ 40."""

SQL_DATA = ("SELECT 'state'::text AS kind, data::text AS a, age_s::text AS b, NULL::text AS c FROM api.ui_get($1, 'fm:' || $2) "
            "UNION ALL SELECT 'acct', external_id::text, name::text, currency::text FROM api.list_ad_accounts($1) WHERE platform::text = 'meta' AND enabled")

LIB = r"""
const OBJ = { awareness: ['📣', 'وعي (وصول لأكبر عدد)', 'وصول'], traffic: ['🔗', 'زيارات لموقعك', 'نقرات على الرابط'], engagement: ['💬', 'تفاعل مع المنشور', 'تفاعلات'] };
const SOON = ['🎯 عملاء محتملين', '🛒 مبيعات', '📲 ترويج تطبيق'];
const GEN = { a: 'الكل', m: 'رجال', f: 'نساء' };
const GMAP = { m: ['1'], f: ['2'] };
const LINE = '━━━━━━━━━━━━━━';
const FX = 1555;
const sh = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const SEQ = o => ['obj', 'acct', 'post'].concat(o === 'traffic' ? ['url'] : []).concat(['bud', 'dur', 'age', 'gen', 'nm', 'sum']);
const BUDS = { IQD: [10000, 25000, 50000, 100000] }; const BUD_DEF = [5, 10, 20, 50, 100];
const DURS = [1, 3, 7, 14, 30];
const AGE_FROM = [18, 21, 25, 30, 35, 40, 45]; const AGE_TO = [24, 29, 34, 39, 44, 49];
const fnum = n => Number(n || 0).toLocaleString('en-US');
const hash36 = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(36); };
const ageTxt = S => S.amin ? ('من ' + S.amin + ' إلى ' + (S.amax ? S.amax : 'فما فوق')) : 'كل الأعمار (18+)';
const FBPOST = /https:\/\/(?:www\.|m\.|web\.|mbasic\.)?facebook\.com\/[^\s\x00-\x1f<>"']{4,400}|https:\/\/(?:fb\.watch|fb\.com)\/[^\s\x00-\x1f<>"']{3,200}/i;
"""

JS_PLAN = r"""
const d = $('Route').first().json;
const rows = $input.all().map(i => i.json).filter(r => r && r.kind);
const accts = rows.filter(r => r.kind === 'acct');
const ACCS = accts.map(r => ({ id: String(r.a), name: String(r.b || ''), cur: String(r.c || '').toUpperCase() })).filter(a => /^act_[0-9]{5,25}$/.test(a.id));
let S0 = null; const sr = rows.find(r => r.kind === 'state'); if (sr) { try { S0 = JSON.parse(sr.a); } catch (e) {} }
const isCb = !!d.cb;
const base = { ctx: d.ctx, chatId: d.chatId, edit: isCb, linked: ACCS.length > 0, items: 0, accts: ACCS };
const cmd = String(d.cmd || '');
const isIn = !isCb && cmd === 'fmin';
const p = isCb ? String(d.cb).split(':') : (isIn ? ['fm', 'ti'] : ['fm', 's']); const op = p[1] || 's', arg = p.slice(2).join(':');
const fresh = { st: 'obj', obj: '', acct: '', post: '', url: '', bud: 0, days: 0, amin: 0, amax: 0, aset: false, gen: 'a', nm: '' };
let S = (S0 && typeof S0 === 'object' && !Array.isArray(S0)) ? { ...fresh, ...S0 } : { ...fresh };
const num = s => /^\d{1,7}$/.test(String(s)) ? parseInt(s, 10) : 0;
const adv = () => {
  const q = SEQ(S.obj); const i = q.indexOf(S.st); S.st = q[Math.min(i < 0 ? 0 : i + 1, q.length - 1)];
  if (S.st === 'acct' && ACCS.length === 1) { S.acct = ACCS[0].id; S.st = q[q.indexOf('acct') + 1]; }
};
if (op === 's') S = { ...fresh };
else if (op === 'o') { if (OBJ[arg]) { S.obj = arg; S.st = 'obj'; adv(); } }
else if (op === 'ac') { const full = 'act_' + arg; if (ACCS.some(x => x.id === full)) { S.acct = full; S.st = 'acct'; adv(); } }
else if (op === 'af') { if (AGE_FROM.indexOf(num(arg)) >= 0) { S.amin = num(arg); S.amax = 0; S.aset = false; S.st = 'age'; } }
else if (op === 'af0') { S.amin = 0; S.amax = 0; S.aset = false; S.st = 'age'; }
else if (op === 'at') { if (arg === '0' || (AGE_TO.indexOf(num(arg)) >= 0 && num(arg) > S.amin)) { S.amax = num(arg); S.aset = true; S.st = 'age'; adv(); } }
else if (op === 'aa') { S.amin = 0; S.amax = 0; S.aset = true; S.st = 'age'; adv(); }
else if (op === 'g') { if (GEN[arg]) { S.gen = arg; S.st = 'gen'; adv(); } }
else if (op === 'bu') { const a = ACCS.find(x => x.id === S.acct); const L = (a && BUDS[a.cur]) || BUD_DEF; if (L.indexOf(num(arg)) >= 0) { S.bud = num(arg); S.st = 'bud'; adv(); } }
else if (op === 'du') { if (DURS.indexOf(num(arg)) >= 0) { S.days = num(arg); S.st = 'dur'; adv(); } }
else if (op === 'nt') { S.nm = ''; S.st = 'nm'; adv(); }
else if (op === 'ti') {
  const txt = String(d.args || '').trim();
  if (S.st === 'post') { const m = FBPOST.exec(txt); if (m) { S.post = m[0]; adv(); } else base.postBad = true; }
  else if (S.st === 'url') { const m = /^(https:\/\/[^\s\x00-\x1f<>"']{4,500})$/.exec(txt); if (m) { S.url = m[1]; adv(); } else base.linkBad = true; }
  else if (S.st === 'nm') { const v = txt.replace(/[\x00-\x1f<>]/g, ' ').replace(/\s+/g, ' ').trim(); if (v && v.length <= 40) { S.nm = v; adv(); } else base.nmBad = true; }
}
else if (op === 'go') { S.st = 'sum'; base.go = true; }
else if (op === 'b') { if (SEQ(S.obj).indexOf(arg) >= 0) { S.st = arg; if (arg === 'age') { S.amin = 0; S.amax = 0; S.aset = false; } } }
if (S.st !== 'obj' && !OBJ[S.obj]) S.st = 'obj';
if (SEQ(S.obj).indexOf(S.st) < 0) S.st = 'obj';
base.S = S;
const items = [];
if (base.go) {
  const a = ACCS.find(x => x.id === S.acct);
  if (!OBJ[S.obj]) base.goErr = 'اختر هدف الحملة أول.';
  else if (!a || !S.bud || !S.days || !FBPOST.test(S.post || '') || (S.obj === 'traffic' && !/^https:\/\//.test(S.url || ''))) base.goErr = 'ناقصة معلومات: تأكد من الحساب ورابط المنشور' + (S.obj === 'traffic' ? ' ورابط الموقع' : '') + ' والميزانية والمدة.';
  else {
    const nm = S.nm ? String(S.nm).slice(0, 120) : ('FB · ' + OBJ[S.obj][1] + ' · ' + new Date().toISOString().slice(5, 10)).slice(0, 120);
    const usd = a.cur === 'IQD' ? Math.round(S.bud / FX * 10000) / 10000 : S.bud;
    const prm = { objective_key: S.obj, post_url: S.post, budget_usd: usd, days: S.days, name: nm, budget_mode: 'total', countries: ['IQ'] };
    if (S.obj === 'traffic') prm.link_url = S.url;
    if (S.amin) { prm.age_min = S.amin; if (S.amax) prm.age_max = S.amax; }
    if (GMAP[S.gen]) prm.genders = GMAP[S.gen];
    const idem = ('fmw-' + String(d.chatId).replace(/[^0-9]/g, '') + '-' + hash36(JSON.stringify(prm)) + '-' + Math.floor(Date.now() / 120000)).slice(0, 90);
    items.push({ json: { ...base, need: true, k: 'go', platform: 'meta', ad_account: a.id, op: 'meta.launch_whatsapp', params: prm, idem, goName: nm } });
  }
}
base.items = items.length;
return items.length ? items.map(x => ({ json: { ...x.json, items: items.length } })) : [{ json: base }];
"""

JS_RENDER = r"""
const P = $('FM2: plan').all().map(i => i.json)[0];
const S = P.S; const R = {};
if (P.need) { $('FM2: plan').all().map(i => i.json).forEach((it, i) => { R[it.k] = $input.all().map(x => x.json)[i] || {}; }); }
const home = [[{ t: '🏠 الرئيسية', c: 'h' }]];
const done = (text, kb) => [{ json: { ctx: P.ctx, chatId: P.chatId, text: String(text).slice(0, 3800), keyboard: (kb || home).slice(0, 8), edit: P.edit, state: JSON.stringify(S) } }];
if (!P.linked) return [{ json: { ctx: P.ctx, chatId: P.chatId, text: '🔵 حسابك الإعلاني بفيسبوك غير مربوط بعد.\nاطلب من الإدارة ربط حساب ميتا ثم جرّب مرة ثانية.', keyboard: home, edit: P.edit } }];
const SQ = SEQ(S.obj || 'awareness');
const stepNo = () => (Math.max(0, SQ.indexOf(S.st)) + 1) + '/' + SQ.length;
const head = t => '🔵 حملة فيسبوك بالأهداف\n' + LINE + '\n' + t + '  [' + stepNo() + ']\n';
const prevOf = () => { const q = SQ; let i = q.indexOf(S.st) - 1; if (q[i] === 'acct' && (P.accts || []).length === 1) i--; return q[Math.max(0, i)]; };
const back = () => ({ t: '⬅️ رجوع', c: 'fm:b:' + prevOf() });
const chunk = (arr, n) => { const o = []; for (let i = 0; i < arr.length; i += n) o.push(arr.slice(i, i + n)); return o; };
const accOf = () => (P.accts || []).find(x => x.id === S.acct) || null;
const FR = { st: 'obj', obj: '', acct: '', post: '', url: '', bud: 0, days: 0, amin: 0, amax: 0, aset: false, gen: 'a', nm: '' };
const STG = { account: 'قراءة الحساب', post: 'قراءة المنشور', campaign: 'إنشاء الحملة', adset: 'إنشاء المجموعة الإعلانية', creative: 'إنشاء الكريتيف', ad: 'إنشاء الإعلان' };
if (P.go) {
  if (P.goErr) return done('⚠️ ' + P.goErr, [[{ t: '⬅️ رجوع للملخص', c: 'fm:b:sum' }]]);
  const r = R.go || {}, dd = r.data || {}, a = accOf();
  if (r.ok) {
    const cid = dd.campaign_id;
    const L = ['✅ انرفعت حملة فيسبوك (متوقفة)', LINE, '📣 الحملة: ' + (P.goName || ''), '🎯 الهدف: ' + OBJ[S.obj][1],
      '🆔 الحملة: ' + cid, '🆔 المجموعة: ' + dd.adset_id, '🆔 الإعلان: ' + dd.ad_id,
      '💰 الميزانية: ' + fnum(S.bud) + ' ' + (dd.currency || (a && a.cur) || '') + ' (إجمالية)',
      '📈 النتيجة تنقاس بـ: ' + OBJ[S.obj][2] + ' (مو رسائل)',
      '⏸️ الحالة: متوقفة' + (dd.readback && dd.readback.effective_status ? ' (ميتا: ' + dd.readback.effective_status + ')' : '') + '. ما فيه صرف لين تفعّلها.',
      '', 'للتفعيل بعد المراجعة: /fbactivate_' + cid, 'راجع الإعلان بـAds Manager قبل التفعيل.'];
    Object.keys(FR).forEach(k => { S[k] = FR[k]; });
    return done(L.join('\n'), [[{ t: '🔁 حملة جديدة', c: 'fm:s' }, { t: '🏠 الرئيسية', c: 'h' }]]);
  }
  const L = ['❌ ما اكتملت الحملة (المرحلة: ' + (STG[dd.stage] || dd.stage || '؟') + ')', LINE, String((r.error && (r.error.message || r.error.class)) || 'خطأ غير معروف من ميتا').slice(0, 500)];
  const cb = dd.created_before_failure;
  if (cb && cb.campaign_id) L.push('', '⚠️ انعملت حملة (متوقفة) برقم ' + cb.campaign_id + (cb.adset_id ? ' ومجموعة ' + cb.adset_id : '') + (cb.ad_id ? '' : ' بدون إعلان') + '. ما يصرف شي، احذفها أو كمّلها من Ads Manager.');
  L.push('', 'ما فعّلت شي.');
  return done(L.join('\n'), [[{ t: '⬅️ رجوع للملخص', c: 'fm:b:sum' }, { t: '🏠 الرئيسية', c: 'h' }]]);
}
if (S.st === 'obj') {
  const kb = chunk(Object.keys(OBJ).map(k => ({ t: OBJ[k][0] + ' ' + OBJ[k][1], c: 'fm:o:' + k })), 1); kb.push([{ t: '🏠 الرئيسية', c: 'h' }]);
  return done(head('اختر هدف الحملة') + 'الأهداف المتاحة الآن: وعي، زيارات، تفاعل.\nقريباً: ' + SOON.join('، ') + '.\nلحملة رسائل واتساب استخدم المعالج المعتاد (/fbwa).', kb);
}
if (S.st === 'acct') {
  const A = P.accts || []; const kb = A.slice(0, 6).map(x => [{ t: sh(x.name || x.id, 26) + (x.cur ? ' (' + x.cur + ')' : ''), c: 'fm:ac:' + x.id.slice(4) }]); kb.push([back()]);
  return done(head('اختر الحساب الإعلاني') + 'حسابات فيسبوك المربوطة:', kb);
}
if (S.st === 'post') {
  const kb = [[back()]];
  return done(head('رابط المنشور') + (P.postBad ? '⚠️ ما فهمت الرابط. لازم رابط منشور فيديو من فيسبوك (facebook.com أو fb.watch).\n\n' : '') + 'أرسل رابط المنشور (فيديو من صفحتك) كرسالة عادية. الإعلان يُبنى من هذا المنشور.', kb);
}
if (S.st === 'url') {
  const kb = [[back()]];
  return done(head('رابط موقعك') + (P.linkBad ? '⚠️ الرابط غير صالح، لازم يبدأ بـ https://\n\n' : '') + 'أرسل رابط الموقع اللي تريد الزوار يروحون له (https) كرسالة عادية.', kb);
}
if (S.st === 'bud') {
  const a = accOf(); const cur = a ? a.cur : ''; const L = BUDS[cur] || BUD_DEF;
  const kb = chunk(L.map(v => ({ t: (S.bud === v ? '✅ ' : '') + fnum(v) + ' ' + cur, c: 'fm:bu:' + v })), 3); kb.push([back()]);
  return done(head('اختر الميزانية') + 'الحساب: ' + (a ? a.name : '') + '\nالميزانية إجمالية للحملة كلها (مو يومية)، بعملة الحساب: ' + cur + '.', kb);
}
if (S.st === 'dur') {
  const kb = chunk(DURS.map(v => ({ t: (S.days === v ? '✅ ' : '') + v + (v === 1 ? ' يوم' : ' أيام'), c: 'fm:du:' + v })), 3); kb.push([back()]);
  return done(head('اختر مدة الحملة') + 'تبدأ بعد 10 دقايق تقريباً من الرفع، لكن تبقى متوقفة لين تفعّلها.', kb);
}
if (S.st === 'age') {
  if (!S.amin) {
    const kb = chunk(AGE_FROM.map(n => ({ t: n + '', c: 'fm:af:' + n })), 3); kb.push([{ t: 'كل الأعمار (18+)', c: 'fm:aa' }]); kb.push([back()]);
    return done(head('العمر: من أي عمر؟') + 'اختر الحد الأدنى للعمر. بعدها تختار الحد الأعلى.', kb);
  }
  const kb = chunk(AGE_TO.filter(n => n > S.amin).map(n => ({ t: 'إلى ' + n, c: 'fm:at:' + n })), 3); kb.push([{ t: 'فما فوق (بدون حد أعلى)', c: 'fm:at:0' }]); kb.push([{ t: '⬅️ غيّر الحد الأدنى', c: 'fm:af0' }]);
  return done(head('العمر: من ' + S.amin + ' إلى؟') + 'اختر الحد الأعلى للعمر.', kb);
}
if (S.st === 'gen') {
  const kb = [Object.keys(GEN).map(k => ({ t: (S.gen === k ? '✅ ' : '') + GEN[k], c: 'fm:g:' + k })), [back()]];
  return done(head('اختر الجنس'), kb);
}
if (S.st === 'nm') {
  const kb = [[{ t: '✔️ اسم تلقائي', c: 'fm:nt' }, back()]];
  return done(head('اسم الحملة') + (P.nmBad ? '⚠️ الاسم لازم يكون حتى 40 حرف.\n\n' : '') + 'أرسل اسم الحملة كرسالة عادية، أو دوس «اسم تلقائي».', kb);
}
// summary
const a2 = accOf();
const L = [head('ملخص الحملة').trimEnd(), '',
  '🎯 الهدف: ' + OBJ[S.obj][1], '🏢 الحساب: ' + (a2 ? a2.name + ' (' + a2.cur + ')' : 'غير محدد'),
  '🎬 المنشور: ' + (S.post ? sh(S.post, 60) : '❌ ناقص'), ...(S.obj === 'traffic' ? ['🔗 الموقع: ' + (S.url ? sh(S.url, 60) : '❌ ناقص')] : []),
  '📍 المكان: العراق', '🎂 العمر: ' + ageTxt(S), '🚻 الجنس: ' + GEN[S.gen], '',
  '💰 الميزانية: ' + (S.bud ? fnum(S.bud) + ' ' + ((a2 && a2.cur) || '') + ' (إجمالية)' : 'غير محددة'), '📅 المدة: ' + (S.days ? S.days + (S.days === 1 ? ' يوم' : ' أيام') : 'غير محددة'),
  '📈 النتيجة تنقاس بـ: ' + OBJ[S.obj][2] + ' (مو رسائل)', '🏷️ الاسم: ' + (S.nm || 'تلقائي'), '',
  '⏸️ تنرفع كحملة كاملة (حملة + مجموعة + إعلان) بحالة متوقفة، وما يصرف شي لين تفعّلها.'];
const ready = a2 && S.bud && S.days && S.post && (S.obj !== 'traffic' || S.url);
const kbS = []; if (ready) kbS.push([{ t: '🚀 رفع كحملة متوقفة', c: 'fm:go' }]);
kbS.push([{ t: '🔁 من جديد', c: 'fm:s' }, { t: '🎬 المنشور', c: 'fm:b:post' }, { t: '💰 الميزانية', c: 'fm:b:bud' }], [{ t: '🏠 الرئيسية', c: 'h' }]);
return done(L.join('\n'), kbS);
"""

JS_REPLY = r"""
const r = $('FM2: render').first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, keyboard: r.keyboard, edit: r.edit } }];
"""


def build(b, w, sw, idx, reply, CRT):
    code, pg, call_broker = b.code, b.pg, b.call_broker
    data = pg(w, "FM2: data", SQL_DATA, "={{ [$('Route').first().json.ctx, String($('Route').first().json.chatId)] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    plan = code(w, "FM2: plan", LIB + JS_PLAN)
    need = w.add("FM2: need broker?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.need ? 1 : 0 }}"})
    call = call_broker(w, "FM2: launch", mode="each")
    render = code(w, "FM2: render", LIB + JS_RENDER)
    save = pg(w, "FM2: save state",
              "SELECT CASE WHEN $3::text <> '' THEN api.ui_set($1, 'fm:' || $2, 'v', $3::jsonb, 3600)::text END AS saved",
              "={{ [$json.ctx, String($json.chatId), $json.state || ''] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    out = reply("FM2: reply", JS_REPLY)
    w.link(sw, data, idx)
    w.chain(data, plan, need)
    w.link(need, render, 0)
    w.link(need, call, 1)
    w.chain(call, render)
    w.chain(render, save, out)
