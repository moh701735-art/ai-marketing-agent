# -*- coding: utf-8 -*-
"""سناب شات — معالج الاستهداف (المرحلة 2/أ: واجهة واستهداف فقط، لا تُنشأ حملة).
callbacks بادئة `sn:` (يوجّهها wf_ingress إلى cmd = snapwiz): sn:s (بداية) · sn:o:<هدف> · sn:r:<id> / ra / rc / rp:<n> / rn · sn:a:<كود> / aa / an · sn:g:<a|m|f> · sn:l:<لغة> · sn:i:<id> / ic / ip:<n> / in · sn:b:<شاشة>.
بيانات العراق (المحافظات 19 + اهتمامات SCL ≈150 مع country_code=iq) تُقرأ حيّة من سناب عبر الـBroker (قراءة فقط): snapchat.t_regions / snapchat.t_interests.
الحالة تُخزَّن بـapi.ui_set بمفتاح sn:<chat> لمدة ساعة (اختيارات فقط، بدون قوائم). مقيّدات تلغرام: ≤8 صفوف، ≤3 أزرار بالصف، t ≤ 40."""

SQL_DATA = ("SELECT 'state'::text AS kind, data::text AS a, age_s::text AS b, NULL::text AS c FROM api.ui_get($1, 'sn:' || $2) "
            "UNION ALL SELECT 'acct', external_id::text, name::text, currency::text FROM api.list_ad_accounts($1) WHERE platform::text = 'snapchat' AND enabled")

LIB = r"""
const OBJ = { sal: ['🛒', 'مبيعات'], msg: ['💬', 'رسائل سناب شات'], led: ['🎯', 'عملاء محتملين'], trf: ['🔗', 'زيارات'] };
const AGES = { a1: '18-20', a2: '21-24', a3: '25-34', a4: '35+' };
const LNG = { '': 'كل اللغات', ar: 'العربية', en: 'English', ku: 'کوردی' };
const GEN = { a: 'الكل', m: 'رجال', f: 'نساء' };
const GOV = [['baghdad', 'بغداد'], ['basra', 'البصرة'], ['basrah', 'البصرة'], ['ninev', 'نينوى'], ['ninaw', 'نينوى'], ['nainaw', 'نينوى'], ['mosul', 'نينوى'], ['erbil', 'أربيل'], ['arbil', 'أربيل'], ['irbil', 'أربيل'], ['sulaym', 'السليمانية'], ['sulaim', 'السليمانية'], ['dohuk', 'دهوك'], ['duhok', 'دهوك'], ['dahuk', 'دهوك'], ['kirkuk', 'كركوك'], ['tamim', 'كركوك'], ['anbar', 'الأنبار'], ['babil', 'بابل'], ['babylon', 'بابل'], ['karbala', 'كربلاء'], ['najaf', 'النجف'], ['diyala', 'ديالى'], ['wasit', 'واسط'], ['maysan', 'ميسان'], ['misan', 'ميسان'], ['dhiqar', 'ذي قار'], ['thiqar', 'ذي قار'], ['muthanna', 'المثنى'], ['qadis', 'القادسية'], ['diwaniy', 'القادسية'], ['salah', 'صلاح الدين'], ['saladin', 'صلاح الدين'], ['halabja', 'حلبجة']];
const arGov = n => { const k = String(n || '').toLowerCase().replace(/[^a-z]/g, ''); const h = GOV.find(g => k.indexOf(g[0]) >= 0); return h ? h[1] : String(n || ''); };
const LINE = '━━━━━━━━━━━━━━';
const sh = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const STEPS = ['obj', 'reg', 'age', 'gen', 'lng', 'int', 'sum'];
const STN = { obj: 'الهدف', reg: 'المحافظات', age: 'العمر', gen: 'الجنس', lng: 'اللغة', int: 'الاهتمامات', sum: 'الملخص' };
"""

JS_PLAN = r"""
const d = $('Route').first().json;
const rows = $input.all().map(i => i.json).filter(r => r && r.kind);
const accts = rows.filter(r => r.kind === 'acct');
let S0 = null; const sr = rows.find(r => r.kind === 'state'); if (sr) { try { S0 = JSON.parse(sr.a); } catch (e) {} }
const isCb = !!d.cb;
const base = { ctx: d.ctx, chatId: d.chatId, edit: isCb, linked: accts.length > 0, items: 0 };
const p = isCb ? String(d.cb).split(':') : ['sn', 's']; const op = p[1] || 's', arg = p.slice(2).join(':');
const fresh = { st: 'obj', obj: '', regs: [], ages: [], gen: 'a', lng: 'ar', ints: [], rp: 0, ip: 0 };
let S = (S0 && typeof S0 === 'object' && !Array.isArray(S0)) ? { ...fresh, ...S0 } : { ...fresh };
if (!Array.isArray(S.regs)) S.regs = []; if (!Array.isArray(S.ages)) S.ages = []; if (!Array.isArray(S.ints)) S.ints = [];
const tog = (arr, v, max) => { const i = arr.indexOf(v); if (i >= 0) { arr.splice(i, 1); return arr; } if (arr.length < max) arr.push(v); return arr; };
const num = s => /^\d{1,6}$/.test(String(s)) ? parseInt(s, 10) : 0;
if (op === 's') S = { ...fresh };
else if (op === 'o') { if (OBJ[arg]) { S.obj = arg; S.st = 'reg'; S.rp = 0; } }
else if (op === 'r') { if (/^\d{1,12}$/.test(arg)) S.regs = tog(S.regs, arg, 19); S.st = 'reg'; }
else if (op === 'ra' || op === 'rc') { S.regs = []; S.st = 'reg'; }
else if (op === 'rp') { S.rp = num(arg); S.st = 'reg'; }
else if (op === 'rn') S.st = 'age';
else if (op === 'a') { if (AGES[arg]) S.ages = tog(S.ages, arg, 4); S.st = 'age'; }
else if (op === 'aa') { S.ages = []; S.st = 'age'; }
else if (op === 'an') S.st = 'gen';
else if (op === 'g') { if (GEN[arg]) { S.gen = arg; S.st = 'lng'; } }
else if (op === 'l') { if (arg in LNG) { S.lng = arg; S.st = 'int'; S.ip = 0; } }
else if (op === 'i') { if (/^slc_\d{1,6}$/i.test(arg)) S.ints = tog(S.ints, arg.toUpperCase(), 10); S.st = 'int'; }
else if (op === 'ic') { S.ints = []; S.st = 'int'; }
else if (op === 'ip') { S.ip = num(arg); S.st = 'int'; }
else if (op === 'in') S.st = 'sum';
else if (op === 'b') { if (STEPS.indexOf(arg) >= 0) S.st = arg; }
if (!OBJ[S.obj] && S.st !== 'obj') S.st = 'obj';
base.S = S;
const items = [];
const need = (k, o, params) => items.push({ json: { ...base, need: true, k, platform: 'snapchat', ad_account: '', op: o, params } });
if (base.linked) {
  if (S.st === 'reg' || (S.st === 'sum' && S.regs.length)) need('regs', 'snapchat.t_regions', { oid: 'iq' });
  if (S.st === 'int' || (S.st === 'sum' && S.ints.length)) need('ints', 'snapchat.t_interests', { oid: 'scls', country_code: 'iq' });
}
base.items = items.length;
return items.length ? items.map(x => ({ json: { ...x.json, items: items.length } })) : [{ json: base }];
"""

JS_RENDER = r"""
const P = $('SN2: plan').all().map(i => i.json)[0];
const S = P.S; const R = {};
if (P.need) { $('SN2: plan').all().map(i => i.json).forEach((it, i) => { R[it.k] = $input.all().map(x => x.json)[i] || {}; }); }
const home = [[{ t: '🏠 الرئيسية', c: 'h' }]];
const done = (text, kb) => [{ json: { ctx: P.ctx, chatId: P.chatId, text: String(text).slice(0, 3800), keyboard: (kb || home).slice(0, 8), edit: P.edit, state: JSON.stringify(S) } }];
if (!P.linked) return [{ json: { ctx: P.ctx, chatId: P.chatId, text: '👻 سناب شات صار متوفر بالنظام الإعلاني ✅\n\nحسابك الإعلاني بسناب غير مربوط بعد. لتفعيله نحتاج منك:\n1️⃣ حساب سناب بيه منظمة (Organization) وأنت مديرها.\n2️⃣ تفتح رابط الموافقة الي نرسله لك وتضغط Allow.\n\nتواصل مع الإدارة وننجز ربطه بدقايق.', keyboard: home, edit: P.edit, state: '' } }];
const stepNo = () => (STEPS.indexOf(S.st) + 1) + '/' + STEPS.length;
const head = t => '👻 حملة سناب شات (مسودة استهداف)\n' + LINE + '\n' + t + '  [' + stepNo() + ']\n';
const back = (to) => ({ t: '⬅️ رجوع', c: 'sn:b:' + to });
const chunk = (arr, n) => { const o = []; for (let i = 0; i < arr.length; i += n) o.push(arr.slice(i, i + n)); return o; };
const listOf = (r, key) => (((r || {}).data || {})[key] || []);
const regionList = () => { const r = R.regs || {}; if (!r.ok) return null; return listOf(r, 'targeting_dimensions').map(x => (x || {}).region || {}).filter(x => x.id).map(x => ({ id: String(x.id), name: arGov(x.name), en: String(x.name || '') })); };
const interestList = () => { const r = R.ints || {}; if (!r.ok) return null; return listOf(r, 'targeting_dimensions').map(x => (x || {}).scls || {}).filter(x => x.id).map(x => ({ id: String(x.id), name: String(x.name || x.id), parent: String(x.parentId || '') })); };
const errText = r => '⚠️ ما كدرت أقرأ البيانات من سناب: ' + String(((r || {}).error && (r.error.message || r.error.class)) || 'خطأ').slice(0, 140) + '\nجرّب مرة ثانية بعد شوي.';
if (S.st === 'obj') {
  const ks = Object.keys(OBJ); const kb = chunk(ks.map(k => ({ t: OBJ[k][0] + ' ' + OBJ[k][1], c: 'sn:o:' + k })), 2); kb.push([{ t: '🏠 الرئيسية', c: 'h' }]);
  return done(head('اختر هدف الحملة') + 'هذي مسودة استهداف فقط، ما راح تنشأ حملة بسناب بهالمرحلة.', kb);
}
if (S.st === 'reg') {
  const L = regionList(); if (!L) return done(head('المحافظات') + errText(R.regs), [[back('obj')]]);
  const PER = 15, pages = Math.max(1, Math.ceil(L.length / PER)); S.rp = Math.min(Math.max(0, S.rp), pages - 1);
  const part = L.slice(S.rp * PER, S.rp * PER + PER);
  const kb = [[{ t: (S.regs.length ? '' : '✅ ') + '🇮🇶 كل العراق', c: 'sn:ra' }, { t: '🗑️ مسح الاختيار', c: 'sn:rc' }]];
  chunk(part.map(x => ({ t: (S.regs.indexOf(x.id) >= 0 ? '✅ ' : '') + sh(x.name, 16), c: 'sn:r:' + x.id })), 3).forEach(r => kb.push(r));
  kb.push([{ t: '◀️', c: 'sn:rp:' + Math.max(0, S.rp - 1) }, { t: (S.rp + 1) + '/' + pages, c: 'sn:rp:' + S.rp }, { t: '▶️', c: 'sn:rp:' + Math.min(pages - 1, S.rp + 1) }]);
  kb.push([{ t: '✔️ التالي (' + (S.regs.length ? S.regs.length + ' محافظة' : 'كل العراق') + ')', c: 'sn:rn' }, back('obj')]);
  return done(head('اختر المحافظات') + 'الهدف: ' + OBJ[S.obj][1] + '\nدوس على المحافظة تحدد/تلغي. إذا ما اخترت شي = كل العراق.', kb);
}
if (S.st === 'age') {
  const kb = [Object.keys(AGES).slice(0, 2).map(k => ({ t: (S.ages.indexOf(k) >= 0 ? '✅ ' : '') + AGES[k], c: 'sn:a:' + k })), Object.keys(AGES).slice(2).map(k => ({ t: (S.ages.indexOf(k) >= 0 ? '✅ ' : '') + AGES[k], c: 'sn:a:' + k })),
    [{ t: (S.ages.length ? '' : '✅ ') + 'كل الأعمار (18+)', c: 'sn:aa' }], [{ t: '✔️ التالي', c: 'sn:an' }, back('reg')]];
  return done(head('اختر الفئات العمرية') + 'تقدر تختار أكثر من فئة. حدود الأعمار حسب تعريف سناب (غير مؤكدة من توثيقه).', kb);
}
if (S.st === 'gen') {
  const kb = [Object.keys(GEN).map(k => ({ t: (S.gen === k ? '✅ ' : '') + GEN[k], c: 'sn:g:' + k })), [back('age')]];
  return done(head('اختر الجنس'), kb);
}
if (S.st === 'lng') {
  const ks = Object.keys(LNG); const kb = chunk(ks.map(k => ({ t: (S.lng === k ? '✅ ' : '') + LNG[k], c: 'sn:l:' + k })), 2); kb.push([back('gen')]);
  return done(head('اختر لغة الجمهور') + 'ملاحظة: قائمة اللغات من عندنا (سناب ما سمح بقراءتها من حسابنا)، والرموز غير مؤكدة.', kb);
}
if (S.st === 'int') {
  const L = interestList(); if (!L) return done(head('الاهتمامات') + errText(R.ints), [[back('lng')]]);
  const PER = 12, pages = Math.max(1, Math.ceil(L.length / PER)); S.ip = Math.min(Math.max(0, S.ip), pages - 1);
  const part = L.slice(S.ip * PER, S.ip * PER + PER);
  const kb = []; chunk(part.map(x => ({ t: (S.ints.indexOf(x.id) >= 0 ? '✅ ' : '') + sh(x.name, 18), c: 'sn:i:' + x.id.toLowerCase() })), 3).forEach(r => kb.push(r));
  kb.push([{ t: '◀️', c: 'sn:ip:' + Math.max(0, S.ip - 1) }, { t: (S.ip + 1) + '/' + pages, c: 'sn:ip:' + S.ip }, { t: '▶️', c: 'sn:ip:' + Math.min(pages - 1, S.ip + 1) }]);
  kb.push([{ t: '🗑️ مسح', c: 'sn:ic' }, { t: '✔️ التالي (' + S.ints.length + ')', c: 'sn:in' }, back('lng')]);
  return done(head('اختر الاهتمامات (حتى 10)') + 'الاهتمامات من قائمة سناب للعراق (' + L.length + ' اهتمام). بدون اختيار = كل الاهتمامات.', kb);
}
// summary
const RL = regionList() || [], IL = interestList() || [];
const rn = S.regs.length ? S.regs.map(id => { const x = RL.find(r => r.id === id); return x ? x.name : id; }).join('، ') : 'كل العراق';
const inn = S.ints.length ? S.ints.map(id => { const x = IL.find(r => r.id === id); return x ? x.name : id; }).join('، ') : 'كل الاهتمامات';
const L = [head('ملخص الاستهداف').trimEnd(), '',
  '🎯 الهدف: ' + OBJ[S.obj][1], '📍 المحافظات: ' + rn, '🎂 العمر: ' + (S.ages.length ? S.ages.map(k => AGES[k]).join('، ') : 'كل الأعمار (18+)'), '🚻 الجنس: ' + GEN[S.gen], '🗣️ اللغة: ' + (LNG[S.lng] || S.lng), '❤️ الاهتمامات: ' + inn, '',
  '⏳ هذي مسودة استهداف فقط. إنشاء الحملة بسناب نضيفه بالمرحلة الجاية.'];
return done(L.join('\n'), [[{ t: '🔁 من جديد', c: 'sn:s' }, { t: '✏️ تعديل الاهتمامات', c: 'sn:b:int' }], [{ t: '🏠 الرئيسية', c: 'h' }]]);
"""

JS_REPLY = r"""
const r = $('SN2: render').first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, keyboard: r.keyboard, edit: r.edit } }];
"""


def build(b, w, sw, idx, reply, CRT):
    code, pg, call_broker = b.code, b.pg, b.call_broker
    data = pg(w, "SN2: data", SQL_DATA, "={{ [$('Route').first().json.ctx, String($('Route').first().json.chatId)] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    plan = code(w, "SN2: plan", LIB + JS_PLAN)
    need = w.add("SN2: need broker?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.need ? 1 : 0 }}"})
    call = call_broker(w, "SN2: read targeting", mode="each")
    render = code(w, "SN2: render", LIB + JS_RENDER)
    save = pg(w, "SN2: save state",
              "SELECT CASE WHEN $3::text <> '' THEN api.ui_set($1, 'sn:' || $2, 'v', $3::jsonb, 3600)::text END AS saved",
              "={{ [$json.ctx, String($json.chatId), $json.state || ''] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    out = reply("SN2: reply", JS_REPLY)
    w.link(sw, data, idx)
    w.chain(data, plan, need)
    w.link(need, render, 0)
    w.link(need, call, 1)
    w.chain(call, render)
    w.chain(render, save, out)
