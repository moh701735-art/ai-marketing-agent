# -*- coding: utf-8 -*-
"""كليشه واحدة تروّج بكل المنصات (p295): تيك توك + فيسبوك/إنستغرام + سناب شات. محلل ثابت (بدون LLM) + بطاقة مراجعة واحدة + إطلاق متوازي بعد «تأكيد».
الدخول: رسالة (أو كابشن فيديو) أول سطر فيها «روّج: تيك توك + فيسبوك + سناب». callbacks بادئة `mp:` (mp:go تأكيد، mp:x إلغاء، mp:s إعادة).
القرارات (المالك 27-11): نفس المبلغ لكل منصة، الكل يشتغل مباشرة بعد التأكيد (تيك توك/فيسبوك)، الهدف بالكليشه لكل منصة. سناب = مسودة متوقفة (ما فيه عملية تفعيل بالـBroker) والبطاقة تقولها.
لا يلمس أي مسار إطلاق قائم: يستدعي نفس عمليات Broker (tiktok.launch_spark, meta.launch_whatsapp, snapchat.launch_draft). الحالة بـapi.ui_set بمفتاح mp:<chat> ساعة."""

SQL_DATA = ("SELECT 'acct'::text AS kind, platform::text AS a, external_id::text AS b, name::text AS c, currency::text AS d FROM api.list_ad_accounts($1) WHERE enabled "
            "UNION ALL SELECT 'page', page_id::text, name::text, NULL, NULL FROM api.list_pages($1) "
            "UNION ALL SELECT 'state', data::text, age_s::text, NULL, NULL FROM api.ui_get($1, 'mp:' || $2)")

LIB = r"""
const FX = 1555, CAP_USD = 300, LINE = '━━━━━━━━━━━━━━';
const PN = { tt: '🎵 تيك توك', meta: '🔵 فيسبوك/إنستغرام', snap: '👻 سناب شات' };
const norm = s => String(s || '').replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632)).replace(/[ً-ٟـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/\r/g, '').toLowerCase();
const sh = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const fnum = n => Number(n || 0).toLocaleString('en-US');
const hash36 = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0; return h.toString(36); };
const HDR = /^\s*(?:روج|ارفع|promo)\s*[:：]\s*(.+)$/;
const isPromoText = t => { const l = norm(t).split('\n').map(x => x.trim()).find(x => x); return !!(l && HDR.test(l)); };
const platOf = s => { const n = norm(s).replace(/\s+/g, ' ').trim(); if (/^(?:تيك ?توك|تكتوك|tiktok)$/.test(n)) return 'tt'; if (/^(?:فيس ?بوك|فيس|facebook|انستغرام|انستا|instagram|ميتا)$/.test(n)) return 'meta'; if (/^(?:سناب ?شات|سناب|snap(?:chat)?)$/.test(n)) return 'snap'; return ''; };
const DAYW = { 'واحد': 1, 'وحده': 1, 'يومين': 2, 'اثنين': 2, 'ثلاث': 3, 'ثلاثه': 3, 'اربع': 4, 'اربعه': 4, 'خمس': 5, 'خمسه': 5, 'سبع': 7, 'سبعه': 7 };
function parseDays(v) { const n = norm(v); if (/يومين/.test(n)) return 2; let m = /(\d{1,2})\s*(?:ايام|يوم)/.exec(n); if (m) return parseInt(m[1], 10); m = /(?:^|\s)(\d{1,2})(?:\s|$)/.exec(n); if (m && !/دولار|الف|دينار/.test(n)) return parseInt(m[1], 10); m = /(واحد|وحده|ثلاثه|ثلاث|اربعه|اربع|خمسه|خمس|سبعه|سبع)/.exec(n); if (m) return DAYW[m[1]]; if (/يوم/.test(n)) return 1; return 0; }
function parseBudget(v) {
  const n = norm(v).replace(/[,،]/g, ''); const m = /(\d+(?:\.\d+)?)\s*(الف|الاف|k)?/.exec(n); if (!m) return null; let x = parseFloat(m[1]); const th = !!m[2];
  const usd = /(?:دولار|\$|usd|دولاره)/.test(n), iqd = /(?:دينار|iqd|د\.ع)/.test(n) || th;
  if (th) x = x * 1000;
  let cur = usd ? 'USD' : (iqd ? 'IQD' : (x >= 1000 ? 'IQD' : 'USD'));
  return { amount: x, cur, usd: cur === 'IQD' ? Math.round(x / FX * 10000) / 10000 : x };
}
function parseAge(v) { const n = norm(v); if (/كل|الكل|جميع/.test(n) && !/\d/.test(n)) return { min: 0, max: 0, ok: true }; const m = /(\d{2})\s*(?:-|الى|إلى|لل?ى|–|—|to)\s*(\d{2})/.exec(n); if (m) { const a = +m[1], b = +m[2]; return a >= 18 && b <= 65 && a < b ? { min: a, max: b, ok: true } : { ok: false }; } const m2 = /(?:من\s*)?(\d{2})\s*(?:فما فوق|\+)?/.exec(n); if (m2 && +m2[1] >= 18 && +m2[1] <= 65) return { min: +m2[1], max: 0, ok: true }; return { ok: false }; }
const GENW = { a: /الكل|كل|الجنسين/, m: /رجال|ذكور|رجل/, f: /نساء|اناث|بنات|نسائي/ };
const parseGen = v => { const n = norm(v); for (const k of ['f', 'm', 'a']) if (GENW[k].test(n)) return k; return ''; };
const waNum = s => { const n = norm(s).replace(/[\s\-+]/g, ''); const m = /(?:^|[^0-9])((?:964|0)?7[3-9]\d{8})(?!\d)/.exec(n); if (!m) return ''; let d = m[1]; if (d.startsWith('964')) d = '0' + d.slice(3); if (!d.startsWith('0')) d = '0' + d; return /^07[3-9]\d{8}$/.test(d) ? d : ''; };
const URLRX = /https?:\/\/[^\s\x00-\x1f<>"'،]{4,500}/i;
const FBLINK = /^https:\/\/(?:(?:www\.|m\.|web\.|mbasic\.)?facebook\.com\/|fb\.watch\/|fb\.com\/)/i;
const PLACEHOLDER = /^[#x\s_\-.*]+$/i;
function parseObj(plat, v) {
  const n = norm(v); const o = { key: '', wa: waNum(v), url: ((URLRX.exec(String(v || ''))) || [''])[0] };
  if (/مبيعات|sales/.test(n)) o.key = 'sales'; else if (/عملاء\s*محتملين|ليد|leads?/.test(n)) o.key = 'leads'; else if (/وعي|وصول|reach|awareness/.test(n)) o.key = 'awareness'; else if (/تفاعل|engagement/.test(n)) o.key = 'engagement';
  else if (/زيارات|ترافيك|نقرات|traffic/.test(n)) o.key = 'traffic'; else if (/واتس|whats|محادث|رسائل?/.test(n)) o.key = 'whatsapp';
  return o;
}
function parseCodes(v) { return (String(v || '').match(/[A-Za-z0-9_#\-]{6,64}/g) || []).map(x => x.replace(/^#/, '')).filter(x => x.length >= 6); }
function splitSections(text) {
  const lines = String(text || '').replace(/\r/g, '').split('\n'); const sec = { _: [], tt: [], meta: [], snap: [] }; let cur = '_';
  lines.forEach(raw => { const clean = raw.replace(/[\s\-–—_=*#•]+/g, ' ').trim(); const p = clean && clean.indexOf(':') < 0 && clean.length <= 20 ? platOf(clean) : ''; if (p) { cur = p; return; } sec[cur].push(raw); });
  return sec;
}
function kv(lines) { const out = [], bare = []; lines.forEach(l => { const t = l.trim(); if (!t) return; const m = /^([^:：]{1,24})[:：]\s*(.*)$/.exec(t); if (m && !/^https?$/i.test(m[1].trim())) out.push([norm(m[1]).replace(/\s+/g, ' ').trim(), m[2].trim()]); else bare.push(t); }); return { out, bare }; }
const LBL = { budget: /^(?:ال)?ميزانيه$/, days: /^(?:ال)?مده$|^(?:ال)?ايام$/, age: /^(?:ال)?عمر$/, gen: /^(?:ال)?جنس$/, name: /^(?:ال)?اسم(?: الحمله)?$/, codes: /^(?:كود|كودات|الكود|الكودات|spark|سبارك)$/, link: /^(?:رابط|الرابط|منشور|المنشور|فيديو|الفيديو|link)$/, obj: /^(?:هدف|الهدف)$/, acct: /^(?:حساب|الحساب)$/, page: /^(?:صفحه|الصفحه|page)$/, wa: /^(?:رقم|الرقم|واتساب|واتس)$/ };
const lab = l => { for (const k of Object.keys(LBL)) if (LBL[k].test(l)) return k; return ''; };
function parsePromo(text, hasFile) {
  const E = [], W = []; const sec = splitSections(text); const head = sec._.map(x => x.trim()).find(x => x) || '';
  const hm = HDR.exec(norm(head)); const plats = []; if (hm) hm[1].split(/[+،,&\/]|\sو\s|\sمع\s/).forEach(p => { const k = platOf(p.trim()); if (k && plats.indexOf(k) < 0) plats.push(k); });
  if (!plats.length) E.push('ما فهمت المنصات. اكتب أول سطر: «روّج: تيك توك + فيسبوك + سناب».');
  const sh0 = kv(sec._.slice(sec._.indexOf(head) + 1)); const P = { plats, bud: null, days: 0, age: { min: 0, max: 0, ok: true }, gen: 'a', name: '', tt: null, meta: null, snap: null };
  sh0.out.forEach(([l, v]) => { const k = lab(l); if (k === 'budget') P.bud = parseBudget(v); else if (k === 'days') P.days = parseDays(v); else if (k === 'age') P.age = parseAge(v); else if (k === 'gen') { const g = parseGen(v); if (g) P.gen = g; else E.push('الجنس غير مفهوم: ' + sh(v, 20)); } else if (k === 'name') P.name = v.replace(/[\x00-\x1f<>]/g, ' ').trim().slice(0, 40); });
  if (!P.bud || !(P.bud.amount > 0)) E.push('ناقصة الميزانية (مثل: 20 دولار).');
  else if (P.bud.usd > CAP_USD) E.push('الميزانية أكبر من الحد الأقصى لكل منصة (' + CAP_USD + '$). قلّلها أو اطلبها بحملة منفصلة.');
  if (!(P.days >= 1 && P.days <= 30)) E.push('ناقصة المدة (مثل: يوم واحد).');
  if (!P.age.ok) E.push('العمر غير مفهوم (مثل: 25-45 أو كل الأعمار).');
  plats.forEach(pk => {
    const s = kv(sec[pk]); const Q = { acctName: '', pageName: '', codes: [], url: '', obj: '', wa: '', objRaw: '' };
    s.out.forEach(([l, v]) => { const k = lab(l); if (k === 'codes') Q.codes = Q.codes.concat(parseCodes(v)); else if (k === 'link') { const u = (URLRX.exec(v) || [''])[0]; if (u) Q.url = u; } else if (k === 'obj') { Q.objRaw = v; const o = parseObj(pk, v); Q.obj = o.key; if (o.wa) Q.wa = o.wa; if (o.url) Q.url2 = o.url; } else if (k === 'acct') Q.acctName = v; else if (k === 'page') Q.pageName = v; else if (k === 'wa') { const w = waNum(v); if (w) Q.wa = w; } });
    s.bare.forEach(b => { const u = (URLRX.exec(b) || [''])[0]; if (u && !Q.url) Q.url = u; });
    P[pk] = Q;
  });
  const T = P.tt, M = P.meta, S = P.snap;
  if (T) { if (!T.codes.length) E.push('تيك توك: ناقص كود Spark.'); else if (T.codes.every(c => PLACEHOLDER.test(c))) E.push('تيك توك: الكود مثال (XXXX). حط كود Spark حقيقي.');
    if (!['whatsapp', 'sales', 'leads', 'traffic'].includes(T.obj)) E.push('تيك توك: الهدف ناقص أو غير مدعوم (محادثات واتساب / مبيعات / عملاء محتملين / زيارات).');
    if (T.obj === 'whatsapp' && !T.wa) E.push('تيك توك: ناقص رقم الواتساب بالهدف.'); if (T.obj === 'traffic' && !(T.url2 || T.url)) E.push('تيك توك: هدف الزيارات يحتاج رابط الوجهة.'); }
  if (M) { if (!M.url || !FBLINK.test(M.url)) E.push('فيسبوك: ناقص رابط منشور/ريل فيسبوك (facebook.com أو fb.watch).');
    if (!['whatsapp', 'traffic', 'awareness', 'engagement'].includes(M.obj)) E.push('فيسبوك: الهدف ناقص أو غير مدعوم (رسائل واتساب / زيارات / وعي / تفاعل).');
    if (M.obj === 'whatsapp' && !M.wa) E.push('فيسبوك: ناقص رقم الواتساب بالهدف.'); if (M.obj === 'traffic' && !(M.url2 && /^https:/.test(M.url2))) E.push('فيسبوك: هدف الزيارات يحتاج رابط موقع https بسطر الهدف.'); }
  if (S) { if (!hasFile) E.push('سناب: الفيديو لازم يكون مرفقاً بنفس رسالة تيليجرام (الكليشه ككابشن).');
    if (S.obj !== 'traffic') E.push('سناب: المتاح الآن هدف «زيارات» فقط (سنابّ يرفض المبيعات بدون أحداث شراء).'); else if (!/^https:\/\//.test(S.url2 || '')) E.push('سناب: ناقص رابط الوجهة https بسطر الهدف (زيارات https://…). لا wa.me: سناب يرفضه، استعمل صفحة الواتساب الوسيطة.'); }
  return { P, E, W };
}
const nameKey = s => norm(s).replace(/[^a-z0-9ء-ي]+/g, '');
function pickOne(list, want, what) {
  if (!list.length) return { err: what + ': ما عندك حساب مربوط.' };
  const w = nameKey(want || '');
  if (w) { let m = list.filter(x => nameKey(x.name) === w || x.id === String(want).trim() || x.id === 'act_' + String(want).trim()); if (m.length === 1) return { it: m[0] }; m = w.length >= 3 ? list.filter(x => nameKey(x.name).includes(w) || x.id.includes(String(want).trim())) : []; if (m.length === 1) return { it: m[0] }; return { err: what + ': «' + sh(want, 24) + '» ' + (m.length ? 'ينطبق على أكثر من واحد: ' + m.slice(0, 5).map(x => sh(x.name || x.id, 22)).join('، ') : 'غير موجود بحساباتك') + '.' }; }
  if (list.length === 1) return { it: list[0] };
  return { err: what + ': اكتب «حساب: الاسم». المتاح: ' + list.slice(0, 6).map(x => sh(x.name || x.id, 22)).join('، ') + '.' };
}
"""

JS_PLAN = r"""
const d = $('Route').first().json;
const rows = $input.all().map(i => i.json).filter(r => r && r.kind);
const ACC = rows.filter(r => r.kind === 'acct').map(r => ({ pl: String(r.a || ''), id: String(r.b || ''), name: String(r.c || ''), cur: String(r.d || '').toUpperCase() }));
const PGS = rows.filter(r => r.kind === 'page' && /^[0-9]{5,25}$/.test(String(r.a))).map(r => ({ id: String(r.a), name: String(r.b || r.a).replace(/[\x00-\x1f<>]/g, ' ').trim().slice(0, 120) }));
let S0 = null, age0 = 99999; const sr = rows.find(r => r.kind === 'state'); if (sr) { try { S0 = JSON.parse(sr.a); } catch (e) {} age0 = parseInt(sr.b, 10) || 0; }
const isCb = !!d.cb; const op = isCb ? (String(d.cb).split(':')[1] || '') : 's';
const base = { ctx: d.ctx, chatId: d.chatId, edit: isCb, items: 0 };
const items = [];
const tgt = pl => ACC.filter(a => a.pl === pl);
const metaId = id => 'act_' + String(id).replace(/^act_/, '');
if (op === 's') {
  const text = String(d.args || d.text || d.caption || '');
  const fid = String(d.fileId || '').trim(); const hasFile = !!(fid && /^[A-Za-z0-9_\-]{10,200}$/.test(fid) && Number(d.fileSize || 0) <= 20000000);
  const { P, E, W } = parsePromo(text, hasFile); const R = { tt: null, meta: null, snap: null };
  if (!E.length) {
    if (P.tt) { const r = pickOne(tgt('tiktok'), P.tt.acctName, 'تيك توك'); if (r.err) E.push(r.err); else R.tt = r.it; }
    if (P.meta) { const r = pickOne(tgt('meta').map(a => ({ ...a, id: metaId(a.id) })), P.meta.acctName, 'فيسبوك'); if (r.err) E.push(r.err); else R.meta = r.it;
      if (PGS.length >= 2) { const q = pickOne(PGS, P.meta.pageName, 'الصفحة'); if (q.err) E.push(q.err); else R.page = q.it; } else if (PGS.length === 1) R.page = PGS[0]; }
    if (P.snap) { const r = pickOne(tgt('snapchat'), P.snap.acctName, 'سناب'); if (r.err) E.push(r.err); else R.snap = r.it; }
    if (P.gen !== 'a' && ((P.tt) || (P.meta && P.meta.obj === 'whatsapp'))) W.push('الجنس يُطبَّق على فيسبوك (وعي/زيارات/تفاعل) وسناب فقط. تيك توك ورسائل فيسبوك: الكل.');
    if (P.snap && P.snap.obj === 'traffic' && !R.snap) { /* خطأ الحساب أعلاه */ }
  }
  base.parse = { P, E, W, R }; base.fid = hasFile ? fid : ''; base.fname = String(d.fileName || '').slice(0, 40);
  if (!E.length) base.S = { st: 'ready', P, R, fid: base.fid, ts: Date.now() }; else base.S = null;
  base.mode = 'review';
} else if (op === 'x') { base.mode = 'cancel'; base.S = { st: 'done' }; }
else if (op === 'go') {
  base.mode = 'go';
  if (!S0 || S0.st !== 'ready' || age0 > 1800) { base.stale = true; base.S = null; }
  else {
    const { P, R } = S0; base.S = { st: 'done' }; const nm = P.name || ('حملة مشتركة ' + new Date().toISOString().slice(5, 10));
    const stamp = String(d.chatId).replace(/[^0-9]/g, '') + '-' + hash36(JSON.stringify([P, R && R.tt && R.tt.id, R && R.meta && R.meta.id])) + '-' + Math.floor(Date.now() / 120000);
    const idem = k => ('mp-' + stamp + '-' + k).slice(0, 90);
    const need = (k, pl, acct, o, params) => items.push({ json: { ...base, need: true, k, platform: pl, ad_account: acct, op: o, params, idem: idem(k) } });
    if (P.tt && R.tt) { const T = P.tt; const bud = R.tt.cur === 'IQD' ? Math.round(P.bud.usd * FX) : P.bud.usd;
      const prm = { objective: T.obj, budget: bud, budget_mode: 'total', days: P.days, spark_codes: T.codes, campaign_name: nm.slice(0, 120), activate_now: true };
      if (T.obj === 'whatsapp') prm.whatsapp_number = T.wa; if (T.obj === 'traffic') prm.landing_url = T.url2 || T.url;
      if (P.age.min) { prm.age_min = P.age.min; if (P.age.max) prm.age_max = P.age.max; }
      need('tt', 'tiktok', R.tt.id, 'tiktok.launch_spark', prm); }
    if (P.meta && R.meta) { const M = P.meta; const prm = { post_url: M.url, budget_usd: P.bud.usd, days: P.days, name: nm.slice(0, 120), budget_mode: 'total', countries: ['IQ'], activate_now: true };
      if (M.obj === 'whatsapp') prm.whatsapp = M.wa; else { prm.objective_key = M.obj; if (M.obj === 'traffic') prm.link_url = M.url2; if (P.gen === 'm') prm.genders = ['1']; else if (P.gen === 'f') prm.genders = ['2']; }
      if (P.age.min) { prm.age_min = P.age.min; if (P.age.max) prm.age_max = P.age.max; }
      if (R.page) prm.page_id = R.page.id;
      need('meta', 'meta', R.meta.id, 'meta.launch_whatsapp', prm); }
    if (P.snap && R.snap) { const bud = R.snap.cur === 'IQD' ? Math.round(P.bud.usd * FX) : P.bud.usd;
      const prm = { account_id: R.snap.id, name: nm.slice(0, 100), objective: 'trf', budget: bud, days: P.days, regions: [], gender: P.gen, lang: [], interests: [], file_id: S0.fid, cta: 'MORE', brand_name: String(R.snap.name || nm).slice(0, 25), headline: nm.slice(0, 34), landing_url: P.snap.url2 };
      if (P.age.min) { prm.min_age = P.age.min; if (P.age.max) prm.max_age = P.age.max; }
      need('snap', 'snapchat', '', 'snapchat.launch_draft', prm); }
    base.S0 = S0;
  }
} else { base.mode = 'cancel'; base.S = S0; }
base.items = items.length;
return items.length ? items.map(x => ({ json: { ...x.json, items: items.length, S0: base.S0 } })) : [{ json: base }];
"""

JS_RENDER = r"""
const Ps = $('MP2: plan').all().map(i => i.json); const P0 = Ps[0];
const home = [[{ t: '🏠 الرئيسية', c: 'h' }]];
const out = (text, kb, state) => [{ json: { ctx: P0.ctx, chatId: P0.chatId, text: String(text).slice(0, 3800), keyboard: (kb || home).slice(0, 8), edit: P0.edit, state: state === undefined ? '' : (state ? JSON.stringify(state) : '') } }];
if (P0.mode === 'cancel') return out('❌ انلغت الحملة المشتركة. ما انرفع شي.', home, P0.S);
if (P0.stale) return out('⚠️ انتهت صلاحية البطاقة أو ما فيه حملة جاهزة. ارسل الكليشه من جديد.', home, '');
const AMT = u => '$' + fnum(u);
if (P0.mode === 'review') {
  const { P, E, W, R } = P0.parse;
  if (E.length) return out('⚠️ ما قدرت أكمل، لا شي انرفع:\n' + LINE + '\n' + E.map(x => '• ' + x).join('\n') + '\n\nصحّح وارسل الكليشه من جديد.', home, '');
  const n = P.plats.length; const bud = P.bud.usd; const L = ['🧾 مراجعة الحملة المشتركة', LINE, '🏷️ الاسم: ' + (P.name || 'تلقائي'),
    '💰 ' + AMT(bud) + ' لكل منصة × ' + n + ' = ' + AMT(Math.round(bud * n * 100) / 100) + ' (المجموع)', '📅 المدة: ' + P.days + (P.days === 1 ? ' يوم' : ' أيام') + ' (ميزانية إجمالية، الحملة تنتهي لحالها)',
    '🎂 العمر: ' + (P.age.min ? 'من ' + P.age.min + (P.age.max ? ' إلى ' + P.age.max : ' فما فوق') : 'كل الأعمار') + ' | 🚻 ' + ({ a: 'الكل', m: 'رجال', f: 'نساء' })[P.gen] + ' | 📍 العراق', ''];
  if (P.tt) { const a = R.tt; L.push('🎵 تيك توك: حساب «' + sh(a.name || a.id, 24) + '» (' + a.cur + ') | ' + ({ whatsapp: 'محادثات واتساب ' + P.tt.wa, sales: 'مبيعات', leads: 'عملاء محتملين', traffic: 'زيارات' })[P.tt.obj] + ' | ' + P.tt.codes.length + ' كود Spark | يشتغل مباشرة بعد التأكيد'); }
  if (P.meta) { const a = R.meta; L.push('🔵 فيسبوك/إنستغرام: حساب «' + sh(a.name || a.id, 24) + '» (' + a.cur + ')' + (R.page ? ' | صفحة «' + sh(R.page.name, 26) + '»' : '') + ' | ' + ({ whatsapp: 'رسائل واتساب ' + P.meta.wa, traffic: 'زيارات', awareness: 'وعي', engagement: 'تفاعل' })[P.meta.obj] + ' | يشتغل مباشرة بعد التأكيد (إنستغرام ضمن أماكن الظهور بنفس الحملة)'); }
  if (P.snap) { const a = R.snap; L.push('👻 سناب: حساب «' + sh(a.name || a.id, 24) + '» (' + a.cur + ') | زيارات ' + sh(P.snap.url2, 40) + ' | 🎬 الفيديو مرفق ✅ | ينرفع **مسودة متوقفة** (التفعيل من Snap Ads Manager)'); }
  if (W.length) { L.push(''); W.forEach(w => L.push('ℹ️ ' + w)); }
  L.push('', '⚠️ فيسبوك وسناب ما عندهم إيقاف صرف تلقائي (الحارس لتيك توك فقط). السقف هو الميزانية الإجمالية والمدة.', 'دوس «تأكيد وتشغيل» لتنفيذ كل المنصات.');
  return out(L.join('\n'), [[{ t: '✅ تأكيد وتشغيل', c: 'mp:go' }, { t: '❌ إلغاء', c: 'mp:x' }]], P0.S);
}
// go: نتائج كل منصة
const R = {}; Ps.forEach((it, i) => { if (it.k) R[it.k] = $input.all().map(x => x.json)[i] || {}; });
const S0 = Ps[0].S0 || {}; const P = S0.P || {};
const L = ['📣 نتيجة الحملة المشتركة', LINE];
const errT = r => String((r.error && (r.error.message || r.error.class)) || 'خطأ غير معروف').slice(0, 300);
const dd = r => r.data || {};
if (P.tt) { const r = R.tt; if (!r) L.push('🎵 تيك توك: ما انرسل (لا حساب).'); else if (r.ok) { const x = dd(r); L.push('🎵 تيك توك: ✅ انرفعت' + (x.campaign_id ? ' | الحملة ' + x.campaign_id : '') + (x.enabled === false ? ' | ⏸️ متوقفة' : ' | تم طلب التشغيل (تأكد من حالتها بتقرير الساعة)')); } else { L.push('🎵 تيك توك: ❌ ' + errT(r)); const cb = dd(r).created_before_failure || dd(r).made; if (cb && (cb.campaign_id || cb.campaign)) L.push('   ⚠️ انعمل جزء: ' + (cb.campaign_id || cb.campaign) + ' (راجعه بمدير إعلانات تيك توك).'); } }
if (P.meta) { const r = R.meta; if (!r) L.push('🔵 فيسبوك: ما انرسل (لا حساب).'); else if (r.ok) { const x = dd(r); L.push('🔵 فيسبوك/إنستغرام: ✅ انرفعت | الحملة ' + (x.campaign_id || '؟') + ' | الحالة: ' + (x.status || '؟') + (x.activation_error ? ' | ⚠️ التفعيل: ' + String(x.activation_error).slice(0, 120) : '')); } else { L.push('🔵 فيسبوك/إنستغرام: ❌ ' + (/post_not_from_selected_page/.test(errT(r)) ? 'المنشور مو من الصفحة المختارة' : errT(r))); const cb = dd(r).created_before_failure; if (cb && cb.campaign_id) L.push('   ⚠️ انعملت حملة متوقفة ' + cb.campaign_id + ' (احذفها أو كمّلها من Ads Manager، ما تصرف).'); } }
if (P.snap) { const r = R.snap; if (!r) L.push('👻 سناب: ما انرسل (لا حساب).'); else if (r.ok) { const x = dd(r); L.push('👻 سناب: ✅ انرفعت مسودة متوقفة' + (x.campaign_id ? ' | ' + x.campaign_id : '') + ' | فعّلها من Snap Ads Manager'); } else L.push('👻 سناب: ❌ ' + errT(r) + (dd(r).created_before_failure ? ' | ⚠️ انعمل جزء متوقف (احذفه من Snap)' : '')); }
L.push('', 'كل منصة نتيجتها مستقلة. ما فيه تراجع تلقائي، ولا إعادة محاولة آلية.');
return out(L.join('\n'), [[{ t: '🔁 كليشه جديدة', c: 'mp:s' }, { t: '🏠 الرئيسية', c: 'h' }]], { st: 'done' });
"""

JS_REPLY = r"""
const r = $('MP2: render').first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, keyboard: r.keyboard, edit: r.edit } }];
"""


def build(b, w, sw, idx, reply, CRT):
    code, pg, call_broker = b.code, b.pg, b.call_broker
    data = pg(w, "MP2: data", SQL_DATA, "={{ [$('Route').first().json.ctx, String($('Route').first().json.chatId)] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    plan = code(w, "MP2: plan", LIB + JS_PLAN)
    need = w.add("MP2: need broker?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.need ? 1 : 0 }}"})
    call = call_broker(w, "MP2: launch", mode="each")
    render = code(w, "MP2: render", LIB + JS_RENDER)
    save = pg(w, "MP2: save state",
              "SELECT CASE WHEN $3::text <> '' THEN api.ui_set($1, 'mp:' || $2, 'v', $3::jsonb, 3600)::text END AS saved",
              "={{ [$json.ctx, String($json.chatId), $json.state || ''] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    out = reply("MP2: reply", JS_REPLY)
    w.link(sw, data, idx)
    w.chain(data, plan, need)
    w.link(need, render, 0)
    w.link(need, call, 1)
    w.chain(call, render)
    w.chain(render, save, out)
