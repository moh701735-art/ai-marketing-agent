const inp = $input.first().json;
const norm = (x) => String(x || '').toLowerCase().replace(/[ً-ٟـ]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي');
const n10 = (p) => String(p || '').replace(/\D/g, '').replace(/^00/, '').slice(-10);
const reply = (t) => [{ kind: 'reply', finalMessage: t }];
const WORDS = /[^a-z0-9؀-ۿ]+/;
function intFind() {
  const text = norm(inp.text), hist = inp.hist || [], clients = inp.clients || [];
  const ok = (v) => v === true || v === 1 || /^(1|true)$/i.test(String(v));
  const m = {};
  hist.forEach((r) => { if (r && r.campaign_id && /tik/i.test(String(r.platform || '')) && ok(r.success) && r.action === 'create') m[String(r.campaign_id)] = r; });
  const tik = Object.values(m);
  const cl = clients.filter((c) => c && c.client && norm(c.client).length >= 3 && text.includes(norm(c.client))).map((c) => norm(c.client));
  const cand = cl.length ? tik.filter((r) => cl.includes(norm(r.client))) : tik;
  if (!cand.length) return reply('ما لكيت حملة تيك توك' + (cl.length ? ' بهذا الحساب' : '') + ' بسجل الحملات. اكتب اسم الحساب واسم الحملة، مثال: "الغ الاهتمامات من حملة زيارات بحساب boostpro7808".');
  const words = new Set(text.split(WORDS).filter((w) => w.length >= 3));
  const score = (r) => norm(r.name).split(WORDS).filter((w) => w.length >= 3 && words.has(w)).length;
  let best = null, bs = -1;
  cand.forEach((r) => { const s = score(r); if (s >= bs) { bs = s; best = r; } });
  if (bs <= 0 && !cl.length) return reply('أي حملة تريد ألغي اهتماماتها؟ اكتب اسمها واسم الحساب، مثال: "الغ الاهتمامات من حملة زيارات بحساب boostpro7808".');
  const row = clients.find((c) => c && c.tiktok_advertiser_id && norm(c.client) === norm(best.client) && (!inp.phone || n10(c.phone) === n10(inp.phone))) || clients.find((c) => c && c.tiktok_advertiser_id && norm(c.client) === norm(best.client));
  const adv = row ? String(row.tiktok_advertiser_id).replace(/\D/g, '') : '';
  if (!adv) return reply('لقيت الحملة "' + best.name + '" بس ما كدرت أحدد حساب تيك توك الإعلاني للعميل "' + best.client + '".');
  return [{ kind: 'find', campaign_id: String(best.campaign_id), name: best.name || '', client: best.client || '', advertiser_id: adv, wantsActivate: /(فعل|شغل|ارفع)/.test(text) }];
}
function intUpd() {
  const c = inp.ctx || {}, ag = inp.ag || {};
  if (ag.code !== 0) return reply('❌ ما كدرت أقرأ مجموعات حملة "' + c.name + '": ' + String(ag.message || 'خطأ غير معروف').slice(0, 200));
  const list = (ag.data && ag.data.list) || [];
  if (!list.length) return reply('ما لكيت مجموعات إعلانية لحملة "' + c.name + '" (يمكن انحذفت). تأكد من الحملة بمدير الإعلانات.');
  const out = [];
  list.forEach((g) => {
    const n = (g.interest_keyword_ids || []).length + (g.interest_category_ids || []).length;
    if (!n) return;
    const body = { advertiser_id: c.advertiser_id, adgroup_id: String(g.adgroup_id), interest_keyword_ids: [], interest_category_ids: [] };
    ['location_ids', 'age_groups', 'languages'].forEach((k) => { if (Array.isArray(g[k]) && g[k].length) body[k] = g[k]; });
    ['gender', 'spending_power', 'pacing', 'dayparting'].forEach((k) => { if (g[k]) body[k] = g[k]; });
    out.push({ ...c, kind: 'upd', adgroup_id: String(g.adgroup_id), had: n, body });
  });
  if (!out.length) return reply('حملة "' + c.name + '" ما عندها اهتمامات أصلاً، ما أحتاج أعدّل شي.');
  return out;
}
function intDone() {
  const ctx = inp.ctx || [], ups = inp.ups || [], ver = inp.ver || [];
  const c = ctx[0] || {};
  let had = 0, bad = '';
  ctx.forEach((x, i) => {
    had += x.had || 0;
    const u = ups[i] || {}, v = ver[i] || {};
    const g = ((v.data && v.data.list) || [])[0] || {};
    const left = (g.interest_keyword_ids || []).length + (g.interest_category_ids || []).length;
    if (u.code !== 0) bad = bad || String(u.message || 'فشل التعديل').slice(0, 200);
    else if (v.code === 0 && left > 0) bad = bad || 'التعديل انقبل بس بقت ' + left + ' اهتمامات';
  });
  if (bad) return reply('❌ ما كملت حذف الاهتمامات من حملة "' + c.name + '": ' + bad);
  return reply('✅ حذفت ' + had + ' اهتمام من حملة "' + c.name + '" (تيك توك).' + (c.wantsActivate ? '\nللتفعيل اكتب: فعل حملة ' + c.name : ''));
}
const out = ({ intFind, intUpd, intDone }[inp.mode] || (() => []))();
return out.map((json) => ({ json }));
