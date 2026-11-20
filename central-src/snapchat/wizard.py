# -*- coding: utf-8 -*-
"""سناب شات — معالج الحملة v3 (p197c): أهداف (مبيعات/عملاء محتملين/زيارات/مشاهدات)، كل اختيار يفتح الخطوة التالية، عمر من → إلى، فيديو إلزامي من تلغرام، ثم رفع **مسودة متوقفة كاملة** (حملة + مجموعة + تصميم + إعلان) عبر `snapchat.launch_draft`.
callbacks بادئة `sn:` (wf_ingress يوجّهها إلى cmd = snapwiz): sn:s · o:<هدف> · ac:<id> · px:<id> · r:<id>/ra/rc/rp:<n>/rn · af:<n>/af0/at:<n>/aa · g:<a|m|f> · l:<لغة> · i:<id>/ic/ip:<n>/in · bu:<n> · du:<n> · vn · ct:<زر> · tn · go · b:<شاشة>.
إدخال نص/ملف (cmd = snapin من wf_ingress عندما تكون الخطوة url/vid/txt): النص بـd.args والملف بـd.fileId. `/snaplink <رابط>` ما زال يشتغل.
الحالة بـapi.ui_set بمفتاح sn:<chat> لمدة ساعة (اختيارات فقط). مقيّدات تلغرام: ≤8 صفوف، ≤3 أزرار بالصف، t ≤ 40."""

SQL_DATA = ("SELECT 'state'::text AS kind, data::text AS a, age_s::text AS b, NULL::text AS c FROM api.ui_get($1, 'sn:' || $2) "
            "UNION ALL SELECT 'acct', external_id::text, name::text, currency::text FROM api.list_ad_accounts($1) WHERE platform::text = 'snapchat' AND enabled")

LIB = r"""
const OBJ = { sal: ['🛒', 'مبيعات'], led: ['🎯', 'عملاء محتملين'], trf: ['🔗', 'زيارات'], vid: ['👁️', 'مشاهدات'] };
const OBJ_OK = { sal: true, trf: true, vid: true };
const LNG = { '': 'كل اللغات', ar: 'العربية', en: 'English', ku: 'کوردی' };
const GEN = { a: 'الكل', m: 'رجال', f: 'نساء' };
const GOV = [['baghdad', 'بغداد'], ['basra', 'البصرة'], ['basrah', 'البصرة'], ['ninev', 'نينوى'], ['ninaw', 'نينوى'], ['nainaw', 'نينوى'], ['mosul', 'نينوى'], ['erbil', 'أربيل'], ['arbil', 'أربيل'], ['irbil', 'أربيل'], ['sulaym', 'السليمانية'], ['sulaim', 'السليمانية'], ['dohuk', 'دهوك'], ['duhok', 'دهوك'], ['dahuk', 'دهوك'], ['kirkuk', 'كركوك'], ['tamim', 'كركوك'], ['anbar', 'الأنبار'], ['babil', 'بابل'], ['babylon', 'بابل'], ['karbala', 'كربلاء'], ['najaf', 'النجف'], ['diyala', 'ديالى'], ['wasit', 'واسط'], ['maysan', 'ميسان'], ['misan', 'ميسان'], ['dhiqar', 'ذي قار'], ['thiqar', 'ذي قار'], ['muthanna', 'المثنى'], ['qadis', 'القادسية'], ['diwaniy', 'القادسية'], ['salah', 'صلاح الدين'], ['saladin', 'صلاح الدين'], ['halabja', 'حلبجة']];
const arGov = n => { const k = String(n || '').toLowerCase().replace(/[^a-z]/g, ''); const h = GOV.find(g => k.indexOf(g[0]) >= 0); return h ? h[1] : String(n || ''); };
const LINE = '━━━━━━━━━━━━━━';
const sh = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const SEQ = o => ['obj', 'acct'].concat(o === 'sal' ? ['pix'] : []).concat((o === 'sal' || o === 'trf') ? ['url'] : []).concat(['reg', 'age', 'gen', 'lng', 'int', 'bud', 'dur', 'vid', 'txt', 'sum']);
const BUDS = { IQD: [10000, 25000, 50000, 100000] }; const BUD_DEF = [5, 10, 20, 50, 100];
const DURS = [1, 3, 7, 14, 30];
const AGE_FROM = [18, 21, 25, 30, 35, 40, 45]; const AGE_TO = [24, 29, 34, 39, 44, 49];
const CTAS = { MORE: 'المزيد', LEARN_MORE: 'اعرف أكثر', SHOP_NOW: 'تسوق الآن', ORDER_NOW: 'اطلب الآن', SIGN_UP: 'سجّل', BOOK_NOW: 'احجز الآن' };
const fnum = n => Number(n || 0).toLocaleString('en-US');
const hash36 = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(36); };
const ageTxt = S => S.amin ? ('من ' + S.amin + ' إلى ' + (S.amax ? S.amax : 'فما فوق')) : 'كل الأعمار (18+)';
"""

JS_PLAN = r"""
const d = $('Route').first().json;
const rows = $input.all().map(i => i.json).filter(r => r && r.kind);
const accts = rows.filter(r => r.kind === 'acct');
const ACCS = accts.map(r => ({ id: String(r.a), name: String(r.b || ''), cur: String(r.c || '').toUpperCase() }));
let S0 = null; const sr = rows.find(r => r.kind === 'state'); if (sr) { try { S0 = JSON.parse(sr.a); } catch (e) {} }
const isCb = !!d.cb;
const base = { ctx: d.ctx, chatId: d.chatId, edit: isCb, linked: accts.length > 0, items: 0, accts: ACCS };
const cmd = String(d.cmd || '');
const isLink = !isCb && cmd === 'snaplink', isIn = !isCb && cmd === 'snapin', isTx = !isCb && cmd === 'snaptext';
const p = isCb ? String(d.cb).split(':') : (isLink ? ['sn', 'lk'] : (isIn ? ['sn', 'ti'] : (isTx ? ['sn', 'tx'] : ['sn', 's']))); const op = p[1] || 's', arg = p.slice(2).join(':');
const fresh = { st: 'obj', obj: '', regs: [], amin: 0, amax: 0, aset: false, gen: 'a', lng: 'ar', ints: [], rp: 0, ip: 0, acct: '', pix: '', bud: 0, days: 0, url: '', vid: '', vnm: '', hdl: '', cta: 'MORE', nm: '' };
let S = (S0 && typeof S0 === 'object' && !Array.isArray(S0)) ? { ...fresh, ...S0 } : { ...fresh };
if (!Array.isArray(S.regs)) S.regs = []; if (!Array.isArray(S.ints)) S.ints = [];
const tog = (arr, v, max) => { const i = arr.indexOf(v); if (i >= 0) { arr.splice(i, 1); return arr; } if (arr.length < max) arr.push(v); return arr; };
const num = s => /^\d{1,6}$/.test(String(s)) ? parseInt(s, 10) : 0;
const adv = () => {
  const q = SEQ(S.obj); const i = q.indexOf(S.st); S.st = q[Math.min(i < 0 ? 0 : i + 1, q.length - 1)];
  if (S.st === 'acct' && ACCS.length === 1) { S.acct = ACCS[0].id; S.st = q[q.indexOf('acct') + 1]; }
};
if (op === 's') S = { ...fresh };
else if (op === 'o') { if (OBJ[arg]) { if (arg === 'led') { S.obj = ''; S.st = 'obj'; base.ledNote = true; } else { S.obj = arg; S.st = 'obj'; adv(); } } }
else if (op === 'ac') { if (ACCS.some(x => x.id === arg)) { S.acct = arg; S.st = 'acct'; adv(); } }
else if (op === 'px') { if (/^[0-9a-f\-]{8,64}$/.test(arg)) { S.pix = arg; S.st = 'pix'; adv(); } }
else if (op === 'r') { if (/^\d{1,12}$/.test(arg)) S.regs = tog(S.regs, arg, 19); S.st = 'reg'; }
else if (op === 'ra' || op === 'rc') { S.regs = []; S.st = 'reg'; }
else if (op === 'rp') { S.rp = num(arg); S.st = 'reg'; }
else if (op === 'rn') { S.st = 'reg'; adv(); }
else if (op === 'af') { if (AGE_FROM.indexOf(num(arg)) >= 0) { S.amin = num(arg); S.amax = 0; S.aset = false; S.st = 'age'; } }
else if (op === 'af0') { S.amin = 0; S.amax = 0; S.aset = false; S.st = 'age'; }
else if (op === 'at') { if (arg === '0' || (AGE_TO.indexOf(num(arg)) >= 0 && num(arg) > S.amin)) { S.amax = num(arg); S.aset = true; S.st = 'age'; adv(); } }
else if (op === 'aa') { S.amin = 0; S.amax = 0; S.aset = true; S.st = 'age'; adv(); }
else if (op === 'g') { if (GEN[arg]) { S.gen = arg; S.st = 'gen'; adv(); } }
else if (op === 'l') { if (arg in LNG) { S.lng = arg; S.st = 'lng'; adv(); S.ip = 0; } }
else if (op === 'i') { if (/^slc_\d{1,6}$/i.test(arg)) S.ints = tog(S.ints, arg.toUpperCase(), 10); S.st = 'int'; }
else if (op === 'ic') { S.ints = []; S.st = 'int'; }
else if (op === 'ip') { S.ip = num(arg); S.st = 'int'; }
else if (op === 'in') { S.st = 'int'; adv(); }
else if (op === 'bu') { const a = ACCS.find(x => x.id === S.acct); const L = (a && BUDS[a.cur]) || BUD_DEF; if (L.indexOf(num(arg)) >= 0) { S.bud = num(arg); S.st = 'bud'; adv(); } }
else if (op === 'du') { if (DURS.indexOf(num(arg)) >= 0) { S.days = num(arg); S.st = 'dur'; adv(); } }
else if (op === 'lk') { const m = /https:\/\/[^\s\x00-\x1f<>"']{4,500}/.exec(String(d.args || '')); if (m) { S.url = m[0]; if (S.st === 'url') adv(); base.linkOk = true; } else base.linkBad = true; }
else if (op === 'tx') {
  // p221: رفع من رسالة واحدة (نص + فيديو): يملأ الحالة مما فهمه بالقواعد، وكل شي ناقص أو غير مفهوم يسأل عنه المعالج بأزراره. لا يرفع شي لحاله؛ يوصل لشاشة الملخص وانت تضغط 🚀.
  S = { ...fresh }; const got = [], miss = [];
  const raw = String(d.args || '').replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632));
  const nzt = s => String(s || '').replace(/[ً-ْـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').toLowerCase().replace(/[،,؟?!:："'«»()]/g, ' ').replace(/\s+/g, ' ').trim();
  const TB = nzt(raw.replace(/https?:\/\/\S+/g, ' '));
  const mu = /https:\/\/[^\s\x00-\x1f<>"']{4,500}/.exec(raw); if (mu) { S.url = mu[0]; got.push('🔗 الرابط: ' + sh(S.url, 60)); }
  if (/مبيعات|مبيع|بيع/.test(TB)) S.obj = 'sal'; else if (/زيارات|زياره|ترافيك|traffic/.test(TB)) S.obj = 'trf'; else if (/مشاهدات|مشاهده/.test(TB)) S.obj = 'vid'; else if (/عملاء محتملين|ليدز|leads/.test(TB)) { base.ledNote = true; miss.push('«عملاء محتملين» يحتاج نموذج عملاء بسناب (مو متاح)'); }
  if (S.obj) got.push('🎯 الهدف: ' + OBJ[S.obj][1]);
  if (S.obj === 'sal') miss.push('مبيعات: سناب يرفضها لأن البكسل بدون أحداث شراء (E3017)، ولرابط واتساب اكتب «زيارات» بدلها.');   // p222
  const sm = /(?:بحساب|حساب) ([^\n]{1,40})/.exec(TB);
  if (sm && ACCS.length) { const ws = sm[1].split(' ').filter(w => w.length >= 3).slice(0, 3); const hit = ACCS.filter(a => { const an = nzt(a.name).split(' '); return ws.some(w => an.some(x => x.length >= 3 && (x.indexOf(w) === 0 || w.indexOf(x) === 0))); }); if (hit.length === 1) { S.acct = hit[0].id; got.push('🏷️ الحساب: ' + sh(hit[0].name, 30)); } else miss.push(hit.length ? 'اسم الحساب يطابق أكثر من حساب' : 'ما لقيت حساب سناب بهذا الاسم'); }
  if (!S.acct && ACCS.length === 1) { S.acct = ACCS[0].id; got.push('🏷️ الحساب: ' + sh(ACCS[0].name, 30)); }
  let dy = 0; if (/يوم واحد|يوم وحد/.test(TB) || /(^| )1 يوم/.test(TB)) dy = 1; else if (/يومين/.test(TB)) dy = 2; else if (/اسبوعين/.test(TB)) dy = 14; else if (/اسبوع/.test(TB)) dy = 7; else if (/(^| )شهر/.test(TB)) dy = 30; else { const m = /(\d{1,3}) (?:يوم|ايام)/.exec(TB); if (m) dy = parseInt(m[1], 10); }
  if (dy) { if (DURS.indexOf(dy) >= 0) { S.days = dy; got.push('📅 المدة: ' + dy + ' يوم'); } else miss.push('المدة ' + dy + ' يوم مو من الخيارات (' + DURS.join('/') + ')'); }
  { const m1 = /(\d+(?:\.\d+)?) ?(?:دولار|\$|usd)/.exec(TB) || /\$ ?(\d+(?:\.\d+)?)/.exec(TB), m2 = /(\d+(?:\.\d+)?) ?(?:الف|الاف)/.exec(TB), m3 = /(\d{4,}) ?(?:دينار|iqd)?/.exec(TB), m4 = /ميزانيه ?(\d+(?:\.\d+)?)/.exec(TB);
    let usd = 0, iqd = 0; if (m1) usd = parseFloat(m1[1]); else if (m2) iqd = Math.round(parseFloat(m2[1]) * 1000); else if (m3) iqd = parseInt(m3[1], 10); else if (m4) { const v = parseFloat(m4[1]); if (v >= 1000) iqd = Math.round(v); else usd = v; }
    if (usd || iqd) { const a = ACCS.find(x => x.id === S.acct); if (a) { const L = BUDS[a.cur] || BUD_DEF; const v = a.cur === 'IQD' ? iqd : usd; if (v && L.indexOf(v) >= 0) { S.bud = v; got.push('💰 الميزانية: ' + fnum(v) + ' ' + a.cur); } else miss.push('الميزانية ' + (usd ? usd + '$' : fnum(iqd) + ' د.ع') + ' مو من خيارات حساب ' + a.cur + ' (' + L.map(fnum).join('/') + ')'); } else miss.push('الميزانية تتحدد بعد اختيار الحساب'); } }
  const nmm = /سمي(?:ها|ه)\s+([^\n]{1,40})/.exec(raw); if (nmm) { const v = nmm[1].replace(/[\x00-\x1f<>]/g, ' ').replace(/\s+/g, ' ').trim(); if (v) { S.nm = v.slice(0, 40); got.push('🏷️ الاسم: ' + S.nm); } }
  const fid = String(d.fileId || '').trim();
  if (fid) { if (/^[A-Za-z0-9_\-]{10,200}$/.test(fid) && Number(d.fileSize || 0) <= 20000000) { S.vid = fid; S.vnm = String(d.fileName || '').slice(0, 40); got.push('🎬 الفيديو: وصل'); } else miss.push('الفيديو (أكبر من 20MB أو غير صالح)'); }
  if (/عراق/.test(TB)) got.push('📍 الموقع: العراق (كل المحافظات)');
  const SQx = SEQ(S.obj || 'trf'); const must = { obj: () => !!S.obj, acct: () => !!S.acct, pix: () => !!S.pix, url: () => /^https:\/\//.test(S.url || ''), bud: () => !!S.bud, dur: () => !!S.days, vid: () => !!S.vid };
  S.st = 'sum'; for (const k of SQx) { if (must[k] && !must[k]()) { S.st = k; break; } }
  base.tx = { got, miss };
}
else if (op === 'ti') {
  const txt = String(d.args || '').trim(), fid = String(d.fileId || '').trim();
  if (S.st === 'url') { const m = /^(https:\/\/[^\s\x00-\x1f<>"']{4,500})$/.exec(txt); if (m) { S.url = m[1]; adv(); } else base.linkBad = true; }
  else if (S.st === 'vid') {
    if (fid && /^[A-Za-z0-9_\-]{10,200}$/.test(fid)) { if (Number(d.fileSize || 0) > 20000000) base.vidBig = true; else { S.vid = fid; S.vnm = String(d.fileName || '').slice(0, 40); base.vidOk = true; } } else base.vidBad = true;
  }
  else if (S.st === 'txt') { if (txt && txt.length <= 34 && !/[\x00-\x1f<>]/.test(txt)) { S.hdl = txt; base.hdlOk = true; } else base.hdlBad = true; }
}
else if (op === 'vn') { if (S.vid) { S.st = 'vid'; adv(); } }
else if (op === 'ct') { if (CTAS[arg.toUpperCase()]) { S.cta = arg.toUpperCase(); S.st = 'txt'; } }
else if (op === 'tn') { S.st = 'txt'; adv(); }
else if (op === 'go') { S.st = 'sum'; base.go = true; }
else if (op === 'b') { if (SEQ(S.obj).indexOf(arg) >= 0) { S.st = arg; if (arg === 'age') { S.amin = 0; S.amax = 0; S.aset = false; } } }
if (S.st !== 'obj' && !OBJ[S.obj]) S.st = 'obj';
if (SEQ(S.obj).indexOf(S.st) < 0) S.st = 'obj';
base.S = S;
const items = [];
const need = (k, o, params) => items.push({ json: { ...base, need: true, k, platform: 'snapchat', ad_account: '', op: o, params } });
if (base.linked && !base.go) {
  if (S.st === 'reg' || (S.st === 'sum' && S.regs.length)) need('regs', 'snapchat.t_regions', { oid: 'iq' });
  if (S.st === 'int' || (S.st === 'sum' && S.ints.length)) need('ints', 'snapchat.t_interests', { oid: 'scls', country_code: 'iq' });
  if (S.st === 'pix' && S.acct) need('pix', 'snapchat.pixels', { oid: S.acct });
}
if (base.go) {
  const a = ACCS.find(x => x.id === S.acct); const needUrl = S.obj === 'sal' || S.obj === 'trf';
  if (!OBJ_OK[S.obj]) base.goErr = 'هذا الهدف غير متاح للرفع حالياً. اختر هدف ثاني.';
  else if (!a || !S.bud || !S.days || !S.vid || (needUrl && !/^https:\/\//.test(S.url || '')) || (S.obj === 'sal' && !S.pix)) base.goErr = 'ناقصة معلومات: تأكد من الحساب والميزانية والمدة والفيديو' + (needUrl ? ' والرابط' : '') + (S.obj === 'sal' ? ' والبكسل' : '') + '.';
  else {
    const nm = S.nm ? String(S.nm).slice(0, 120) : ('Snap · ' + OBJ[S.obj][1] + ' · ' + new Date().toISOString().slice(5, 10)).slice(0, 120);
    const prm = { account_id: a.id, name: nm, objective: S.obj, budget: S.bud, days: S.days, regions: S.regs, gender: S.gen, lang: S.lng, interests: S.ints, file_id: S.vid, cta: needUrl ? S.cta : 'MORE', brand_name: String(a.name || nm).slice(0, 25), headline: String(S.hdl || nm).slice(0, 34) };
    if (S.amin) { prm.min_age = S.amin; if (S.amax) prm.max_age = S.amax; }
    if (needUrl) prm.landing_url = S.url;
    if (S.obj === 'sal') prm.pixel_id = S.pix;
    const idem = ('snw-' + String(d.chatId).replace(/[^0-9]/g, '') + '-' + hash36(JSON.stringify(prm)) + '-' + Math.floor(Date.now() / 120000)).slice(0, 90);
    items.push({ json: { ...base, need: true, k: 'go', platform: 'snapchat', ad_account: '', op: 'snapchat.launch_draft', params: prm, idem, goName: nm } });
  }
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
const ACCS_N = () => (P.accts || []).length;
const SQ = SEQ(S.obj || 'trf');
const stepNo = () => (Math.max(0, SQ.indexOf(S.st)) + 1) + '/' + SQ.length;
const TXN = P.tx ? ('📝 فهمت من رسالتك:\n' + (P.tx.got.length ? P.tx.got.join('\n') : 'ما فهمت تفاصيل') + (P.tx.miss.length ? '\n⚠️ ' + P.tx.miss.join('\n⚠️ ') : '') + '\n' + LINE + '\n') : '';
const head = t => '👻 حملة سناب شات\n' + LINE + '\n' + TXN + t + '  [' + stepNo() + ']\n';
const prevOf = () => { const q = SQ; let i = q.indexOf(S.st) - 1; if (q[i] === 'acct' && ACCS_N() === 1) i--; return q[Math.max(0, i)]; };
const back = () => ({ t: '⬅️ رجوع', c: 'sn:b:' + prevOf() });
const chunk = (arr, n) => { const o = []; for (let i = 0; i < arr.length; i += n) o.push(arr.slice(i, i + n)); return o; };
const listOf = (r, key) => (((r || {}).data || {})[key] || []);
const regionList = () => { const r = R.regs || {}; if (!r.ok) return null; return listOf(r, 'targeting_dimensions').map(x => (x || {}).region || {}).filter(x => x.id).map(x => ({ id: String(x.id), name: arGov(x.name), en: String(x.name || '') })); };
const interestList = () => { const r = R.ints || {}; if (!r.ok) return null; return listOf(r, 'targeting_dimensions').map(x => (x || {}).scls || {}).filter(x => x.id).map(x => ({ id: String(x.id), name: String(x.name || x.id), parent: String(x.parentId || '') })); };
const pixelList = () => { const r = R.pix || {}; if (!r.ok) return null; return listOf(r, 'pixels').map(x => ((x || {}).pixel || x || {})).filter(x => x.id).map(x => ({ id: String(x.id), name: String(x.name || 'Pixel') })); };
const errText = r => '⚠️ ما كدرت أقرأ البيانات من سناب: ' + String(((r || {}).error && (r.error.message || r.error.class)) || 'خطأ').slice(0, 140) + '\nجرّب مرة ثانية بعد شوي.';
const accOf = () => (P.accts || []).find(x => x.id === S.acct) || null;
const FR = { st: 'obj', obj: '', regs: [], amin: 0, amax: 0, aset: false, gen: 'a', lng: 'ar', ints: [], rp: 0, ip: 0, acct: '', pix: '', bud: 0, days: 0, url: '', vid: '', vnm: '', hdl: '', cta: 'MORE', nm: '' };
const STG = { account: 'قراءة الحساب', campaign: 'إنشاء الحملة', adsquad: 'إنشاء المجموعة الإعلانية', media: 'إنشاء ملف الفيديو بسناب', upload: 'رفع الفيديو', profile: 'البروفايل العام', creative: 'إنشاء التصميم', ad: 'إنشاء الإعلان' };
if (P.go) {
  if (P.goErr) return done('⚠️ ' + P.goErr, [[{ t: '⬅️ رجوع للملخص', c: 'sn:b:sum' }]]);
  const r = R.go || {}, dd = r.data || {}, a = accOf();
  if (r.ok) {
    const L = ['✅ انرفعت حملة سناب شات كاملة (متوقفة)', LINE, '📣 الحملة: ' + (P.goName || ''), '🆔 رقم الحملة: ' + dd.campaign_id, '🆔 رقم المجموعة: ' + dd.adsquad_id, '🎬 الإعلان: ' + (dd.ad_id ? 'انبنى (رقمه ' + dd.ad_id + ')' : 'ما انبنى'),
      '💰 الميزانية: ' + fnum(S.bud) + ' ' + (dd.currency || (a && a.cur) || '') + ' (إجمالية)', '📅 من ' + String(dd.start_time || '').slice(0, 16).replace('T', ' ') + ' إلى ' + String(dd.end_time || '').slice(0, 16).replace('T', ' '),
      '⏸️ الحالة: متوقفة، ما فيه صرف لين تفعّلها من Snap Ads Manager.', '', 'راجع الإعلان بـAds Manager (تبويب الإعلانات) قبل التفعيل.'];
    Object.keys(FR).forEach(k => { S[k] = FR[k]; });
    return done(L.join('\n'), [[{ t: '🔁 حملة جديدة', c: 'sn:s' }, { t: '🏠 الرئيسية', c: 'h' }]]);
  }
  const L = ['❌ ما اكتملت الحملة (المرحلة: ' + (STG[dd.stage] || dd.stage || '؟') + ')', LINE, String((r.error && (r.error.message || r.error.class)) || 'خطأ غير معروف من سناب').slice(0, 600)];
  if (/E3017|ineligible for PIXEL/i.test(String((r.error && r.error.message) || ''))) L.push('', 'ℹ️ سناب رفض هدف «مبيعات»: البكسل غير مؤهل لتحسين الشراء (يحتاج أحداث Purchase كافية خلال نافذة التحويل، غالباً آخر 28 يوم). تأكد من Snap Events Manager إن البكسل سجّل شراء، أو اختر هدف زيارات/عملاء محتملين. ما غيّرت الهدف بدون ما تدري.');   // p197f
  if (dd.campaign_id) L.push('', '⚠️ الحملة (متوقفة) انعملت برقم ' + dd.campaign_id + (dd.adsquad_id ? ' والمجموعة ' + dd.adsquad_id : '') + (dd.ad_id ? '' : ' بدون إعلان') + '. إعادة المحاولة تنشئ حملة جديدة، فاحذف هذي من Snap Ads Manager إذا ما تريدها.');
  return done(L.join('\n'), [[{ t: '⬅️ رجوع للملخص', c: 'sn:b:sum' }, { t: '🏠 الرئيسية', c: 'h' }]]);
}
if (S.st === 'obj') {
  const ks = Object.keys(OBJ); const kb = chunk(ks.map(k => ({ t: OBJ[k][0] + ' ' + OBJ[k][1], c: 'sn:o:' + k })), 2); kb.push([{ t: '🏠 الرئيسية', c: 'h' }]);
  return done(head('اختر هدف الحملة') + (P.ledNote ? '\n🎯 «عملاء محتملين» يحتاج نموذج عملاء (Lead Form) وإعداد خاص، وما انبنى بعد. اختر هدف ثاني.\n' : '') + '\nالرفع يكون مسودة متوقفة (حملة + مجموعة + إعلان بالفيديو) وما يصرف لين تفعّلها.', kb);
}
if (S.st === 'acct') {
  const A = P.accts || []; const kb = A.slice(0, 6).map(x => [{ t: sh(x.name || x.id.slice(0, 8), 26) + (x.cur ? ' (' + x.cur + ')' : ''), c: 'sn:ac:' + x.id }]); kb.push([back()]);
  return done(head('اختر الحساب الإعلاني') + 'الحسابات المربوطة بسناب:', kb);
}
if (S.st === 'pix') {
  const L = pixelList(); if (!L) return done(head('البكسل') + errText(R.pix), [[back()]]);
  if (!L.length) return done(head('البكسل') + '⚠️ ما لقيت بكسل (Snap Pixel) بالحساب. هدف المبيعات يحتاج بكسل. أنشئه من Snap Ads Manager (Events Manager) أو اختر هدف ثاني.', [[back()]]);
  const kb = L.slice(0, 6).map(x => [{ t: (S.pix === x.id ? '✅ ' : '') + sh(x.name, 30), c: 'sn:px:' + x.id.toLowerCase() }]); kb.push([back()]);
  return done(head('اختر البكسل') + 'الحملة تُحسَّن على عمليات الشراء من هذا البكسل. تأكد أنه يسجّل أحداث شراء.', kb);
}
if (S.st === 'url') {
  const kb = [[back()]]; if (S.url) kb.unshift([{ t: '✔️ استخدم الرابط الحالي', c: 'sn:b:reg' }]);
  return done(head('رابط الوجهة') + (P.linkBad ? '⚠️ الرابط غير صالح، لازم يبدأ بـ https://\n\n' : '') + 'أرسل رابط الوجهة كرسالة عادية (https). يصير وجهة الإعلان: واتساب، تلغرام، موقعك…' + (S.url ? '\n\nالرابط الحالي: ' + sh(S.url, 80) : ''), kb);
}
if (S.st === 'reg') {
  const L = regionList(); if (!L) return done(head('المحافظات') + errText(R.regs), [[back()]]);
  const PER = 15, pages = Math.max(1, Math.ceil(L.length / PER)); S.rp = Math.min(Math.max(0, S.rp), pages - 1);
  const part = L.slice(S.rp * PER, S.rp * PER + PER);
  const kb = [[{ t: (S.regs.length ? '' : '✅ ') + '🇮🇶 كل العراق', c: 'sn:ra' }, { t: '🗑️ مسح الاختيار', c: 'sn:rc' }]];
  chunk(part.map(x => ({ t: (S.regs.indexOf(x.id) >= 0 ? '✅ ' : '') + sh(x.name, 16), c: 'sn:r:' + x.id })), 3).forEach(r => kb.push(r));
  kb.push([{ t: '◀️', c: 'sn:rp:' + Math.max(0, S.rp - 1) }, { t: (S.rp + 1) + '/' + pages, c: 'sn:rp:' + S.rp }, { t: '▶️', c: 'sn:rp:' + Math.min(pages - 1, S.rp + 1) }]);
  kb.push([{ t: '✔️ التالي (' + (S.regs.length ? S.regs.length + ' محافظة' : 'كل العراق') + ')', c: 'sn:rn' }, back()]);
  return done(head('اختر المحافظات') + 'الهدف: ' + OBJ[S.obj][1] + '\nدوس على المحافظة تحدد/تلغي. إذا ما اخترت شي = كل العراق.', kb);
}
if (S.st === 'age') {
  if (!S.amin) {
    const kb = chunk(AGE_FROM.map(n => ({ t: n + '', c: 'sn:af:' + n })), 3); kb.push([{ t: 'كل الأعمار (18+)', c: 'sn:aa' }]); kb.push([back()]);
    return done(head('العمر: من أي عمر؟') + 'اختر الحد الأدنى للعمر. بعدها تختار الحد الأعلى.', kb);
  }
  const kb = chunk(AGE_TO.filter(n => n > S.amin).map(n => ({ t: 'إلى ' + n, c: 'sn:at:' + n })), 3); kb.push([{ t: 'فما فوق (بدون حد أعلى)', c: 'sn:at:0' }]); kb.push([{ t: '⬅️ غيّر الحد الأدنى', c: 'sn:af0' }]);
  return done(head('العمر: من ' + S.amin + ' إلى؟') + 'اختر الحد الأعلى للعمر.', kb);
}
if (S.st === 'gen') {
  const kb = [Object.keys(GEN).map(k => ({ t: (S.gen === k ? '✅ ' : '') + GEN[k], c: 'sn:g:' + k })), [back()]];
  return done(head('اختر الجنس'), kb);
}
if (S.st === 'lng') {
  const ks = Object.keys(LNG); const kb = chunk(ks.map(k => ({ t: (S.lng === k ? '✅ ' : '') + LNG[k], c: 'sn:l:' + k })), 2); kb.push([back()]);
  return done(head('اختر لغة الجمهور') + 'ملاحظة: قائمة اللغات من عندنا (سناب ما سمح بقراءتها من حسابنا)، والرموز غير مؤكدة.', kb);
}
if (S.st === 'int') {
  const L = interestList(); if (!L) return done(head('الاهتمامات') + errText(R.ints), [[back()]]);
  const PER = 12, pages = Math.max(1, Math.ceil(L.length / PER)); S.ip = Math.min(Math.max(0, S.ip), pages - 1);
  const part = L.slice(S.ip * PER, S.ip * PER + PER);
  const kb = []; chunk(part.map(x => ({ t: (S.ints.indexOf(x.id) >= 0 ? '✅ ' : '') + sh(x.name, 18), c: 'sn:i:' + x.id.toLowerCase() })), 3).forEach(r => kb.push(r));
  kb.push([{ t: '◀️', c: 'sn:ip:' + Math.max(0, S.ip - 1) }, { t: (S.ip + 1) + '/' + pages, c: 'sn:ip:' + S.ip }, { t: '▶️', c: 'sn:ip:' + Math.min(pages - 1, S.ip + 1) }]);
  kb.push([{ t: '🗑️ مسح', c: 'sn:ic' }, { t: '✔️ التالي (' + S.ints.length + ')', c: 'sn:in' }, back()]);
  return done(head('اختر الاهتمامات (حتى 10)') + 'الاهتمامات من قائمة سناب للعراق (' + L.length + ' اهتمام). بدون اختيار = كل الاهتمامات.', kb);
}
if (S.st === 'bud') {
  const a = accOf(); const cur = a ? a.cur : ''; const L = BUDS[cur] || BUD_DEF;
  const kb = chunk(L.map(v => ({ t: (S.bud === v ? '✅ ' : '') + fnum(v) + ' ' + cur, c: 'sn:bu:' + v })), 3); kb.push([back()]);
  return done(head('اختر الميزانية') + 'الحساب: ' + (a ? a.name : '') + '\nالميزانية إجمالية للحملة كلها (مو يومية)، بعملة الحساب: ' + cur + '.', kb);
}
if (S.st === 'dur') {
  const kb = chunk(DURS.map(v => ({ t: (S.days === v ? '✅ ' : '') + v + (v === 1 ? ' يوم' : ' أيام'), c: 'sn:du:' + v })), 3); kb.push([back()]);
  return done(head('اختر مدة الحملة') + 'تبدأ بعد 15 دقيقة تقريباً من الرفع (بتوقيت الحساب)، لكن تبقى متوقفة لين تفعّلها.', kb);
}
if (S.st === 'vid') {
  const kb = []; if (S.vid) kb.push([{ t: '✔️ التالي', c: 'sn:vn' }]); kb.push([back()]);
  const msg = P.vidBig ? '⚠️ الملف أكبر من 20MB (حد تلغرام للبوتات). صغّره أو اقصّ الفيديو وارسله من جديد.\n\n' : (P.vidBad ? '⚠️ ما استلمت فيديو. أرسل الفيديو كملف (📎 ← فيديو) مو كنص.\n\n' : '');
  return done(head('أرسل الفيديو') + msg + '🎬 أرسل فيديو الإعلان هنا كملف (فيديو mp4، حد 20MB، الأفضل عمودي 9:16).\n' + (S.vid ? '\n✅ استلمت الفيديو' + (S.vnm ? ' (' + S.vnm + ')' : '') + '. دوس «التالي» أو أرسل فيديو ثاني يستبدله.' : '\nالفيديو إلزامي قبل الرفع.'), kb);
}
if (S.st === 'txt') {
  const needUrl = S.obj === 'sal' || S.obj === 'trf';
  const kb = []; if (needUrl) chunk(Object.keys(CTAS).map(k => ({ t: (S.cta === k ? '✅ ' : '') + CTAS[k], c: 'sn:ct:' + k.toLowerCase() })), 3).forEach(r => kb.push(r));
  kb.push([{ t: '✔️ التالي', c: 'sn:tn' }, back()]);
  const note = P.hdlOk ? '✅ انحفظ العنوان.\n\n' : (P.hdlBad ? '⚠️ العنوان لازم يكون حتى 34 حرف وبدون رموز غريبة.\n\n' : '');
  return done(head('عنوان الإعلان' + (needUrl ? ' وزر الإجراء' : '')) + note + 'أرسل عنوان الإعلان كرسالة عادية (حتى 34 حرف)، أو دوس «التالي» وأستعمل اسم الحملة.\n' + (S.hdl ? '\nالعنوان الحالي: ' + S.hdl : '') + (needUrl ? '\nزر الإجراء: ' + CTAS[S.cta] : ''), kb);
}
// summary
const RL = regionList() || [], IL = interestList() || [];
const rn = S.regs.length ? S.regs.map(id => { const x = RL.find(r => r.id === id); return x ? x.name : id; }).join('، ') : 'كل العراق';
const inn = S.ints.length ? S.ints.map(id => { const x = IL.find(r => r.id === id); return x ? x.name : id; }).join('، ') : 'كل الاهتمامات';
const needUrl2 = S.obj === 'sal' || S.obj === 'trf';
const L = [head('ملخص الحملة').trimEnd(), '',
  '🎯 الهدف: ' + OBJ[S.obj][1], '🏢 الحساب: ' + (accOf() ? accOf().name + ' (' + accOf().cur + ')' : 'غير محدد'),
  ...(S.obj === 'sal' ? ['🧩 البكسل: ' + (S.pix ? S.pix.slice(0, 8) + '…' : 'غير محدد')] : []), ...(needUrl2 ? ['🔗 الرابط: ' + (S.url ? sh(S.url, 60) : 'غير محدد')] : []),
  '📍 المحافظات: ' + rn, '🎂 العمر: ' + ageTxt(S), '🚻 الجنس: ' + GEN[S.gen], '🗣️ اللغة: ' + (LNG[S.lng] || S.lng), '❤️ الاهتمامات: ' + inn, '',
  '💰 الميزانية: ' + (S.bud ? S.bud + ' ' + ((accOf() && accOf().cur) || '') + ' (إجمالية)' : 'غير محددة'), '📅 المدة: ' + (S.days ? S.days + (S.days === 1 ? ' يوم' : ' أيام') : 'غير محددة'),
  '🎬 الفيديو: ' + (S.vid ? '✅ جاهز' + (S.vnm ? ' (' + S.vnm + ')' : '') : '❌ ناقص'), '📝 العنوان: ' + (S.hdl || 'اسم الحملة') + (needUrl2 ? ' | الزر: ' + CTAS[S.cta] : ''), '',
  '⏸️ تنرفع كحملة كاملة (حملة + مجموعة + إعلان) بحالة متوقفة، وما يصرف شي لين تفعّلها.'];
const ready = accOf() && S.bud && S.days && S.vid && (!needUrl2 || S.url) && (S.obj !== 'sal' || S.pix);
const kbS = []; if (ready) kbS.push([{ t: '🚀 رفع كحملة متوقفة', c: 'sn:go' }]);
kbS.push([{ t: '🔁 من جديد', c: 'sn:s' }, { t: '🎬 الفيديو', c: 'sn:b:vid' }, { t: '✏️ الاهتمامات', c: 'sn:b:int' }], [{ t: '🏠 الرئيسية', c: 'h' }]);
return done(L.join('\n'), kbS);
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
