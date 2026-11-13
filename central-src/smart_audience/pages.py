"""smart_audience/pages.py — 🎯 Smart Audience Builder (منشئ الجمهور الذكي). Module مستقل فوق البوت المركزي؛ مفتاح تشغيل/إيقاف بالقاعدة (db/72_smart_audience.sql).

يُبنى داخل workflow الاستقبال بنفس نمط premium_features: build(b, w, sw, idx, reply, CRT) يضيف عقد
  SA: data → plan → (cache hit? لا Broker) → SA: read via Broker (قراءة فقط) → SA: render → SA: save → SA: reply.
المبدأ: النظام يقترح — المستخدم يختار — تيك توك يعطي الحجم — النظام يعرضه حرفياً — المستخدم يقرر.
- كل اهتمام معروض هو keyword_id حقيقي رجّعه tiktok.recommend_interests (قاموس الأسواق يُستعمل كمفاتيح بحث فقط). لا يُرسل أي ID خارج ما رجّعه تيك توك.
- التقدير: tiktok.estimate_audience (قراءة فقط) يُعرض كما رجع (user_count{lower_end,upper_end} + user_count_stage). **تأكد بالفحص (p153): التقدير يتفاعل مع الدولة/الجنس/العمر ولا يتفاعل مع الاهتمامات** — ولذلك الواجهة تقول ذلك صراحة ولا تقدّم رقماً «يتحرك» باختيار الاهتمامات.
- لا إنشاء حملات ولا أي عملية كتابة. «متابعة» تتحقق من الاختيار وتحفظ القائمة النهائية بحالة الجلسة (sa:<chat>) لربطها بمعالج الحملة بالمرحلة 2.
callback_data: sa | sa:mk:<سوق> | sa:t:<رقم> | sa:tb:<d|r|n|a> | sa:pg:<n> | sa:lv:<p|b|w|x> | sa:g:<a|f|m> | sa:ag:<all|1824|2534|3544|45p> | sa:r | sa:sv | sa:cmp | sa:cx | sa:ok | sa:cfg"""

SQL_DATA = ("SELECT 'cfg'::text AS kind, smart_audience.config($1)::text AS a, NULL::text AS b, NULL::text AS c, NULL::text AS d, NULL::text AS e, NULL::text AS f "
            "UNION ALL SELECT 'state', data::text, age_s::text, NULL, NULL, NULL, NULL FROM api.ui_get($1, 'sa:' || $2) "
            "UNION ALL SELECT 'cache', key, value::text, age_s::text, NULL, NULL, NULL FROM smart_audience.cache_list($1) "
            "UNION ALL SELECT 'trace', api.ui_set($1, 'sa:t1', 'v', jsonb_build_object('at', now()::text, 'chat', $2::text), 3600)::text, NULL, NULL, NULL, NULL, NULL "      # تتبّع مؤقت (تشخيص p155)
            "UNION ALL SELECT 'acct', external_id::text, name::text, platform::text, currency::text, status::text, enabled::text FROM api.list_ad_accounts($1)")

LIB = r"""
const NUM = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
const N0 = v => Math.round(Number(v) || 0).toLocaleString('en-US');
const sh = (s, n) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const LINE = '━━━━━━━━━━━━';
const norm = s => String(s || '').replace(/[ً-ْـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632)).toLowerCase();
const NOEST = '⚠️ لا يتوفر تقدير مباشر لحجم الجمهور من TikTok لهذا الاستهداف حالياً.';
const NOTE_INT = 'ℹ️ تقدير تيك توك يتغير مع الدولة والجنس والعمر فقط — اختيار الاهتمامات ما يغيّر الرقم (تأكدنا بالفحص).';
const TIERS = { d: ['🔥', 'مباشر جداً'], r: ['🟢', 'مرتبط'], n: ['🟡', 'قريب'], a: ['🔵', 'جمهور مجاور'] };
const LV = { p: ['🔵 دقيق', ['d']], b: ['🟢 متوازن', ['d', 'r']], w: ['🟡 واسع', ['d', 'r', 'n']], x: ['🔴 توسع كبير', ['d', 'r', 'n', 'a']] };
const AGES = { all: ['كل الأعمار', null], '1824': ['18–24', ['AGE_18_24']], '2534': ['25–34', ['AGE_25_34']], '3544': ['35–44', ['AGE_35_44']], '45p': ['45+', ['AGE_45_54', 'AGE_55_100']] };
const GEN = { a: ['الكل', null], f: ['إناث', 'GENDER_FEMALE'], m: ['ذكور', 'GENDER_MALE'] };
// قاموس الأسواق: يُستعمل فقط كمفاتيح بحث عن اهتمامات تيك توك الحقيقية (لا يُعرض ولا يُرسل منه شي مباشرة). tiers: seeds لكل مستوى.
const MK = {
  bty: { n: '🧴 عناية بالبشرة / تبييض', w: ['تبييض', 'بشره', 'كريم', 'عنايه', 'سيروم', 'تصبغ', 'تفتيح', 'whitening', 'skin', 'cream', 'serum'], d: ['skin whitening', 'skin brightening', 'pigmentation'], r: ['skincare', 'body care', 'personal care'], n: ['cosmetics', 'beauty', 'makeup'], a: ['hair care', 'beauty salon'] },
  hair: { n: '💇 شعر وصبغات', w: ['شعر', 'صبغ', 'صبغه', 'شامبو', 'كيراتين', 'حنه', 'hair', 'dye', 'shampoo', 'keratin'], d: ['hair dye', 'hair color', 'hair coloring'], r: ['hair care', 'hair treatment', 'shampoo'], n: ['beauty salon', 'hair salon', 'hairstyle'], a: ['skincare', 'beauty'] },
  mkp: { n: '💄 مكياج ومستحضرات تجميل', w: ['مكياج', 'روج', 'ماسكرا', 'تجميل', 'مستحضرات', 'makeup', 'cosmetics', 'lipstick'], d: ['makeup', 'lipstick', 'mascara'], r: ['cosmetics', 'beauty products', 'makeup tutorial'], n: ['beauty', 'skincare', 'fashion'], a: ['hair care', 'nail art'] },
  mob: { n: '📱 موبايلات وإلكترونيات', w: ['موبايل', 'هاتف', 'جوال', 'ايفون', 'سامسونج', 'شاحن', 'سماعه', 'mobile', 'phone', 'iphone', 'samsung'], d: ['smartphone', 'mobile phone', 'iphone'], r: ['android', 'phone accessories', 'mobile accessories'], n: ['gadgets', 'technology', 'electronics'], a: ['gaming', 'tech reviews'] },
  clo: { n: '👗 ملابس وأزياء', w: ['ملابس', 'قميص', 'فستان', 'بنطلون', 'جاكيت', 'عبايه', 'حذاء', 'احذيه', 'clothes', 'dress', 'shirt', 'fashion'], d: ['clothes', 'fashion', 'dresses'], r: ['outfit', 'streetwear', "women's fashion"], n: ['shoes', 'accessories', 'style'], a: ['beauty', 'bags'] },
  prf: { n: '🌸 عطور', w: ['عطر', 'عطور', 'بخور', 'دهن عود', 'perfume', 'fragrance', 'cologne'], d: ['perfume', 'fragrance', 'cologne'], r: ['luxury', 'body spray', 'beauty'], n: ['fashion', 'gifts'], a: ['skincare', 'makeup'] },
  fod: { n: '🍰 مطاعم وأكل وحلويات', w: ['مطعم', 'اكل', 'حلويات', 'كيك', 'قهوه', 'وجبات', 'food', 'cake', 'coffee', 'restaurant'], d: ['food', 'desserts', 'restaurant'], r: ['cooking', 'recipes', 'coffee'], n: ['foodie', 'baking'], a: ['travel', 'lifestyle'] },
  hom: { n: '🏠 أثاث ومنزل', w: ['اثاث', 'مطبخ', 'ديكور', 'سجاد', 'منزل', 'furniture', 'decor', 'kitchen'], d: ['furniture', 'home decor', 'kitchen'], r: ['interior design', 'home improvement', 'diy'], n: ['home', 'organization'], a: ['gardening', 'lifestyle'] },
  kid: { n: '🧸 أطفال وألعاب', w: ['اطفال', 'طفل', 'العاب', 'حفاضات', 'رضيع', 'kids', 'baby', 'toys'], d: ['baby products', 'kids toys', 'toys'], r: ['parenting', 'kids fashion', 'baby care'], n: ['family', 'education'], a: ['gaming', 'lifestyle'] }
};
const matchMarket = t => { const s = norm(t); if (!s) return null; let best = null, sc = 0;
  for (const k of Object.keys(MK)) { let c = 0; MK[k].w.forEach(w => { if (s.includes(norm(w))) c += norm(w).length; }); if (c > sc) { sc = c; best = k; } }
  return best; };
const rate = (cfg, lo, up) => { const th = (cfg && cfg.thresholds) || {}; const mid = (NUM(lo) + NUM(up)) / 2; const s = NUM(th.small), m = NUM(th.medium), l = NUM(th.large), v = NUM(th.very_large);
  if (!(s > 0 && m > s && l > m && v > l)) return null;                           // عتبات غير مضبوطة: لا تقييم (لا نخترع حدود)
  return mid < s ? '🔴 جمهور ضيق' : mid < m ? '🟡 جمهور متوسط' : mid < l ? '🟢 جمهور جيد' : mid < v ? '🟢 جمهور واسع' : '🔵 جمهور واسع جداً'; };
const estSig = (cfg, g, ag) => 'est:' + String((cfg && cfg.location_id) || '') + ':' + g + ':' + ag;
const ESTBASE = { objective_type: 'LEAD_GENERATION', optimize_goal: 'CONVERSATION', optimization_goal: 'CONVERSATION', promotion_type: 'LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE',
  optimization_event: 'MESSAGE', messaging_app_type: 'WHATSAPP', billing_event: 'OCPM', bid_type: 'BID_TYPE_NO_BID', placement_type: 'PLACEMENT_TYPE_NORMAL', placements: ['PLACEMENT_TIKTOK'] };
const estParams = (cfg, g, ag) => { const p = { ...ESTBASE, location_ids: [String((cfg && cfg.location_id) || '')] }; if (GEN[g] && GEN[g][1]) p.gender = GEN[g][1]; if (AGES[ag] && AGES[ag][1]) p.age_groups = AGES[ag][1]; return p; };
// قراءة رد التقدير كما رجع (نطاق lower_end/upper_end + user_count_stage). غير ذلك ⇒ null (لا نخترع)
const readEst = r => { if (!r || r.ok !== true) return null; const d = r.data && r.data.data; const u = d && d.user_count; if (!u) return null;
  const lo = Number(u.lower_end), up = Number(u.upper_end); if (!Number.isFinite(lo) || !Number.isFinite(up)) return null;
  return { lo, up, st: d.user_count_stage == null ? null : d.user_count_stage }; };
const failWhy = r => !r ? '' : (r.error && r.error.class === 'rate_limited') ? ' (حد الطلبات من تيك توك — جرّب بعد دقيقة)' : (r.error && /timeout|timed out/i.test(String(r.error.message || r.error.class || ''))) ? ' (انتهت مهلة الطلب)' : '';
"""

JS_PLAN = r"""
const d = $('Route').first().json;
const rows = $input.all().map(i => i.json).filter(r => r && r.kind);
const cfgRow = rows.find(r => r.kind === 'cfg'); let cfg = null; try { cfg = cfgRow ? JSON.parse(cfgRow.a) : null; } catch (e) {}
const on = !!(cfg && cfg.enabled === true);
let st = null, stAge = 1e9; const sr = rows.find(r => r.kind === 'state'); if (sr) { try { st = JSON.parse(sr.a); stAge = Number(sr.b); } catch (e) {} }
const cache = {}; rows.filter(r => r.kind === 'cache').forEach(r => { try { cache[r.a] = { v: JSON.parse(r.b), age: Number(r.c) }; } catch (e) {} });
const accts = rows.filter(r => r.kind === 'acct' && String(r.c) === 'tiktok' && r.f !== 'false' && /^\d{6,25}$/.test(String(r.a)));
const isCb = !!d.cb;
const base = { ctx: d.ctx, chatId: d.chatId, edit: isCb, on, cfg, cmd: String(d.cmd || ''), acct: accts[0] ? String(accts[0].a) : '', needBroker: false, items: [] };
let op = '', arg = '', text = '';
if (isCb) { const p = String(d.cb).split(':'); op = p[1] || ''; arg = p.slice(2).join(':'); } else { op = 'text'; text = String(d.args || '').trim(); }
base.act = op; base.arg = arg; base.text = text;
const S0 = (st && typeof st === 'object') ? st : null; base.st = S0;
const items = [];
const need = (k, extra) => items.push({ json: { ...base, need: true, k, ...extra } });
const lvOf = () => (S0 && S0.lv) || 'b';
if (on && base.acct) {
  let mk = null, search = null;
  if (op === 'mk') mk = MK[arg] ? arg : null;
  else if (op === 'text') { mk = matchMarket(text); if (!mk && S0 && S0.cands && text) search = text; }
  base.mk = mk; base.search = search;
  const gOf = () => (op === 'g' ? (GEN[arg] ? arg : 'a') : ((S0 && S0.g) || 'a')), aOf = () => (op === 'ag' ? (AGES[arg] ? arg : 'all') : ((S0 && S0.ag) || 'all'));
  const prepEst = () => { const g = (mk ? 'a' : gOf()), ag = (mk ? 'all' : aOf()); const sig = estSig(cfg, g, ag); base.g2 = g; base.ag2 = ag; base.sig = sig;
    const c = cache[sig]; if (c && op !== 'r') { base.estCached = c.v; return false; }
    if (S0 && S0.est && S0.est.sig === sig && op !== 'r' && !mk) { base.estCached = S0.est; return false; }
    return true; };
  if (mk) {
    const dc = cache['disc:' + mk]; const seedsNeeded = !(dc && dc.age < 86400);
    if (!seedsNeeded) base.discCached = dc.v;
    const estNeeded = prepEst();                                                        // كل حقول base تُضبط قبل إنشاء أي عنصر
    if (seedsNeeded) { const M = MK[mk]; ['d', 'r', 'n', 'a'].forEach(t => M[t].slice(0, t === 'd' ? 3 : 2).forEach(sd => need('seed', { tier: t, seed: sd, op: 'tiktok.recommend_interests', params: { keywords: [sd], language: 'en', limit: 12 } }))); }
    if (estNeeded) need('est', { params: estParams(cfg, base.g2, base.ag2), op: 'tiktok.estimate_audience' });
  } else if (op === 'g' || op === 'ag' || op === 'r') { if (prepEst()) need('est', { params: estParams(cfg, base.g2, base.ag2), op: 'tiktok.estimate_audience' }); }
  else if (op === 'ok' && S0 && Array.isArray(S0.sel) && S0.sel.length) need('chk', { op: 'tiktok.check_interests', params: { keyword_ids: S0.sel.filter(x => /^\d{3,25}$/.test(String(x))).slice(0, 50) } });
}
base.items = items.length;
const out = items.length ? items.map(it => ({ json: { ...it.json, ad_account: base.acct, platform: 'tiktok' } })) : [{ json: base }];
return out;
"""

JS_RENDER = r"""
const plans = $('SA: plan').all().map(i => i.json); const P = plans[0];
const results = P.need ? $input.all().map(i => i.json) : [];
const cfg = P.cfg || {}; const S0 = P.st || null;
const done = (text, kb, S, cacheSets) => [{ json: { ctx: P.ctx, chatId: P.chatId, text: String(text).slice(0, 3800), keyboard: (kb || [[{ t: '🏠 الرئيسية', c: 'h' }]]).slice(0, 8), edit: P.edit, state: S == null ? '' : JSON.stringify(S), cacheSets: JSON.stringify(cacheSets || []) } }];
const home = [[{ t: '🏠 الرئيسية', c: 'h' }]];
if (!P.on) {          // مطفأ: نفس السلوك القديم
  if (P.edit) return done('❌ خيار غير معروف.', home);
  return [{ json: { ctx: P.ctx, chatId: P.chatId, text: 'ما فهمت الأمر. اكتب /help لتشوف الأوامر.', edit: false, state: '', cacheSets: '[]' } }];
}
const head = t => t + '\n' + LINE + '\n';
const menuKb = () => { const ks = Object.keys(MK), kb = []; for (let i = 0; i < ks.length; i += 2) kb.push(ks.slice(i, i + 2).map(k => ({ t: MK[k].n, c: 'sa:mk:' + k }))); kb.push([{ t: '🏠 الرئيسية', c: 'h' }]); return kb; };
const menuText = (pre) => head('🎯 منشئ الجمهور الذكي') + (pre ? pre + '\n\n' : '') + 'اختر سوق منتجك (أو اكتب /audience <اسم المنتج>):\nأقترح اهتمامات تيك توك الحقيقية المرتبطة بمنتجك، وإنت تختار.\nما أختار الجمهور نيابة عنك، وما أنشئ أي حملة.';
if (!P.acct) return done(head('🎯 منشئ الجمهور الذكي') + 'ما عندك حساب تيك توك مفعّل أقرأ منه. اربط حساب أول.', home);
const E = (name, sig) => (sig ? name : name);
const estFrom = (sig) => {                       // نتيجة التقدير: من الـcache أو من قراءة Broker الحالية
  if (P.estCached && P.estCached.lo != null) return { est: { lo: P.estCached.lo, up: P.estCached.up, st: P.estCached.st, sig, at: P.estCached.at || null }, fresh: false, err: '' };
  const it = results.map((r, i) => ({ r, p: plans[i] })).find(x => x.p && x.p.k === 'est');
  if (!it) return { est: null, fresh: false, err: '' };
  const e = readEst(it.r); return e ? { est: { ...e, sig, at: 1 }, fresh: true, err: '' } : { est: null, fresh: false, err: failWhy(it.r) };
};
const sets = [];
let S = S0 ? JSON.parse(JSON.stringify(S0)) : null;
const op = P.act, arg = P.arg;
// ───── فتح سوق جديد: اكتشاف الاهتمامات ─────
if (P.mk) {
  const M = MK[P.mk]; let cands = null;
  if (P.discCached && Array.isArray(P.discCached.c)) cands = P.discCached.c;
  else {
    const seen = {}; cands = []; let okN = 0, rate = false;
    results.forEach((r, i) => { const p = plans[i]; if (!p || p.k !== 'seed') return; if (!r || r.ok !== true) { if (r && r.error && r.error.class === 'rate_limited') rate = true; return; } okN++;
      const body = r.data && r.data.data; const list = (body && body.recommended_keywords) || [];
      list.forEach(x => { const id = String((x && x.keyword_id) || ''); if (!/^\d{3,25}$/.test(id) || seen[id] || (x.status && String(x.status) !== 'EFFECTIVE')) return; seen[id] = 1; cands.push({ id, n: String(x.keyword || '').slice(0, 60), t: p.tier }); }); });
    const cap = { d: 12, r: 12, n: 10, a: 8 }, cnt = { d: 0, r: 0, n: 0, a: 0 };
    cands = ['d', 'r', 'n', 'a'].flatMap(t => cands.filter(c => c.t === t).slice(0, cap[t]));
    if (!cands.length) return done(menuText() + '\n\n⚠️ ما كدرت أجيب اهتمامات من تيك توك هسه' + (rate ? ' (حد الطلبات — جرّب بعد دقيقة)' : '') + '. جرّب سوق ثاني أو أعد المحاولة.', menuKb());
    sets.push({ k: 'disc:' + P.mk, v: { c: cands }, t: 86400 });
  }
  const g = 'a', ag = 'all', sig = P.sig; const ef = estFrom(sig);
  S = { mk: P.mk, cands, sel: [], lv: 'b', tb: 'd', pg: 0, g, ag, est: ef.est, estErr: ef.err, snaps: (S0 && S0.snaps) || [] };
  if (ef.fresh && ef.est) sets.push({ k: sig, v: { lo: ef.est.lo, up: ef.est.up, st: ef.est.st, at: 1 }, t: 21600 });
}
else if (op === '' || (!S && op !== 'text')) { if (!S && op !== '') return done(menuText('⏳ انتهت الجلسة، ابدأ من جديد.'), menuKb()); return done(menuText(), menuKb(), S); }
else if (op === 'text' && !P.mk) {
  if (!P.search) return done(menuText(P.text ? '🤔 ما عرفت السوق من «' + sh(P.text, 30) + '».' : ''), menuKb(), S);
  S.q = String(P.text).slice(0, 40); S.tb = 'all'; S.pg = 0;
} else if (S) {
  if (op === 't') { const i = parseInt(arg, 10); const c = Number.isInteger(i) ? S.cands[i] : null; if (c) { const k = S.sel.indexOf(c.id); if (k >= 0) S.sel.splice(k, 1); else S.sel.push(c.id); } }
  else if (op === 'tb') { if (TIERS[arg] || arg === 'all') { S.tb = arg; S.pg = 0; S.q = ''; } }
  else if (op === 'pg') { S.pg = Math.max(0, parseInt(arg, 10) || 0); }
  else if (op === 'lv') { if (LV[arg]) { S.lv = arg; if (!LV[arg][1].includes(S.tb) && S.tb !== 'all') S.tb = 'd'; S.pg = 0; } }
  else if (op === 'g' || op === 'ag') { if (op === 'g' && GEN[arg]) S.g = arg; if (op === 'ag' && AGES[arg]) S.ag = arg; const ef = estFrom(P.sig); S.est = ef.est; S.estErr = ef.err; if (ef.fresh && ef.est) sets.push({ k: P.sig, v: { lo: ef.est.lo, up: ef.est.up, st: ef.est.st, at: 1 }, t: 21600 }); }
  else if (op === 'r') { const ef = estFrom(P.sig); S.est = ef.est; S.estErr = ef.err; if (ef.fresh && ef.est) sets.push({ k: P.sig, v: { lo: ef.est.lo, up: ef.est.up, st: ef.est.st, at: 1 }, t: 21600 }); }
  else if (op === 'sv') { if (S.snaps.length >= 3) S.snaps.shift(); S.snaps.push({ names: S.sel.map(id => (S.cands.find(c => c.id === id) || {}).n).filter(Boolean), g: S.g, ag: S.ag, est: S.est ? { lo: S.est.lo, up: S.est.up, st: S.est.st } : null }); }
  else if (op === 'cx') { S.snaps = []; }
}
if (!S) return done(menuText(), menuKb());
// ───── صفحات خاصة ─────
const ratingOf = e => (e ? rate(cfg, e.lo, e.up) : null);
if (op === 'cmp' && S) {
  let t = head('⚖️ مقارنة الجماهير') + 'كل مجموعة محفوظة بتقدير تيك توك لها (الجنس/العمر هم اللي يغيّرون الرقم):\n';
  if (!S.snaps.length) t += '\nما في مجموعات محفوظة. اضغط «💾 احفظ الحالي» من صفحة الاختيار.';
  S.snaps.forEach((s, i) => { const l = 'ABC'[i]; t += '\n' + 'Audience ' + l + '\n• الجنس: ' + GEN[s.g][0] + ' | العمر: ' + AGES[s.ag][0] + '\n• الاهتمامات (' + s.names.length + '): ' + (s.names.slice(0, 6).join('، ') || '—') + (s.names.length > 6 ? '…' : '') + '\n• 👥 ' + (s.est ? N0(s.est.lo) + ' – ' + N0(s.est.up) + (s.est.st != null ? ' (مرحلة ' + s.est.st + ')' : '') + ' ' + (ratingOf(s.est) || '') : 'غير متوفر') + '\n'; });
  t += '\n' + NOTE_INT;
  return done(t, [[{ t: '🗑 مسح المقارنات', c: 'sa:cx' }, { t: '⬅️ رجوع للاختيار', c: 'sa:tb:' + (S.tb || 'd') }], [{ t: '🏠 الرئيسية', c: 'h' }]], S, sets);
}
if (op === 'ok') {
  const chk = results.map((r, i) => ({ r, p: plans[i] })).find(x => x.p && x.p.k === 'chk');
  const known = {}; S.cands.forEach(c => { known[c.id] = c; });
  let ids = S.sel.filter(id => known[id]);                                       // المحقق الأول: فقط IDs رجّعها تيك توك بهالجلسة
  let note = '';
  if (chk && chk.r && chk.r.ok === true) { const body = chk.r.data && chk.r.data.data; const arr = (body && (body.keywords || body.list || body.interest_keywords)) || null;
    if (Array.isArray(arr)) { const okIds = {}; arr.forEach(x => { const id = String((x && (x.keyword_id || x.id)) || ''); if (id && !(x.status && String(x.status) !== 'EFFECTIVE')) okIds[id] = 1; }); const before = ids.length; ids = ids.filter(id => okIds[id]); if (ids.length < before) note = '\n⚠️ ' + (before - ids.length) + ' اهتمام ما عاد صالح عند تيك توك وانشال من القائمة.'; } }
  else if (chk) note = '\nℹ️ التحقق الإضافي من تيك توك غير متاح هسه (القائمة مأخوذة منه قبل لحظات).';
  if (!ids.length) return done(head('🎯 الجمهور') + 'ما اخترت أي اهتمام صالح. ارجع واختر من المربعات.' + note, [[{ t: '⬅️ رجوع للاختيار', c: 'sa:tb:' + (S.tb || 'd') }]], S, sets);
  S.final = ids.map(id => ({ id, n: known[id].n })); S.done = true;
  const t = head('✅ اهتماماتك المعتمدة') + 'الدولة: ' + (cfg.country || '—') + ' | الجنس: ' + GEN[S.g][0] + ' | العمر: ' + AGES[S.ag][0] + '\n\n' + S.final.map((x, i) => (i + 1) + '. ' + sh(x.n, 40) + '  (' + x.id + ')').join('\n') + '\n\n👥 ' + (S.est ? N0(S.est.lo) + ' – ' + N0(S.est.up) + ' ' + (ratingOf(S.est) || '') : 'التقدير غير متوفر') + '\n' + NOTE_INT + note + '\n\nالقائمة محفوظة بجلستك لمدة ساعة. لاستعمالها بحملة تيك توك: ابدأ حملة جديدة ← بشاشة مراجعة الحملة اضغط «🎯 استخدم جمهور منشئ الجمهور» (يدوي فقط، مو سمارت). ما أطلقت ولا أنشأت أي حملة.';
  return done(t, [[{ t: '⬅️ رجوع للاختيار', c: 'sa:tb:' + (S.tb || 'd') }], [{ t: '🏠 الرئيسية', c: 'h' }]], S, sets);
}
// ───── صفحة الاختيار الرئيسية ─────
const lvTiers = LV[S.lv][1]; const tabs = lvTiers; if (S.tb !== 'all' && !tabs.includes(S.tb)) S.tb = tabs[0];
let list = S.cands.map((c, i) => ({ c, i }));
if (S.tb === 'all') { const q = norm(S.q || ''); list = list.filter(x => x.c.n && norm(x.c.n).includes(q)); } else list = list.filter(x => x.c.t === S.tb);
const per = (tabs.length > 3 ? 6 : 9), pages = Math.max(1, Math.ceil(list.length / per));      // حد الـBroker 8 صفوف: مع 4 تبويبات 6 اهتمامات بالصفحة S.pg = Math.min(S.pg || 0, pages - 1);
const part = list.slice(S.pg * per, S.pg * per + per);
const e = S.est; const rt = ratingOf(e);
let t = head('🎯 اختيار الجمهور — ' + sh(MK[S.mk].n, 28));
t += '🎯 جمهورك الحالي\n' + (e ? N0(e.lo) + ' – ' + N0(e.up) + (e.st != null ? '  (مرحلة تيك توك ' + e.st + ')' : '') : NOEST + (S.estErr || '')) + '\n';
t += '🌍 الدولة: ' + (cfg.country || '—') + ' 🇮🇶 | الجنس: ' + GEN[S.g][0] + ' | العمر: ' + AGES[S.ag][0] + '\n☑ الاهتمامات المختارة: ' + S.sel.length + '\n📊 حالة الجمهور: ' + (e ? (rt || 'غير مقيَّم (العتبات غير مضبوطة)') : '—') + '\n';
t += (e ? NOTE_INT + '\n' : '') + '\n' + (S.tb === 'all' ? '🔎 بحث: «' + sh(S.q, 30) + '» (' + list.length + ')' : TIERS[S.tb][0] + ' ' + TIERS[S.tb][1] + ' (' + list.length + ')') + ' — المستوى: ' + LV[S.lv][0] + (pages > 1 ? '\nصفحة ' + (S.pg + 1) + '/' + pages : '') + '\nاضغط المربع لتختار ☐ ← ☑ (وكرر لإلغاء الاختيار).';
const kb = [];
kb.push(tabs.map(x => ({ t: (S.tb === x ? '• ' : '') + TIERS[x][0] + ' ' + TIERS[x][1], c: 'sa:tb:' + x })).slice(0, 3));
if (tabs.length > 3) kb.push(tabs.slice(3).map(x => ({ t: (S.tb === x ? '• ' : '') + TIERS[x][0] + ' ' + TIERS[x][1], c: 'sa:tb:' + x })));
for (let i = 0; i < part.length; i += 3) kb.push(part.slice(i, i + 3).map(x => ({ t: (S.sel.includes(x.c.id) ? '☑ ' : '☐ ') + sh(x.c.n, 16), c: 'sa:t:' + x.i })));
if (pages > 1) kb.push([...(S.pg > 0 ? [{ t: '⬅️ السابق', c: 'sa:pg:' + (S.pg - 1) }] : []), ...(S.pg < pages - 1 ? [{ t: '➡️ التالي', c: 'sa:pg:' + (S.pg + 1) }] : [])]);
kb.push([{ t: '👤 ' + GEN[S.g][0], c: 'sa:g:' + (S.g === 'a' ? 'f' : S.g === 'f' ? 'm' : 'a') }, { t: '🎂 ' + AGES[S.ag][0], c: 'sa:ag:' + (S.ag === 'all' ? '1824' : S.ag === '1824' ? '2534' : S.ag === '2534' ? '3544' : S.ag === '3544' ? '45p' : 'all') }, { t: '🎯 ' + LV[S.lv][0], c: 'sa:lv:' + (S.lv === 'p' ? 'b' : S.lv === 'b' ? 'w' : S.lv === 'w' ? 'x' : 'p') }]);
kb.push([{ t: '🔄 تحديث الجمهور', c: 'sa:r' }, { t: '💾 احفظ للمقارنة', c: 'sa:sv' }, { t: '⚖️ مقارنة', c: 'sa:cmp' }]);
kb.push([{ t: '➡️ متابعة', c: 'sa:ok' }, { t: '⬅️ الأسواق', c: 'sa' }]);
return done(t, kb, S, sets);
"""

JS_SAVE = r"""
const r = $input.first().json;
return [{ json: r }];
"""

JS_REPLY = r"""
const r = $('SA: render').first().json;
return [{ json: { ctx: r.ctx, chatId: r.chatId, text: r.text, keyboard: r.keyboard, edit: r.edit } }];
"""


def build(b, w, sw, idx, reply, CRT):
    code, pg, call_broker = b.code, b.pg, b.call_broker
    data = pg(w, "SA: data", SQL_DATA, "={{ [$('Route').first().json.ctx, String($('Route').first().json.chatId)] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    plan = code(w, "SA: plan", LIB + JS_PLAN)
    need = w.add("SA: need broker?", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 2, "output": "={{ $json.need ? 1 : 0 }}"})
    call = call_broker(w, "SA: read via Broker", mode="each")
    render = code(w, "SA: render", LIB + JS_RENDER)
    save = pg(w, "SA: save state + cache",
              "SELECT CASE WHEN $3::text <> '' THEN api.ui_set($1, 'sa:' || $2, 'v', coalesce(nullif($3::text, ''), '{}')::jsonb, 3600)::text END AS saved, "      # تحويل آمن للحالة الفارغة (p156)
              "api.ui_set($1, 'sa:t2', 'v', jsonb_build_object('at', now()::text, 'len', length($3::text)), 3600)::text AS trace, "      # تتبّع مؤقت (تشخيص p155)
              "(SELECT count(*) FROM jsonb_to_recordset($4::jsonb) AS x(k text, v jsonb, t int) WHERE smart_audience.cache_set($1, x.k, x.v, x.t)) AS cached",
              "={{ [$json.ctx, String($json.chatId), $json.state || '', $json.cacheSets || '[]'] }}", CRT, always=True)
    w.nodes[-1]["onError"] = "continueRegularOutput"
    out = reply("SA: reply", JS_REPLY)
    w.chain(data, plan, need)
    w.link(need, render, 0)
    w.link(need, call, 1)
    w.chain(call, render)
    w.chain(render, save, out)
    # تتبّع تشخيصي مؤقت (p156): فروع جانبية تكتب sa:t3 (بعد الخطة) و sa:t4 (بعد بناء الرد) و sa:t5 (بعد عقدة الرد). فشلها لا يؤثر على المسار.
    for tn, src, key in (("SA: trace after plan", plan, "sa:t3"), ("SA: trace after render", render, "sa:t4"), ("SA: trace after reply", out, "sa:t5")):
        t = pg(w, tn, "SELECT api.ui_set($1, '" + key + "', 'v', jsonb_build_object('at', now()::text, 'n', $2::text), 3600)::text AS t",
               "={{ [$json.ctx, (x => x.length > 1900 ? x.slice(0, 900) + ' ~~~ ' + x.slice(-1000) : x)(JSON.stringify($json))] }}", CRT, always=True)
        w.nodes[-1]["onError"] = "continueRegularOutput"
        w.link(src, t)
    w.link(sw, data, idx)
